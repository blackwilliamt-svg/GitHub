#!/usr/bin/env python3
"""
Drilling cost analysis and LCOE for the deep closed-loop geothermal system.

Couples a well-cost model to the thermal model in ground_loop_model.py to
answer: what does it cost to drill the two 8-mile boreholes, and what does
the electricity they produce cost per MWh?

Well-cost basis
---------------
Drilling cost grows super-linearly with depth (each extra metre is drilled
through a smaller bit, with longer trip times, more casing strings, and
higher temperature). The anchor is the widely used geothermal well-cost
correlation of Lukawski et al. (2014, J. Petroleum Sci. Eng.):

    C[MM 2009$] = 1.72e-7 * D^2 + 2.3e-3 * D - 0.62      (D in metres)

inflated to 2026$ (factor 1.40, IHS/BLS drilling cost indices). That curve
is fit to wells <= ~6 km; an 8-mile (12.9 km) hole is deeper than any
production well ever drilled, so extrapolation risk is handled with three
explicit scenarios instead of false precision:

  * OPTIMISTIC  (1.0x): geothermal-industry drilling economics hold all the
    way to 12.9 km (rapid-learning assumption, e.g. FORGE/Fervo-style gains).
  * BASE        (3.0x): engineering premium for ultra-deep - extra casing
    strings, exponential trip time, high-temperature tools and mud cooling.
  * PESSIMISTIC (14.5x): anchored to the actual cost of the KTB borehole
    (9.1 km, Germany, ~$350M spent 1987-94 ~= $700M in 2026$), i.e.
    research-well economics. (Kola SG-3, 12.26 km, took 19 years.)

Other capital: downhole pipe (bare steel down leg, vacuum-insulated tubing
up leg), the bottom hole-intersection ("connector"), the steam surface
plant, engineering and contingency.

LCOE: 30-year life, 7% real discount rate, 95% availability, yearly energy
from the thermal model including rock depletion, discounted-cash-flow LCOE.

Run:  python3 drilling_cost_model.py          (8-mile report + depth sweep)
      python3 drilling_cost_model.py --depth-miles 5
"""

import argparse
import math
import os

import numpy as np

from ground_loop_model import MILE, YEAR, Config, run_case, sweep_flow

# ---------------------------------------------------------------------------
# Cost assumptions (2026 USD)
# ---------------------------------------------------------------------------
INFLATION_2009_2026 = 1.40

DRILL_SCENARIOS = {
    "optimistic":  {"mult": 1.0,  "label": "Optimistic (geothermal learning curve)"},
    "base":        {"mult": 3.0,  "label": "Base (ultra-deep engineering premium)"},
    "pessimistic": {"mult": 14.5, "label": "Pessimistic (KTB research-well actuals)"},
}

# Reference wells for the cost-vs-depth chart (2026$ where known);
# last tuple element is the label offset in points for the plot
REFERENCE_WELLS = [
    ("Typical onshore oil/gas", 3000, 8e6, (7, -3)),
    ("Deep geothermal production", 5000, 25e6, (7, -3)),
    ("IDDP-2 Iceland", 4659, 25e6, (-14, -16)),
    ("KTB Germany (research)", 9101, 700e6, (7, -3)),
]

PIPE_COST_DOWN = 250.0      # $/m installed, bare high-temp steel casing/pipe
PIPE_COST_UP_VIT = 650.0    # $/m installed, vacuum-insulated tubing
CONNECTOR_COST = 15e6       # $ bottom-hole intersection (magnetic ranging)
PLANT_COST_PER_KW = 3500.0  # $/kW-e small saturated-steam plant, installed
PLANT_COST_FLOOR = 1.5e6    # $ minimum surface plant / balance of plant
ENGINEERING_FRac = 0.12     # owner's costs + engineering, on direct capital
CONTINGENCY_FRAC = 0.25     # on wells + downhole only (the risky part)

OM_WELL_FRAC = 0.005        # /yr of well capital
OM_PLANT_FRAC = 0.025       # /yr of plant capital
OM_FIXED = 250e3            # $/yr site fixed

DISCOUNT_RATE = 0.07        # real
LIFETIME_YR = 30
AVAILABILITY = 0.95

# LCOE benchmarks for context ($/MWh, 2026-ish)
BENCHMARKS = [("Utility solar PV", 40), ("Onshore wind", 45),
              ("Conventional geothermal (flash)", 80), ("New nuclear", 110)]


def lukawski_well_cost(depth_m: float) -> float:
    """Single-well drilling cost, 2026$, Lukawski et al. (2014) correlation."""
    mm2009 = 1.72e-7 * depth_m ** 2 + 2.3e-3 * depth_m - 0.62
    return max(mm2009, 0.1) * 1e6 * INFLATION_2009_2026


def drilling_cost(depth_m: float, scenario: str) -> float:
    """One borehole to depth_m under the given cost scenario, 2026$."""
    return lukawski_well_cost(depth_m) * DRILL_SCENARIOS[scenario]["mult"]


# ---------------------------------------------------------------------------
# Capital and O&M for the whole system
# ---------------------------------------------------------------------------
def capex_breakdown(depth_m: float, net_kw: float, scenario: str) -> dict:
    wells = 2 * drilling_cost(depth_m, scenario)
    pipe = depth_m * (PIPE_COST_DOWN + PIPE_COST_UP_VIT)
    connector = CONNECTOR_COST
    plant = max(PLANT_COST_FLOOR, PLANT_COST_PER_KW * max(net_kw, 0.0))
    direct = wells + pipe + connector + plant
    engineering = ENGINEERING_FRac * direct
    contingency = CONTINGENCY_FRAC * (wells + pipe + connector)
    return {
        "Drilling (2 wells)": wells,
        "Downhole pipe & VIT": pipe,
        "Bottom connection": connector,
        "Surface steam plant": plant,
        "Engineering & owner's": engineering,
        "Contingency": contingency,
        "TOTAL": direct + engineering + contingency,
    }


def annual_om(capex: dict) -> float:
    wells_like = (capex["Drilling (2 wells)"] + capex["Downhole pipe & VIT"]
                  + capex["Bottom connection"])
    return (OM_WELL_FRAC * wells_like
            + OM_PLANT_FRAC * capex["Surface steam plant"] + OM_FIXED)


# ---------------------------------------------------------------------------
# Energy production over the project life (with rock depletion)
# ---------------------------------------------------------------------------
def optimum_flow(cfg: Config) -> float:
    sw = sweep_flow(cfg, np.linspace(1, 60, 60), 10 * YEAR)
    return float(sw[np.argmax(sw[:, 3]), 0])


def yearly_energy_mwh(cfg: Config, mdot: float) -> np.ndarray:
    """Net MWh generated in each project year (evaluated at mid-year)."""
    out = np.zeros(LIFETIME_YR)
    for y in range(LIFETIME_YR):
        _, plant = run_case(cfg, mdot, (y + 0.5) * YEAR)
        out[y] = max(plant.w_net, 0.0) / 1e6 * 8766 * AVAILABILITY
    return out


def lcoe(capex_total: float, om_per_yr: float, energy_mwh: np.ndarray) -> float:
    """Discounted-cash-flow LCOE in $/MWh."""
    disc = 1.0 / (1.0 + DISCOUNT_RATE) ** np.arange(1, LIFETIME_YR + 1)
    pv_energy = float(np.sum(energy_mwh * disc))
    pv_cost = capex_total + om_per_yr * float(np.sum(disc))
    return pv_cost / pv_energy if pv_energy > 0 else float("inf")


def analyze_depth(depth_m: float, gradient: float = 0.028):
    """Full techno-economic result for one loop depth."""
    cfg = Config(depth=depth_m, geo_gradient=gradient, n_segments=200)
    mdot = optimum_flow(cfg)
    loop, plant = run_case(cfg, mdot, 10 * YEAR)
    energy = yearly_energy_mwh(cfg, mdot)
    net_kw = plant.w_net / 1e3
    results = {}
    for sc in DRILL_SCENARIOS:
        cap = capex_breakdown(depth_m, net_kw, sc)
        results[sc] = {
            "capex": cap,
            "om": annual_om(cap),
            "lcoe": lcoe(cap["TOTAL"], annual_om(cap), energy),
        }
    return {
        "cfg": cfg, "mdot": mdot, "loop": loop, "plant": plant,
        "energy": energy, "scenarios": results,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def money(x: float) -> str:
    if x >= 1e9:
        return f"${x/1e9:,.2f}B"
    if x >= 1e6:
        return f"${x/1e6:,.1f}M"
    return f"${x/1e3:,.0f}k"


def print_report(depth_m: float, r: dict):
    w = 66
    plant = r["plant"]
    print("=" * w)
    print(f"DRILLING COST & LCOE - closed loop at {depth_m/MILE:.1f} miles "
          f"({depth_m/1000:.1f} km)")
    print("=" * w)
    print(f"Net electric power (10 yr)  : {plant.w_net/1e6:7.2f} MWe "
          f"at optimal flow {r['mdot']:.0f} kg/s")
    e = r["energy"]
    print(f"Energy, year 1 / year 30    : {e[0]:,.0f} / {e[-1]:,.0f} MWh")
    print(f"Lifetime energy (30 yr)     : {e.sum()/1e3:,.1f} GWh")
    print("-" * w)
    print(f"Single-well drilling cost (2026$, {depth_m/1000:.1f} km):")
    for sc, d in DRILL_SCENARIOS.items():
        print(f"  {d['label']:<44}: {money(drilling_cost(depth_m, sc))}")
    print("-" * w)
    base = r["scenarios"]["base"]["capex"]
    print("Capital breakdown (BASE drilling scenario):")
    for k, v in base.items():
        if k != "TOTAL":
            print(f"  {k:<28}: {money(v):>10}  "
                  f"({v/base['TOTAL']*100:4.1f} %)")
    per_w = (f"   = ${base['TOTAL']/plant.w_net:,.0f}/W-e"
             if plant.w_net > 0 else "")
    print(f"  {'TOTAL CAPEX':<28}: {money(base['TOTAL']):>10}{per_w}")
    print("-" * w)
    print("Levelized cost of electricity (7% real, 30 yr, 95% avail.):")
    for sc, d in DRILL_SCENARIOS.items():
        v = r["scenarios"][sc]["lcoe"]
        print(f"  {d['label']:<44}: "
              f"{'$'+format(v, ',.0f')+'/MWh' if math.isfinite(v) else 'n/a'}")
    print("-" * w)
    print("For context:")
    for name, v in BENCHMARKS:
        print(f"  {name:<44}: ${v}/MWh")
    print("-" * w)
    # Break-even: what total capex hits conventional-geothermal LCOE?
    target = 80.0  # $/MWh
    disc = 1.0 / (1.0 + DISCOUNT_RATE) ** np.arange(1, LIFETIME_YR + 1)
    pv_e = float(np.sum(r["energy"] * disc))
    # O&M consistent with a break-even world: plant + fixed, no well fraction
    om = OM_PLANT_FRAC * r["scenarios"]["base"]["capex"]["Surface steam plant"] \
        + OM_FIXED
    cap_max = target * pv_e - om * float(np.sum(disc))
    print(f"Break-even at ${target:.0f}/MWh (competitive geothermal):")
    print(f"  Max affordable TOTAL capex  : {money(max(cap_max, 0))}")
    print(f"  -> implied budget per well  : {money(max(cap_max, 0) / 2)} "
          f"(vs {money(drilling_cost(depth_m, 'optimistic'))} optimistic)")
    print("=" * w)


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
def make_plots(outdir: str, depth_focus_m: float, gradient: float):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)
    colors = {"optimistic": "#1baf7a", "base": "#2a78d6",
              "pessimistic": "#e34948"}

    # 1. Well cost vs depth ---------------------------------------------------
    d = np.linspace(1000, 14000, 200)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for sc, meta in DRILL_SCENARIOS.items():
        ax.semilogy(d / 1000, [drilling_cost(x, sc) / 1e6 for x in d],
                    color=colors[sc], lw=2, label=meta["label"])
    for name, dm, cost, off in REFERENCE_WELLS:
        ax.plot(dm / 1000, cost / 1e6, "o", color="#0b0b0b", ms=5)
        ax.annotate(name, (dm / 1000, cost / 1e6),
                    textcoords="offset points", xytext=off, fontsize=8,
                    ha="left" if off[0] > 0 else "right")
    ax.axvline(depth_focus_m / 1000, color="gray", ls=":", lw=1)
    ax.annotate("8-mile loop", (depth_focus_m / 1000, 2),
                textcoords="offset points", xytext=(-60, 0), fontsize=9)
    ax.set_xlabel("Well depth (km)")
    ax.set_ylabel("Cost per well (million 2026$)")
    ax.set_title("Drilling cost vs depth - scenarios and reference wells")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "well_cost_vs_depth.png"), dpi=130)
    plt.close(fig)

    # 2 & 3. Depth sweep: power and LCOE -------------------------------------
    depths_mi = np.arange(2.0, 10.01, 0.5)
    lcoes = {sc: [] for sc in DRILL_SCENARIOS}
    powers, capexs = [], []
    for dm in depths_mi:
        r = analyze_depth(dm * MILE, gradient)
        powers.append(max(r["plant"].w_net, 0) / 1e6)
        capexs.append(r["scenarios"]["base"]["capex"]["TOTAL"] / 1e6)
        for sc in DRILL_SCENARIOS:
            lcoes[sc].append(r["scenarios"][sc]["lcoe"])

    fig, ax = plt.subplots(figsize=(8, 5.5))
    for sc, meta in DRILL_SCENARIOS.items():
        ax.semilogy(depths_mi, lcoes[sc], color=colors[sc], lw=2,
                    label=meta["label"])
        i = int(np.argmin(lcoes[sc]))
        ax.plot(depths_mi[i], lcoes[sc][i], "o", color=colors[sc], ms=6)
    for name, v in BENCHMARKS[1:3]:
        ax.axhline(v, color="#898781", lw=1, ls="--")
        ax.annotate(f"{name} (~${v})", (depths_mi[0], v),
                    textcoords="offset points", xytext=(2, 4), fontsize=8,
                    color="#52514e")
    ax.set_xlabel("Loop depth (miles)")
    ax.set_ylabel("LCOE ($/MWh, log scale)")
    ax.set_title("Levelized cost of electricity vs loop depth\n"
                 "(dots mark each scenario's cost-optimal depth)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "lcoe_vs_depth.png"), dpi=130)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(depths_mi, powers, color="#2a78d6", lw=2)
    ax1.set_xlabel("Loop depth (miles)")
    ax1.set_ylabel("Net electric power at 10 yr (MWe)", color="#2a78d6")
    ax1.tick_params(axis="y", labelcolor="#2a78d6")
    ax1.grid(alpha=0.3)
    ax1.set_title("Why LCOE has an optimum: power grows ~linearly,\n"
                  "drilling cost grows super-linearly with depth")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "power_vs_depth.png"), dpi=130)
    plt.close(fig)

    return depths_mi, lcoes


def main():
    p = argparse.ArgumentParser(description="Drilling cost & LCOE analysis")
    p.add_argument("--depth-miles", type=float, default=8.0)
    p.add_argument("--gradient", type=float, default=28.0,
                   help="geothermal gradient C/km")
    p.add_argument("--no-plots", action="store_true")
    args = p.parse_args()

    depth_m = args.depth_miles * MILE
    grad = args.gradient / 1000.0

    r = analyze_depth(depth_m, grad)
    print_report(depth_m, r)

    if not args.no_plots:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "results")
        print("\nRunning depth sweep for plots (2-10 miles)...")
        depths_mi, lcoes = make_plots(outdir, depth_m, grad)
        for sc, meta in DRILL_SCENARIOS.items():
            i = int(np.argmin(lcoes[sc]))
            print(f"  {meta['label']:<44}: LCOE-optimal depth "
                  f"{depths_mi[i]:.1f} mi -> ${lcoes[sc][i]:,.0f}/MWh")
        print(f"\nPlots written to {outdir}/")


if __name__ == "__main__":
    main()
