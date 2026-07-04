#!/usr/bin/env python3
"""
Water in the hole, CO2 in the heat exchanger: the deep loop keeps water as
its working fluid (free thermosiphon, high heat capacity - the best downhole
choice per mmwave_co2_model.py), and the surface plant becomes a
TRANSCRITICAL CO2 POWER CYCLE fed by the loop through the heat exchanger,
instead of boiling water for a steam turbine.

Why this matters - the boiler pinch problem
-------------------------------------------
The loop delivers SENSIBLE heat: water cooling smoothly from ~186 C to 50 C.
A steam boiler absorbs most of its heat AT ONE TEMPERATURE (the boiling
point). In a counter-flow exchanger the loop stream slides down its cooling
curve while the steam side sits flat at t_boil - and they collide: checking
the baseline model's boiler (168 C) against its own loop stream shows the
loop water is at ~79 C at the point where boiling starts, where >= 178 C is
required. The idealized steam plant in ground_loop_model.py is therefore
~3x optimistic. This file adds:

  1. steam_plant_pinched() - an honest single-pressure steam plant: scans
     boiler temperature, enforces the internal evaporator pinch and the
     cold-end approach, and picks the boiler temperature that maximizes
     turbine output. (Boiling low wastes exergy; boiling high strands heat -
     the scan finds the best compromise.)
  2. co2_plant() - a transcritical CO2 cycle: supercritical CO2 at ~200 bar
     absorbs heat with a temperature GLIDE that parallels the water's
     cooling curve, so there is no internal pinch and the loop water can be
     cooled all the way to the cold-end approach. Work is computed from the
     exergy of the transferred heat times a second-law efficiency
     eta_II = 0.50 (literature range 0.40-0.55 for transcritical CO2 at
     100-250 C sources with wet cooling), rather than from a fabricated CO2
     equation of state. The band is carried through the results.
  3. The idealized steam plant kept as a reference line, clearly labeled.

Also modeled: sCO2 turbomachinery is ~10x smaller than a low-pressure steam
turbine, so surface plant capital drops ($2,500/kW vs $3,500/kW here).

Run:  python3 co2_power_cycle_model.py
      python3 co2_power_cycle_model.py --depth-miles 6
"""

import argparse
import math
import os

import numpy as np

from ground_loop_model import (MILE, YEAR, Config, sat_props, solve_loop,
                               run_plant)
from drilling_cost_model import (AVAILABILITY, BENCHMARKS, DISCOUNT_RATE,
                                 LIFETIME_YR, capex_breakdown, annual_om,
                                 money)
from mmwave_co2_model import co2_capex, co2_annual_om, dcf_lcoe

T0_AMBIENT = 25.0            # C, dead-state / cooling-sink temperature
ETA_II_CO2 = 0.50            # transcritical CO2 second-law efficiency (base)
ETA_II_CO2_BAND = (0.40, 0.55)
PLANT_KW_STEAM = 3500.0      # $/kW-e installed
PLANT_KW_CO2 = 2500.0        # $/kW-e installed (compact turbomachinery)


# ---------------------------------------------------------------------------
# Surface plants (all fed by: loop water at t_hot, mass flow mdot_loop)
# ---------------------------------------------------------------------------
def exergy_of_stream(mdot_loop, cp, t_hot, t_ret, t0=T0_AMBIENT):
    """Maximum work obtainable from cooling the stream t_hot -> t_ret."""
    th, tc, tz = t_hot + 273.15, t_ret + 273.15, t0 + 273.15
    if th <= tc:
        return 0.0
    q = mdot_loop * cp * (t_hot - t_ret)
    return q * (1.0 - tz * math.log(th / tc) / (th - tc))


def steam_plant_pinched(cfg: Config, mdot_loop: float, t_hot: float) -> dict:
    """Single-pressure saturated steam plant with the internal pinch enforced.

    Scans boiler temperature; for each, the evaporator pinch caps how much
    steam can be raised, which in turn sets how far the loop water is cooled.
    Returns the boiler temperature that maximizes net work.
    """
    cp = cfg.cp_f
    cold = sat_props(cfg.t_condenser)
    t_ret_floor = cfg.t_condenser + cfg.dt_pinch_cold
    best = dict(w_net=0.0, t_boil=0.0, t_ret=t_hot, q=0.0, mdot_steam=0.0,
                x_exhaust=0.0)
    t_max = t_hot - cfg.dt_pinch_hot
    if t_max <= cfg.t_condenser + 6:
        return best
    for t_boil in np.arange(cfg.t_condenser + 6, t_max, 1.0):
        hot = sat_props(t_boil)
        h_g = hot["h_f"] + hot["h_fg"]
        # Evaporator pinch: steam raised is capped by the loop temperature
        # drop available above (t_boil + pinch).
        ms = mdot_loop * cp * (t_hot - t_boil - cfg.dt_pinch_hot) \
            / (hot["h_fg"] * 1e3)
        if ms <= 0:
            continue
        t_ret = t_hot - ms * (h_g - cold["h_f"]) * 1e3 / (mdot_loop * cp)
        if t_ret < t_ret_floor:
            # Cold end limits instead: size steam flow from total duty.
            t_ret = t_ret_floor
            ms = mdot_loop * cp * (t_hot - t_ret) / ((h_g - cold["h_f"]) * 1e3)
        q = mdot_loop * cp * (t_hot - t_ret)
        s1 = hot["s_f"] + hot["s_fg"]
        x2s = (s1 - cold["s_f"]) / cold["s_fg"]
        h2s = cold["h_f"] + x2s * cold["h_fg"]
        dh = cfg.eta_turbine_is * (h_g - h2s)
        w = ms * dh * 1e3 * cfg.eta_generator
        w -= ms * 0.001 * (hot["p_bar"] - cold["p_bar"]) * 1e5 / cfg.eta_pump
        if w > best["w_net"]:
            x2 = (h_g - dh - cold["h_f"]) / cold["h_fg"]
            best = dict(w_net=w, t_boil=float(t_boil), t_ret=float(t_ret),
                        q=q, mdot_steam=ms, x_exhaust=x2)
    return best


def co2_plant(cfg: Config, mdot_loop: float, t_hot: float,
              eta_ii: float = ETA_II_CO2) -> dict:
    """Transcritical CO2 secondary cycle: gliding heat absorption, no
    internal pinch, loop water cooled to the cold-end approach."""
    t_ret = cfg.t_condenser + cfg.dt_pinch_cold   # CO2 glide permits full cooldown
    if t_hot <= t_ret + 5:
        return dict(w_net=0.0, t_ret=t_hot, q=0.0, eta_ii=eta_ii)
    q = mdot_loop * cfg.cp_f * (t_hot - t_ret)
    x = exergy_of_stream(mdot_loop, cfg.cp_f, t_hot, t_ret)
    return dict(w_net=eta_ii * x, t_ret=t_ret, q=q, eta_ii=eta_ii)


def steam_plant_idealized(cfg: Config, mdot_loop: float, t_hot: float) -> dict:
    """The original (pinch-violating) boiler from ground_loop_model.py,
    kept as a reference for how optimistic it was."""
    class _L:  # minimal stand-in for LoopResult
        t_top = t_hot
        pump = 0.0
        pump_power = 0.0
    res = run_plant(cfg, _L, mdot_loop)
    return dict(w_net=res.w_net, q=res.q_thermal)


PLANTS = {
    "steam-idealized": ("Steam, idealized boiler (no pinch check)",
                        steam_plant_idealized),
    "steam-pinched":   ("Steam, pinch-feasible single-pressure",
                        steam_plant_pinched),
    "co2-hx":          ("Transcritical CO2 cycle in the HX",
                        co2_plant),
}


# ---------------------------------------------------------------------------
# Coupling to the water loop
# ---------------------------------------------------------------------------
def net_power(cfg: Config, mdot: float, t_op: float, plant_key: str) -> float:
    loop = solve_loop(cfg, mdot=mdot, t_operate=t_op)
    w = PLANTS[plant_key][1](cfg, mdot, loop.t_top)["w_net"]
    return max(0.0, w - loop.pump_power)


def optimize_flow(cfg: Config, plant_key: str, t_op: float) -> float:
    best, best_w = 1.0, -1.0
    for m in np.linspace(1, 60, 60):
        w = net_power(cfg, float(m), t_op, plant_key)
        if w > best_w:
            best, best_w = float(m), w
    return best


def energy_series_mwh(cfg: Config, mdot: float, plant_key: str) -> np.ndarray:
    return np.array([
        net_power(cfg, mdot, (y + 0.5) * YEAR, plant_key) / 1e6
        * 8766 * AVAILABILITY
        for y in range(LIFETIME_YR)
    ])


def lcoe_for(depth_m, net_kw, energy, drilling: str, plant_usd_kw: float):
    """LCOE under either drilling basis, with a plant-specific $/kW."""
    if drilling == "rotary":
        cap = capex_breakdown(depth_m, net_kw, "base")
        # swap the plant line for this plant's cost
        cap["TOTAL"] += (max(1.5e6, plant_usd_kw * net_kw)
                         - cap["Surface steam plant"])
        cap["Surface steam plant"] = max(1.5e6, plant_usd_kw * net_kw)
        return dcf_lcoe(cap["TOTAL"], annual_om(cap), energy)
    cap = co2_capex(depth_m, net_kw, "base")
    cap["TOTAL"] += (max(1.5e6, plant_usd_kw * net_kw)
                     - cap["Surface plant (steam + expander)"])
    cap["Surface plant (steam + expander)"] = max(1.5e6, plant_usd_kw * net_kw)
    return dcf_lcoe(cap["TOTAL"], co2_annual_om(cap), energy)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
def run_analysis(depth_m: float, gradient: float):
    cfg = Config(depth=depth_m, geo_gradient=gradient, n_segments=200)
    out = {}
    for key, (label, _) in PLANTS.items():
        mdot = optimize_flow(cfg, key, 10 * YEAR)
        loop = solve_loop(cfg, mdot=mdot, t_operate=10 * YEAR)
        detail = PLANTS[key][1](cfg, mdot, loop.t_top)
        energy = energy_series_mwh(cfg, mdot, key)
        x = exergy_of_stream(mdot, cfg.cp_f, loop.t_top,
                             detail.get("t_ret", cfg.t_inject))
        out[key] = dict(label=label, mdot=mdot, t_top=loop.t_top,
                        detail=detail, energy=energy,
                        w_net=max(0.0, detail["w_net"] - loop.pump_power),
                        eta_ii=(detail["w_net"] / x if x > 0 else 0.0))
    return cfg, out


def print_report(depth_m, cfg, out):
    w = 74
    print("=" * w)
    print(f"WATER LOOP + CO2 POWER CYCLE - {depth_m/MILE:.1f} miles, "
          f"rock {cfg.ground_temp(depth_m):.0f} C at bottom")
    print("=" * w)
    print(f"{'Surface plant':<42}{'flow':>6}{'T_top':>7}{'T_ret':>7}"
          f"{'MWe':>7}")
    for key in ("steam-idealized", "steam-pinched", "co2-hx"):
        r = out[key]
        t_ret = r["detail"].get("t_ret", cfg.t_inject)
        print(f"{r['label']:<42}{r['mdot']:>5.0f} {r['t_top']:>6.0f} "
              f"{t_ret:>6.0f} {r['w_net']/1e6:>6.2f}")
    print("-" * w)
    sp = out["steam-pinched"]["detail"]
    print(f"Pinch-feasible steam details : boiler {sp['t_boil']:.0f} C, "
          f"loop water can only be cooled to {sp['t_ret']:.0f} C")
    print(f"  -> the single-pressure boiler STRANDS the heat below "
          f"{sp['t_ret']:.0f} C")
    co2 = out["co2-hx"]
    lo, hi = ETA_II_CO2_BAND
    print(f"CO2 cycle details            : gliding absorption cools loop to "
          f"{co2['detail']['t_ret']:.0f} C,")
    print(f"  second-law eff. {ETA_II_CO2:.2f} "
          f"(band {lo:.2f}-{hi:.2f} -> "
          f"{co2['w_net']*lo/ETA_II_CO2/1e6:.2f}-"
          f"{co2['w_net']*hi/ETA_II_CO2/1e6:.2f} MWe)")
    gain = co2["w_net"] / max(out["steam-pinched"]["w_net"], 1.0)
    print(f"CO2-in-HX vs feasible steam  : {gain:.2f}x the net power")
    print(f"(Idealized steam reference overstates feasible steam by "
          f"{out['steam-idealized']['w_net']/max(out['steam-pinched']['w_net'],1.0):.1f}x"
          f" - see module docstring)")
    print("-" * w)
    print("LCOE (base cost scenarios, 7% real, 30 yr):")
    print(f"{'':<42}{'Rotary':>14}{'MM-wave':>14}")
    for key in ("steam-pinched", "co2-hx"):
        r = out[key]
        usd_kw = PLANT_KW_CO2 if key == "co2-hx" else PLANT_KW_STEAM
        net_kw = r["w_net"] / 1e3
        lr = lcoe_for(depth_m, net_kw, r["energy"], "rotary", usd_kw)
        lm = lcoe_for(depth_m, net_kw, r["energy"], "mmwave", usd_kw)
        print(f"{r['label']:<42}{'$'+format(lr, ',.0f'):>14}"
              f"{'$'+format(lm, ',.0f'):>14}")
    print("-" * w)
    for name, v in BENCHMARKS[1:3]:
        print(f"  {name:<40}: ${v}/MWh")
    print("=" * w)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
def make_plots(outdir, gradient):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)
    cfg = Config(geo_gradient=gradient)   # only cp / pinch constants used

    # 1. Net work per kg of loop water vs delivery temperature --------------
    t_hots = np.linspace(80, 300, 90)
    per_kg = {k: [] for k in PLANTS}
    band_lo, band_hi = [], []
    for th in t_hots:
        for key in PLANTS:
            per_kg[key].append(PLANTS[key][1](cfg, 1.0, th)["w_net"] / 1e3)
        band_lo.append(co2_plant(cfg, 1.0, th, ETA_II_CO2_BAND[0])["w_net"] / 1e3)
        band_hi.append(co2_plant(cfg, 1.0, th, ETA_II_CO2_BAND[1])["w_net"] / 1e3)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.fill_between(t_hots, band_lo, band_hi, color="#1baf7a", alpha=0.18, lw=0)
    ax.plot(t_hots, per_kg["co2-hx"], color="#1baf7a", lw=2,
            label="Transcritical CO₂ cycle (η_II 0.40–0.55)")
    ax.plot(t_hots, per_kg["steam-pinched"], color="#2a78d6", lw=2,
            label="Steam, pinch-feasible")
    ax.plot(t_hots, per_kg["steam-idealized"], color="#898781", lw=1.5,
            ls="--", label="Steam, idealized (pinch violated)")
    ax.set_xlabel("Loop water delivery temperature (°C)")
    ax.set_ylabel("Net work per kg of loop water (kJ/kg)")
    ax.set_title("Surface plant comparison on a sensible-heat stream\n"
                 "(water cooled toward 50 °C; condenser/sink 40/25 °C)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "plant_comparison_vs_temp.png"), dpi=130)
    plt.close(fig)

    # 2. LCOE vs depth: pinched steam vs CO2 HX (mm-wave base costs) ---------
    depths_mi = np.arange(3.0, 12.01, 1.0)
    lcoes = {"steam-pinched": [], "co2-hx": []}
    for dm in depths_mi:
        _, out = run_analysis(dm * MILE, gradient)
        for key in lcoes:
            r = out[key]
            usd_kw = PLANT_KW_CO2 if key == "co2-hx" else PLANT_KW_STEAM
            lcoes[key].append(lcoe_for(dm * MILE, r["w_net"] / 1e3,
                                       r["energy"], "mmwave", usd_kw))
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.semilogy(depths_mi, lcoes["steam-pinched"], color="#2a78d6", lw=2,
                label="Steam, pinch-feasible")
    ax.semilogy(depths_mi, lcoes["co2-hx"], color="#1baf7a", lw=2,
                label="Transcritical CO₂ cycle")
    ax.axhline(80, color="#898781", lw=1, ls=":")
    ax.annotate("Conventional geothermal (~\\$80)", (depths_mi[0], 80),
                textcoords="offset points", xytext=(2, 4), fontsize=8,
                color="#52514e")
    ax.set_xlabel("Loop depth (miles)")
    ax.set_ylabel("LCOE ($/MWh, log scale)")
    ax.set_title("Water loop + surface plant choice, mm-wave base drilling")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "co2_hx_lcoe_vs_depth.png"), dpi=130)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description="water loop + CO2 power cycle")
    p.add_argument("--depth-miles", type=float, default=8.0)
    p.add_argument("--gradient", type=float, default=28.0)
    p.add_argument("--no-plots", action="store_true")
    args = p.parse_args()

    depth_m = args.depth_miles * MILE
    grad = args.gradient / 1000.0
    cfg, out = run_analysis(depth_m, grad)
    print_report(depth_m, cfg, out)

    if not args.no_plots:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "results")
        print("\nGenerating plots (depth sweep 3-12 miles)...")
        make_plots(outdir, grad)
        print(f"Plots written to {outdir}/")


if __name__ == "__main__":
    main()
