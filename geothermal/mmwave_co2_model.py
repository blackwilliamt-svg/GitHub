#!/usr/bin/env python3
"""
Hypothetical advanced-technology variant of the deep closed-loop system:
millimeter-wave drilled boreholes with supercritical CO2 as the loop fluid.

Technology assumptions (hypothetical, flagged as such)
------------------------------------------------------
MILLIMETER-WAVE DRILLING (Quaise/MIT gyrotron concept):
  * Conventional rotary drilling for the top 3.5 km (sediments/casing zone),
    mm-wave vaporization below that.
  * Cost of the mm-wave section scales ~LINEARLY with depth (energy-based,
    no bit trips, penetration rate roughly depth-independent) instead of the
    super-linear conventional curve. Three $/m scenarios bracket the guess.
  * The mm-wave process vitrifies the borehole wall into a glass liner, so
    the DOWN leg needs no steel pipe at all - the sealed hole itself is the
    conduit, and the rock is in direct contact with the working fluid.
    The UP leg still hangs vacuum-insulated tubing inside the hole.

SUPERCRITICAL CO2 WORKING FLUID (CO2-Plume-Geothermal-style closed loop):
  * CO2 is supercritical everywhere in the loop (> 31 C, > 7.4 MPa).
  * Large thermal expansion (beta ~ 3e-3 /K) gives two effects water barely
    has:
      1. GRAVITATIONAL COMPRESSION HEATING: descending CO2 warms by
         dT/dz = g*T*beta/cp  (~7-9 C per km), and cools by the same
         mechanism on the way up. The temperature march includes this term.
      2. A VERY LARGE THERMOSIPHON: the cold/hot column density difference
         reaches tens of MPa - far more than friction needs - so the excess
         wellhead pressure drives a surface TURBO-EXPANDER that generates
         power on top of the steam cycle.
  * Heat remaining after the expander boils water for the same saturated
    steam Rankine plant as the baseline model ("CO2 as the medium for steam
    generation").
  * CO2 properties are treated as constants representative of 25-60 MPa,
    50-350 C (real sCO2 properties vary strongly near the critical point;
    a Span-Wagner EOS would refine this).

Run:  python3 mmwave_co2_model.py                 (8-mile report + sweeps)
      python3 mmwave_co2_model.py --depth-miles 12
"""

import argparse
import math
import os

import numpy as np

from ground_loop_model import (INCH, MILE, YEAR, Config, sat_props,
                               ground_resistance, wall_resistance,
                               insulation_resistance, friction_factor)
from drilling_cost_model import (AVAILABILITY, BENCHMARKS, CONNECTOR_COST,
                                 CONTINGENCY_FRAC, DISCOUNT_RATE,
                                 ENGINEERING_FRac, LIFETIME_YR, OM_FIXED,
                                 OM_PLANT_FRAC, OM_WELL_FRAC,
                                 PIPE_COST_UP_VIT, PLANT_COST_FLOOR,
                                 PLANT_COST_PER_KW, capex_breakdown,
                                 annual_om, lukawski_well_cost,
                                 analyze_depth, money)

# ---------------------------------------------------------------------------
# Supercritical CO2 loop-fluid properties (representative constants)
# ---------------------------------------------------------------------------
CO2 = dict(
    rho0=700.0,     # kg/m^3 at T0 (dense supercritical, ~25-60 MPa)
    t0=50.0,        # C reference for the density law
    beta=3.0e-3,    # 1/K volumetric expansion (order of magnitude > water)
    rho_min=250.0,  # floor on the linear density law
    cp=1250.0,      # J/kg-K
    k=0.055,        # W/m-K
    mu=4.5e-5,      # Pa-s
)
ETA_EXPANDER = 0.80     # surface turbo-expander isentropic x mechanical
DP_MARGIN = 2e5         # Pa of thermosiphon head reserved to keep circulating

# ---------------------------------------------------------------------------
# Millimeter-wave drilling cost (2026$, hypothetical)
# ---------------------------------------------------------------------------
ROTARY_SECTION_M = 3500.0        # conventional top-hole before mm-wave
MMWAVE_RATES = {                  # $/m for the mm-wave section
    "optimistic":  {"rate": 500.0,  "label": "Optimistic mm-wave ($500/m)"},
    "base":        {"rate": 1200.0, "label": "Base mm-wave ($1,200/m)"},
    "pessimistic": {"rate": 3000.0, "label": "Pessimistic mm-wave ($3,000/m)"},
}
GYROTRON_SITE_COST = 20e6        # gyrotron units, waveguides, site (project)


def mmwave_well_cost(depth_m: float, scenario: str) -> float:
    conv = lukawski_well_cost(min(depth_m, ROTARY_SECTION_M))
    mm = MMWAVE_RATES[scenario]["rate"] * max(0.0, depth_m - ROTARY_SECTION_M)
    return conv + mm


# ---------------------------------------------------------------------------
# CO2 loop physics
# ---------------------------------------------------------------------------
def co2_density(t_c):
    return max(CO2["rho_min"],
               CO2["rho0"] * (1.0 - CO2["beta"] * (t_c - CO2["t0"])))


def co2_convection_resistance(cfg: Config, mdot: float, t_ref: float) -> float:
    """Dittus-Boelter with CO2 properties at a representative temperature."""
    r_in = cfg.pipe_id / 2
    rho = co2_density(t_ref)
    v = mdot / (rho * math.pi * r_in ** 2)
    re = rho * v * cfg.pipe_id / CO2["mu"]
    pr = CO2["cp"] * CO2["mu"] / CO2["k"]
    nu = 0.023 * re ** 0.8 * pr ** 0.4 if re > 4000 else 4.36
    h = nu * CO2["k"] / cfg.pipe_id
    return 1.0 / (2 * math.pi * r_in * h)


def adiabatic_gradient(t_c: float) -> float:
    """Isentropic compression heating of sCO2, K per metre of descent."""
    return 9.81 * (t_c + 273.15) * CO2["beta"] / CO2["cp"]


def march_leg_co2(t_in, z, tg, r_total, mdot, downward):
    """Exponential relaxation march including gravitational compression."""
    tau = mdot * CO2["cp"] * r_total
    n = len(z)
    t = np.empty(n)
    idx = (lambda s: s) if downward else (lambda s: n - 1 - s)
    tf = t_in
    t[idx(0)] = tf
    sign = 1.0 if downward else -1.0
    for s in range(1, n):
        i, j = idx(s), idx(s - 1)
        dz = abs(z[i] - z[j])
        tf = tf + sign * adiabatic_gradient(tf) * dz     # compression term
        tg_mid = 0.5 * (tg[i] + tg[j])
        tf = tg_mid + (tf - tg_mid) * math.exp(-dz / tau)  # rock exchange
        t[i] = tf
    return t


def solve_co2_loop(cfg: Config, mdot: float, t_operate: float):
    n = cfg.n_segments + 1
    z = np.linspace(0.0, cfg.depth, n)
    tg = cfg.ground_temp(z)

    r_in = cfg.pipe_id / 2
    r_out = r_in + cfg.wall_thickness
    t_ref = 0.5 * (cfg.t_inject + cfg.ground_temp(cfg.depth))
    r_conv = co2_convection_resistance(cfg, mdot, t_ref)

    # Down leg: OPEN vitrified hole - no steel wall, rock right at the fluid.
    r_down = r_conv + ground_resistance(cfg, r_in, t_operate)
    # Up leg: VIT hung in the hole, as in the baseline system.
    r_bore_up = r_out + cfg.insulation_thickness
    r_up = (r_conv + wall_resistance(cfg) + insulation_resistance(cfg)
            + ground_resistance(cfg, r_bore_up, t_operate))

    t_down = march_leg_co2(cfg.t_inject, z, tg, r_down, mdot, True)
    t_up = march_leg_co2(t_down[-1], z, tg, r_up, mdot, False)

    # Thermosiphon from the actual density profiles of both columns.
    rho_down = np.array([co2_density(t) for t in t_down])
    rho_up = np.array([co2_density(t) for t in t_up])
    dp_buoy = 9.81 * float(np.trapezoid(rho_down - rho_up, z))

    # Friction, evaluated per leg with that leg's mean density.
    area = math.pi * r_in ** 2
    dp_fric = 0.0
    for rho_leg in (float(rho_down.mean()), float(rho_up.mean())):
        v = mdot / (rho_leg * area)
        re = rho_leg * v * cfg.pipe_id / CO2["mu"]
        f = friction_factor(re, cfg.pipe_roughness / cfg.pipe_id)
        dp_fric += f * cfg.depth / cfg.pipe_id * 0.5 * rho_leg * v ** 2

    # Excess head drives a surface turbo-expander before the boiler.
    dp_excess = max(0.0, dp_buoy - dp_fric - DP_MARGIN)
    rho_top = co2_density(float(t_up[0]))
    w_expander = ETA_EXPANDER * mdot * dp_excess / rho_top
    dt_expander = w_expander / (mdot * CO2["cp"])  # enthalpy leaves the fluid

    return dict(z=z, tg=tg, t_down=t_down, t_up=t_up,
                t_bottom=float(t_down[-1]), t_top=float(t_up[0]),
                dp_buoy=dp_buoy, dp_fric=dp_fric, dp_excess=dp_excess,
                w_expander=w_expander, t_hx_in=float(t_up[0]) - dt_expander)


def steam_cycle(q_thermal: float, t_hot: float, cfg: Config):
    """Saturated Rankine plant fed q_thermal at hot-fluid temperature t_hot."""
    t_boil = min(t_hot - cfg.dt_pinch_hot, cfg.t_boiler_max)
    if q_thermal <= 0 or t_boil <= cfg.t_condenser + 5.0:
        return dict(w_net=0.0, t_boil=t_boil, p_bar=0.0, mdot_steam=0.0)
    hot = sat_props(t_boil)
    cold = sat_props(cfg.t_condenser)
    h1 = hot["h_f"] + hot["h_fg"]
    mdot_steam = q_thermal / ((h1 - cold["h_f"]) * 1e3)
    s1 = hot["s_f"] + hot["s_fg"]
    x2s = (s1 - cold["s_f"]) / cold["s_fg"]
    h2s = cold["h_f"] + x2s * cold["h_fg"]
    h2 = h1 - cfg.eta_turbine_is * (h1 - h2s)
    w_turb = mdot_steam * (h1 - h2) * 1e3 * cfg.eta_generator
    w_feed = mdot_steam * 0.001 * (hot["p_bar"] - cold["p_bar"]) * 1e5 / cfg.eta_pump
    return dict(w_net=w_turb - w_feed, t_boil=t_boil, p_bar=hot["p_bar"],
                mdot_steam=mdot_steam)


def run_co2_case(cfg: Config, mdot: float, t_operate: float):
    loop = solve_co2_loop(cfg, mdot, t_operate)
    q_hx = max(0.0, mdot * CO2["cp"] * (loop["t_hx_in"] - cfg.t_inject))
    steam = steam_cycle(q_hx, loop["t_hx_in"], cfg)
    w_net = steam["w_net"] + loop["w_expander"]
    return dict(loop=loop, steam=steam, q_hx=q_hx, w_net=w_net,
                q_ground=mdot * CO2["cp"] * (loop["t_top"] - cfg.t_inject))


def co2_optimum_flow(cfg: Config, t_operate: float) -> float:
    best, best_w = 5.0, -1.0
    for m in np.linspace(5, 200, 66):
        w = run_co2_case(cfg, m, t_operate)["w_net"]
        if w > best_w:
            best, best_w = float(m), w
    return best


# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------
def co2_capex(depth_m: float, net_kw: float, scenario: str) -> dict:
    wells = 2 * mmwave_well_cost(depth_m, scenario)
    vit = depth_m * PIPE_COST_UP_VIT            # up leg only; down leg is bare
    plant = max(PLANT_COST_FLOOR, PLANT_COST_PER_KW * max(net_kw, 0.0))
    direct = wells + GYROTRON_SITE_COST + vit + CONNECTOR_COST + plant
    eng = ENGINEERING_FRac * direct
    cont = CONTINGENCY_FRAC * (wells + GYROTRON_SITE_COST + vit + CONNECTOR_COST)
    return {
        "Drilling (2 mm-wave wells)": wells,
        "Gyrotron & site equipment": GYROTRON_SITE_COST,
        "Up-leg VIT (down leg bare)": vit,
        "Bottom connection": CONNECTOR_COST,
        "Surface plant (steam + expander)": plant,
        "Engineering & owner's": eng,
        "Contingency": cont,
        "TOTAL": direct + eng + cont,
    }


def co2_annual_om(cap: dict) -> float:
    wells_like = (cap["Drilling (2 mm-wave wells)"]
                  + cap["Gyrotron & site equipment"]
                  + cap["Up-leg VIT (down leg bare)"] + cap["Bottom connection"])
    return (OM_WELL_FRAC * wells_like
            + OM_PLANT_FRAC * cap["Surface plant (steam + expander)"] + OM_FIXED)


def dcf_lcoe(capex_total, om_yr, energy_mwh):
    disc = 1.0 / (1.0 + DISCOUNT_RATE) ** np.arange(1, LIFETIME_YR + 1)
    pv_e = float(np.sum(energy_mwh * disc))
    return (capex_total + om_yr * float(np.sum(disc))) / pv_e if pv_e > 0 else float("inf")


def analyze_co2_depth(depth_m: float, gradient: float = 0.028):
    cfg = Config(depth=depth_m, geo_gradient=gradient, n_segments=200)
    mdot = co2_optimum_flow(cfg, 10 * YEAR)
    case = run_co2_case(cfg, mdot, 10 * YEAR)
    energy = np.array([
        max(run_co2_case(cfg, mdot, (y + 0.5) * YEAR)["w_net"], 0.0)
        / 1e6 * 8766 * AVAILABILITY
        for y in range(LIFETIME_YR)
    ])
    net_kw = case["w_net"] / 1e3
    scenarios = {}
    for sc in MMWAVE_RATES:
        cap = co2_capex(depth_m, net_kw, sc)
        scenarios[sc] = {"capex": cap, "om": co2_annual_om(cap),
                         "lcoe": dcf_lcoe(cap["TOTAL"], co2_annual_om(cap), energy)}
    return dict(cfg=cfg, mdot=mdot, case=case, energy=energy,
                scenarios=scenarios)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_report(depth_m, r, water_ref):
    w = 68
    case, loop = r["case"], r["case"]["loop"]
    print("=" * w)
    print(f"HYPOTHETICAL: MM-WAVE DRILLING + sCO2 LOOP - "
          f"{depth_m/MILE:.1f} miles ({depth_m/1000:.1f} km)")
    print("=" * w)
    print(f"Optimal CO2 flow            : {r['mdot']:7.0f} kg/s "
          f"(vs ~8 kg/s for water - low cp needs more flow)")
    print(f"CO2 at bottom / at surface  : {loop['t_bottom']:7.1f} / "
          f"{loop['t_top']:.1f} C")
    print(f"  compression heating adds ~"
          f"{adiabatic_gradient(150)*1000:.1f} C/km on descent")
    print(f"Thermosiphon / friction     : {loop['dp_buoy']/1e5:7.0f} / "
          f"{loop['dp_fric']/1e5:.0f} bar")
    print(f"Excess head to expander     : {loop['dp_excess']/1e5:7.0f} bar")
    print("-" * w)
    print(f"Turbo-expander power        : {loop['w_expander']/1e6:7.2f} MWe")
    print(f"Steam cycle net power       : {case['steam']['w_net']/1e6:7.2f} MWe "
          f"(boiler {case['steam']['t_boil']:.0f} C, "
          f"{case['steam']['p_bar']:.0f} bar, "
          f"{case['steam']['mdot_steam']:.1f} kg/s steam)")
    print(f"TOTAL NET POWER             : {case['w_net']/1e6:7.2f} MWe "
          f"(water baseline: {water_ref['plant'].w_net/1e6:.2f} MWe)")
    e = r["energy"]
    print(f"Lifetime energy (30 yr)     : {e.sum()/1e3:7.1f} GWh")
    print("-" * w)
    print("Millimeter-wave drilling cost per well:")
    for sc, meta in MMWAVE_RATES.items():
        print(f"  {meta['label']:<42}: {money(mmwave_well_cost(depth_m, sc))}")
    print("-" * w)
    base = r["scenarios"]["base"]["capex"]
    print("Capital breakdown (BASE mm-wave scenario):")
    for k, v in base.items():
        if k != "TOTAL":
            print(f"  {k:<34}: {money(v):>9}  ({v/base['TOTAL']*100:4.1f} %)")
    per_w = f"   = ${base['TOTAL']/case['w_net']:,.0f}/W-e" if case["w_net"] > 0 else ""
    print(f"  {'TOTAL CAPEX':<34}: {money(base['TOTAL']):>9}{per_w}")
    print("-" * w)
    print("LCOE (7% real, 30 yr, 95% availability):")
    for sc, meta in MMWAVE_RATES.items():
        v = r["scenarios"][sc]["lcoe"]
        print(f"  {meta['label']:<42}: ${v:,.0f}/MWh")
    print("-" * w)
    # 2x2 matrix: which change buys what? (base cost scenarios throughout)
    water_kw = water_ref["plant"].w_net / 1e3
    co2_kw = case["w_net"] / 1e3
    cap_w_mm = co2_capex(depth_m, water_kw, "base")
    lcoe_w_mm = dcf_lcoe(cap_w_mm["TOTAL"], co2_annual_om(cap_w_mm),
                         water_ref["energy"])
    cap_c_rot = capex_breakdown(depth_m, co2_kw, "base")
    lcoe_c_rot = dcf_lcoe(cap_c_rot["TOTAL"], annual_om(cap_c_rot), r["energy"])
    print("LCOE matrix - separating the two technology changes (base costs):")
    print(f"  {'':<22}{'Rotary drilling':>18}{'MM-wave drilling':>18}")
    print(f"  {'Water loop':<22}"
          f"{'$'+format(water_ref['scenarios']['base']['lcoe'], ',.0f'):>18}"
          f"{'$'+format(lcoe_w_mm, ',.0f'):>18}")
    print(f"  {'sCO2 loop':<22}"
          f"{'$'+format(lcoe_c_rot, ',.0f'):>18}"
          f"{'$'+format(r['scenarios']['base']['lcoe'], ',.0f'):>18}")
    print("-" * w)
    print("For context:")
    for name, v in BENCHMARKS:
        print(f"  {name:<42}: ${v}/MWh")
    print("=" * w)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
def make_plots(outdir, depth_m, gradient, water_ref):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)

    # 1. Temperature profiles: CO2 vs water --------------------------------
    cfg = Config(depth=depth_m, geo_gradient=gradient, n_segments=400)
    mdot = co2_optimum_flow(cfg, 10 * YEAR)
    loop = solve_co2_loop(cfg, mdot, 10 * YEAR)
    wl = water_ref["loop"]
    fig, ax = plt.subplots(figsize=(7, 8))
    km = loop["z"] / 1000
    ax.plot(loop["tg"], km, "k--", lw=1.2, label="Undisturbed rock")
    ax.plot(loop["t_down"], km, color="#2166ac", lw=2, label="CO$_2$ down (open hole)")
    ax.plot(loop["t_up"], km, color="#b2182b", lw=2, label="CO$_2$ up (insulated)")
    ax.plot(wl.t_down, wl.z / 1000, color="#2166ac", lw=1.2, ls=":",
            label="Water down (baseline)")
    ax.plot(wl.t_up, wl.z / 1000, color="#b2182b", lw=1.2, ls=":",
            label="Water up (baseline)")
    ax.invert_yaxis()
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Depth (km)")
    ax.set_title(f"sCO$_2$ vs water loop at {depth_m/MILE:.0f} miles\n"
                 "(note CO$_2$ compression heating on descent)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "co2_temperature_profile.png"), dpi=130)
    plt.close(fig)

    # 2. LCOE vs depth: mm-wave scenarios vs conventional -------------------
    depths_mi = np.arange(2.0, 12.01, 1.0)
    colors = {"optimistic": "#1baf7a", "base": "#2a78d6", "pessimistic": "#e34948"}
    lcoes = {sc: [] for sc in MMWAVE_RATES}
    conv = []
    for dm in depths_mi:
        rr = analyze_co2_depth(dm * MILE, gradient)
        for sc in MMWAVE_RATES:
            lcoes[sc].append(rr["scenarios"][sc]["lcoe"])
        conv.append(analyze_depth(dm * MILE, gradient)["scenarios"]["base"]["lcoe"])
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.semilogy(depths_mi, conv, color="#898781", lw=2, ls="--",
                label="Water + rotary drilling (base)")
    for sc, meta in MMWAVE_RATES.items():
        ax.semilogy(depths_mi, lcoes[sc], color=colors[sc], lw=2,
                    label=meta["label"].replace("$", "\\$") + " + sCO₂")
        i = int(np.argmin(lcoes[sc]))
        ax.plot(depths_mi[i], lcoes[sc][i], "o", color=colors[sc], ms=6)
    for name, v in BENCHMARKS[2:3]:
        ax.axhline(v, color="#898781", lw=1, ls=":")
        ax.annotate(f"{name} (~${v})", (depths_mi[0], v),
                    textcoords="offset points", xytext=(2, 4), fontsize=8,
                    color="#52514e")
    ax.set_xlabel("Loop depth (miles)")
    ax.set_ylabel("LCOE ($/MWh, log scale)")
    ax.set_title("Hypothetical mm-wave + sCO$_2$ economics vs the baseline")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "mmwave_lcoe_vs_depth.png"), dpi=130)
    plt.close(fig)
    return depths_mi, lcoes, conv


def main():
    p = argparse.ArgumentParser(description="mm-wave + sCO2 hypothetical model")
    p.add_argument("--depth-miles", type=float, default=8.0)
    p.add_argument("--gradient", type=float, default=28.0)
    p.add_argument("--no-plots", action="store_true")
    args = p.parse_args()

    depth_m = args.depth_miles * MILE
    grad = args.gradient / 1000.0

    water_ref = analyze_depth(depth_m, grad)   # baseline for comparison
    r = analyze_co2_depth(depth_m, grad)
    print_report(depth_m, r, water_ref)

    if not args.no_plots:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
        print("\nRunning depth sweep for plots (2-12 miles)...")
        depths_mi, lcoes, conv = make_plots(outdir, depth_m, grad, water_ref)
        for sc, meta in MMWAVE_RATES.items():
            i = int(np.argmin(lcoes[sc]))
            print(f"  {meta['label']:<42}: best {depths_mi[i]:.0f} mi "
                  f"-> ${lcoes[sc][i]:,.0f}/MWh")
        print(f"\nPlots written to {outdir}/")


if __name__ == "__main__":
    main()
