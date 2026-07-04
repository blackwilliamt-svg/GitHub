#!/usr/bin/env python3
"""
Deep closed-loop geothermal ground heat-transfer model.

System modeled
--------------
A closed loop of 8-inch steel pipe reaching 8 miles (12.87 km) underground:

  * DOWN leg  - bare (uninsulated) steel pipe. Cold working fluid descends and
                absorbs heat from progressively hotter rock.
  * UP leg    - very well insulated (vacuum-insulated tubing) so the hot fluid
                keeps its heat on the way back to the surface.
  * SURFACE   - a heat exchanger boils water; the steam drives a Rankine-cycle
                turbine. Cooled loop fluid is re-injected into the down leg.

Physics
-------
* Ground temperature increases linearly with depth (geothermal gradient).
* Rock-to-borehole heat flow uses the transient infinite line-source solution,
  so output correctly declines as the rock around the borehole is depleted:
      R_ground(t) = [ln(4*alpha*t / r_b^2) - gamma] / (4*pi*k_rock)
* Radial resistances in series: rock, steel wall, insulation (up leg only),
  and internal forced convection (Dittus-Boelter).
* The fluid temperature is marched along each leg with the exact exponential
  segment solution  T_out = T_g + (T_in - T_g) * exp(-dz / tau),
  tau = m_dot * cp * R_total  (thermal relaxation length).
* Circulation pressure: Darcy friction (Haaland) minus the thermosiphon assist
  from the density difference between the cold down-column and hot up-column.
* Surface plant: saturated-steam Rankine cycle computed from an embedded steam
  table (pinch-limited boiler temperature, isentropic turbine with wet-steam
  correction handled by a fixed isentropic efficiency, condenser at 40 C).

Simplifying assumptions (documented, not hidden)
------------------------------------------------
* Loop fluid is treated as pressurized liquid water with constant properties.
  (At 12.9 km the hydrostatic pressure ~126 MPa keeps it liquid/supercritical;
  constant-property liquid is a reasonable first-order model.)
* The two legs are assumed far enough apart that they do not thermally
  interfere with each other through the rock.
* Axial conduction in fluid/pipe and compression heating are neglected.
* The boiler pinch analysis is reduced to fixed hot-end and cold-end
  temperature approaches.

Run:  python3 ground_loop_model.py            (full study: sweep + transient)
      python3 ground_loop_model.py --mdot 40  (single case at 40 kg/s)
"""

import argparse
import math
import os
from dataclasses import dataclass, field

import numpy as np

MILE = 1609.344          # m
INCH = 0.0254            # m
YEAR = 365.25 * 24 * 3600  # s
EULER_GAMMA = 0.5772156649


# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
@dataclass
class Config:
    # Geometry ---------------------------------------------------------------
    depth: float = 8 * MILE              # loop depth [m]
    pipe_id: float = 8 * INCH            # pipe inner diameter [m] (8" bore)
    wall_thickness: float = 0.00818      # 8" sch-40 steel wall [m]
    insulation_thickness: float = 0.05   # up-leg insulation [m]

    # Materials ---------------------------------------------------------------
    k_steel: float = 45.0                # W/m-K
    k_insulation: float = 0.02           # W/m-K (vacuum-insulated tubing)
    pipe_roughness: float = 4.5e-5       # m (commercial steel)

    # Rock -------------------------------------------------------------------
    k_rock: float = 3.0                  # W/m-K
    rho_rock: float = 2700.0             # kg/m^3
    cp_rock: float = 900.0               # J/kg-K
    t_surface: float = 15.0              # C, mean surface temperature
    geo_gradient: float = 0.028          # K/m (28 C/km typical continental)

    # Working fluid (pressurized water, constant properties) ------------------
    rho_f: float = 1000.0                # kg/m^3
    cp_f: float = 4200.0                 # J/kg-K
    k_f: float = 0.65                    # W/m-K
    mu_f: float = 3.0e-4                 # Pa-s (hot water average)
    beta_f: float = 5.0e-4               # 1/K volumetric expansion (avg)

    # Operation ----------------------------------------------------------------
    mdot: float = 40.0                   # loop mass flow [kg/s]
    t_operate: float = 10 * YEAR         # time since startup [s]
    n_segments: int = 800

    # Surface plant ------------------------------------------------------------
    t_condenser: float = 40.0            # C
    dt_pinch_hot: float = 15.0           # boiler approach at hot end [K]
    dt_pinch_cold: float = 10.0          # loop-fluid exit approach over feed [K]
    t_boiler_max: float = 340.0          # C, subcritical steam cap
    eta_turbine_is: float = 0.80         # isentropic (wet steam)
    eta_generator: float = 0.97
    eta_pump: float = 0.75

    @property
    def r_inner(self) -> float:
        return self.pipe_id / 2

    @property
    def r_outer(self) -> float:
        return self.r_inner + self.wall_thickness

    @property
    def flow_area(self) -> float:
        return math.pi * self.r_inner ** 2

    @property
    def alpha_rock(self) -> float:
        return self.k_rock / (self.rho_rock * self.cp_rock)

    @property
    def t_inject(self) -> float:
        """Loop fluid re-injection temperature set by the boiler cold end."""
        return self.t_condenser + self.dt_pinch_cold

    def ground_temp(self, z):
        """Undisturbed rock temperature at depth z [m]."""
        return self.t_surface + self.geo_gradient * z


# ----------------------------------------------------------------------------
# Radial thermal resistances (per metre of pipe), K-m/W
# ----------------------------------------------------------------------------
def convection_resistance(cfg: Config, mdot: float) -> float:
    """Internal forced convection, Dittus-Boelter."""
    v = mdot / (cfg.rho_f * cfg.flow_area)
    re = cfg.rho_f * v * cfg.pipe_id / cfg.mu_f
    pr = cfg.cp_f * cfg.mu_f / cfg.k_f
    if re > 4000:
        nu = 0.023 * re ** 0.8 * pr ** 0.4
    else:  # laminar fallback
        nu = 4.36
    h = nu * cfg.k_f / cfg.pipe_id
    return 1.0 / (2 * math.pi * cfg.r_inner * h)


def wall_resistance(cfg: Config) -> float:
    return math.log(cfg.r_outer / cfg.r_inner) / (2 * math.pi * cfg.k_steel)


def insulation_resistance(cfg: Config) -> float:
    r_ins = cfg.r_outer + cfg.insulation_thickness
    return math.log(r_ins / cfg.r_outer) / (2 * math.pi * cfg.k_insulation)


def ground_resistance(cfg: Config, r_borehole: float, t: float) -> float:
    """Transient infinite line-source resistance of the rock at elapsed time t."""
    fo = 4 * cfg.alpha_rock * max(t, 3600.0) / r_borehole ** 2
    fo = max(fo, math.e)  # keep the log-approximation positive at tiny times
    return (math.log(fo) - EULER_GAMMA) / (4 * math.pi * cfg.k_rock)


# ----------------------------------------------------------------------------
# Downhole loop solver
# ----------------------------------------------------------------------------
@dataclass
class LoopResult:
    z: np.ndarray                 # depth grid [m]
    t_down: np.ndarray            # fluid temperature descending [C]
    t_up: np.ndarray              # fluid temperature ascending [C]
    t_ground: np.ndarray          # undisturbed rock temperature [C]
    t_bottom: float               # fluid temp at 8 miles [C]
    t_top: float                  # fluid temp back at surface [C]
    q_down: float                 # heat absorbed on down leg [W]
    q_up: float                   # net heat gained(+)/lost(-) on up leg [W]
    pump_power: float             # circulation pump electrical power [W]
    dp_friction: float            # friction pressure drop, full loop [Pa]
    dp_thermosiphon: float        # buoyancy assist [Pa]
    r_down: float                 # total radial resistance, down leg [K-m/W]
    r_up: float                   # total radial resistance, up leg [K-m/W]


def march_leg(cfg: Config, t_in: float, z: np.ndarray, t_ground: np.ndarray,
              r_total: float, mdot: float, downward: bool):
    """Exact exponential march of fluid temperature along one leg.

    Returns the temperature profile ordered by the z grid and the total heat
    absorbed (positive = into the fluid) in watts.
    """
    tau = mdot * cfg.cp_f * r_total  # thermal relaxation length [m]
    n = len(z)
    t = np.empty(n)
    order = range(n) if downward else range(n - 1, -1, -1)
    prev = None
    q_total = 0.0
    t_f = t_in
    for i in order:
        if prev is None:
            t[i] = t_f
        else:
            dz = abs(z[i] - z[prev])
            tg_mid = 0.5 * (t_ground[i] + t_ground[prev])
            t_new = tg_mid + (t_f - tg_mid) * math.exp(-dz / tau)
            q_total += mdot * cfg.cp_f * (t_new - t_f)
            t_f = t_new
            t[i] = t_f
        prev = i
    return t, q_total


def friction_factor(re: float, rel_rough: float) -> float:
    """Haaland explicit approximation to Colebrook."""
    if re < 2300:
        return 64.0 / max(re, 1.0)
    return (-1.8 * math.log10((rel_rough / 3.7) ** 1.11 + 6.9 / re)) ** -2


def solve_loop(cfg: Config, mdot: float = None, t_operate: float = None) -> LoopResult:
    mdot = cfg.mdot if mdot is None else mdot
    t_op = cfg.t_operate if t_operate is None else t_operate

    z = np.linspace(0.0, cfg.depth, cfg.n_segments + 1)
    t_ground = cfg.ground_temp(z)

    r_conv = convection_resistance(cfg, mdot)
    r_wall = wall_resistance(cfg)
    r_ins = insulation_resistance(cfg)
    r_bore_up = cfg.r_outer + cfg.insulation_thickness

    r_down = r_conv + r_wall + ground_resistance(cfg, cfg.r_outer, t_op)
    r_up = r_conv + r_wall + r_ins + ground_resistance(cfg, r_bore_up, t_op)

    # Down leg: injected fluid descends through hotter and hotter rock.
    t_down, q_down = march_leg(cfg, cfg.t_inject, z, t_ground, r_down, mdot,
                               downward=True)
    # Up leg: starts at the bottom temperature, insulated on the way up.
    t_up, q_up = march_leg(cfg, t_down[-1], z, t_ground, r_up, mdot,
                           downward=False)

    # Circulation pressure balance -------------------------------------------
    v = mdot / (cfg.rho_f * cfg.flow_area)
    re = cfg.rho_f * v * cfg.pipe_id / cfg.mu_f
    f = friction_factor(re, cfg.pipe_roughness / cfg.pipe_id)
    length_total = 2 * cfg.depth
    dp_fric = f * length_total / cfg.pipe_id * 0.5 * cfg.rho_f * v ** 2

    # Thermosiphon: the cold down-column is denser than the hot up-column,
    # which pushes the flow around the loop "for free".
    dt_cols = np.trapezoid(t_up - t_down, z)  # K-m
    dp_buoy = cfg.rho_f * cfg.beta_f * 9.81 * dt_cols

    dp_net = max(0.0, dp_fric - dp_buoy)
    pump_power = dp_net * mdot / (cfg.rho_f * cfg.eta_pump)

    return LoopResult(z=z, t_down=t_down, t_up=t_up, t_ground=t_ground,
                      t_bottom=float(t_down[-1]), t_top=float(t_up[0]),
                      q_down=q_down, q_up=q_up, pump_power=pump_power,
                      dp_friction=dp_fric, dp_thermosiphon=dp_buoy,
                      r_down=r_down, r_up=r_up)


# ----------------------------------------------------------------------------
# Surface plant: boiler + saturated-steam Rankine cycle
# ----------------------------------------------------------------------------
# Saturated water/steam table: T [C], P_sat [bar], h_f, h_fg [kJ/kg], s_f, s_fg
_STEAM = np.array([
    #  T      P        h_f     h_fg     s_f     s_fg
    [ 40.0,  0.0738,  167.5, 2406.0, 0.5724, 7.6845],
    [ 60.0,  0.1994,  251.2, 2358.4, 0.8312, 7.0774],
    [ 80.0,  0.4739,  334.9, 2308.8, 1.0753, 6.5359],
    [100.0,  1.0140,  419.1, 2256.4, 1.3069, 6.0480],
    [120.0,  1.9870,  503.8, 2202.1, 1.5276, 5.6020],
    [150.0,  4.7620,  632.3, 2113.7, 1.8420, 4.9960],
    [180.0, 10.0300,  763.1, 2014.5, 2.1396, 4.4448],
    [200.0, 15.5500,  852.4, 1939.7, 2.3308, 4.0997],
    [220.0, 23.2000,  943.6, 1857.4, 2.5178, 3.7683],
    [250.0, 39.7600, 1085.8, 1715.2, 2.7935, 3.2802],
    [280.0, 64.1700, 1236.7, 1543.2, 3.0680, 2.7903],
    [300.0, 85.8800, 1345.0, 1404.6, 3.2552, 2.4507],
    [320.0, 112.900, 1462.2, 1238.5, 3.4494, 2.0882],
    [340.0, 146.000, 1594.5, 1027.3, 3.6601, 1.6763],
])


def sat_props(t_c: float):
    """Interpolated saturation properties at temperature t_c [C]."""
    t = np.clip(t_c, _STEAM[0, 0], _STEAM[-1, 0])
    p = math.exp(np.interp(t, _STEAM[:, 0], np.log(_STEAM[:, 1])))
    h_f, h_fg, s_f, s_fg = (np.interp(t, _STEAM[:, 0], _STEAM[:, k])
                            for k in (2, 3, 4, 5))
    return dict(p_bar=p, h_f=h_f, h_fg=h_fg, s_f=s_f, s_fg=s_fg)


@dataclass
class PlantResult:
    q_thermal: float          # heat delivered to boiler [W]
    t_boiler: float           # steam saturation temperature [C]
    p_boiler_bar: float       # steam pressure [bar]
    mdot_steam: float         # steam production [kg/s]
    w_turbine: float          # gross turbine shaft power [W]
    w_net: float              # net electric power after pumps [W]
    eta_cycle: float          # W_net / Q_thermal
    steam_quality_exit: float # turbine exhaust quality


def run_plant(cfg: Config, loop: LoopResult, mdot: float) -> PlantResult:
    q_thermal = max(0.0, mdot * cfg.cp_f * (loop.t_top - cfg.t_inject))

    t_boil = min(loop.t_top - cfg.dt_pinch_hot, cfg.t_boiler_max)
    if q_thermal <= 0 or t_boil <= cfg.t_condenser + 5.0:
        return PlantResult(q_thermal, t_boil, 0.0, 0.0, 0.0,
                           -loop.pump_power, 0.0, 0.0)

    hot = sat_props(t_boil)
    cold = sat_props(cfg.t_condenser)

    # Steam raised: feedwater (condensate at T_cond) -> saturated vapor.
    h1 = hot["h_f"] + hot["h_fg"]                       # kJ/kg
    h_feed = cold["h_f"]
    mdot_steam = q_thermal / ((h1 - h_feed) * 1e3)

    # Isentropic expansion to condenser pressure (wet exhaust).
    s1 = hot["s_f"] + hot["s_fg"]
    x2s = (s1 - cold["s_f"]) / cold["s_fg"]
    h2s = cold["h_f"] + x2s * cold["h_fg"]
    h2 = h1 - cfg.eta_turbine_is * (h1 - h2s)
    x2 = (h2 - cold["h_f"]) / cold["h_fg"]

    w_turb = mdot_steam * (h1 - h2) * 1e3 * cfg.eta_generator

    # Feed pump: v * dP / eta.
    dp_feed = (hot["p_bar"] - cold["p_bar"]) * 1e5
    w_feed = mdot_steam * 0.001 * dp_feed / cfg.eta_pump

    w_net = w_turb - w_feed - loop.pump_power
    eta = w_net / q_thermal if q_thermal > 0 else 0.0
    return PlantResult(q_thermal, t_boil, hot["p_bar"], mdot_steam,
                       w_turb, w_net, eta, x2)


# ----------------------------------------------------------------------------
# Studies
# ----------------------------------------------------------------------------
def run_case(cfg: Config, mdot: float, t_operate: float):
    loop = solve_loop(cfg, mdot=mdot, t_operate=t_operate)
    plant = run_plant(cfg, loop, mdot)
    return loop, plant


def sweep_flow(cfg: Config, mdots: np.ndarray, t_operate: float):
    rows = []
    for m in mdots:
        loop, plant = run_case(cfg, m, t_operate)
        rows.append((m, loop.t_top, plant.q_thermal, plant.w_net,
                     loop.pump_power))
    return np.array(rows)


def sweep_time(cfg: Config, mdot: float, times: np.ndarray):
    rows = []
    for t in times:
        loop, plant = run_case(cfg, mdot, t)
        rows.append((t / YEAR, loop.t_top, plant.q_thermal, plant.w_net))
    return np.array(rows)


def print_report(cfg: Config, mdot: float, loop: LoopResult, plant: PlantResult,
                 t_operate: float):
    w = 62
    print("=" * w)
    print("DEEP CLOSED-LOOP GEOTHERMAL MODEL - 8 mile steel pipe loop")
    print("=" * w)
    print(f"Loop depth                : {cfg.depth/1000:8.2f} km  (8 miles)")
    print(f"Pipe bore                 : {cfg.pipe_id/INCH:8.1f} in")
    print(f"Rock temp at bottom       : {cfg.ground_temp(cfg.depth):8.1f} C "
          f"(gradient {cfg.geo_gradient*1000:.0f} C/km)")
    print(f"Operating time            : {t_operate/YEAR:8.1f} years")
    print(f"Loop mass flow            : {mdot:8.1f} kg/s")
    print("-" * w)
    print(f"Radial resistance, down   : {loop.r_down:8.3f} K-m/W (bare steel)")
    print(f"Radial resistance, up     : {loop.r_up:8.3f} K-m/W (insulated, "
          f"{loop.r_up/loop.r_down:.0f}x)")
    print(f"Injection temperature     : {cfg.t_inject:8.1f} C")
    print(f"Fluid temp at bottom      : {loop.t_bottom:8.1f} C")
    print(f"Fluid temp back at surface: {loop.t_top:8.1f} C")
    print(f"Heat gained, down leg     : {loop.q_down/1e6:8.2f} MW")
    print(f"Heat change, up leg       : {loop.q_up/1e6:8.2f} MW "
          f"({'gain' if loop.q_up >= 0 else 'loss'} - insulation working)")
    print(f"Friction pressure drop    : {loop.dp_friction/1e5:8.2f} bar")
    print(f"Thermosiphon assist       : {loop.dp_thermosiphon/1e5:8.2f} bar")
    print(f"Circulation pump power    : {loop.pump_power/1e3:8.1f} kW"
          + ("  (self-circulating!)" if loop.pump_power == 0 else ""))
    print("-" * w)
    print(f"Heat to boiler            : {plant.q_thermal/1e6:8.2f} MW-th")
    print(f"Boiler steam conditions   : {plant.t_boiler:8.1f} C at "
          f"{plant.p_boiler_bar:.1f} bar")
    print(f"Steam production          : {plant.mdot_steam:8.2f} kg/s")
    print(f"Turbine exhaust quality   : {plant.steam_quality_exit:8.3f}")
    print(f"Gross turbine power       : {plant.w_turbine/1e6:8.2f} MW-e")
    print(f"NET ELECTRIC POWER        : {plant.w_net/1e6:8.2f} MW-e")
    print(f"Cycle efficiency          : {plant.eta_cycle*100:8.1f} %")
    print("=" * w)


def make_plots(cfg: Config, outdir: str, mdot_opt: float):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(outdir, exist_ok=True)

    # 1. Temperature vs depth ---------------------------------------------
    loop, plant = run_case(cfg, mdot_opt, cfg.t_operate)
    fig, ax = plt.subplots(figsize=(7, 8))
    km = loop.z / 1000
    ax.plot(loop.t_ground, km, "k--", lw=1.2, label="Undisturbed rock")
    ax.plot(loop.t_down, km, color="#2166ac", lw=2,
            label="Down leg (bare steel)")
    ax.plot(loop.t_up, km, color="#b2182b", lw=2,
            label="Up leg (insulated)")
    ax.invert_yaxis()
    ax.set_xlabel("Temperature (°C)")
    ax.set_ylabel("Depth (km)")
    ax.set_title(f"Loop temperature profile\n"
                 f"{mdot_opt:.0f} kg/s after {cfg.t_operate/YEAR:.0f} years "
                 f"— net {plant.w_net/1e6:.1f} MWe")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "temperature_profile.png"), dpi=130)
    plt.close(fig)

    # 2. Power vs mass flow -------------------------------------------------
    mdots = np.linspace(2, 60, 59)
    sw = sweep_flow(cfg, mdots, cfg.t_operate)
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(sw[:, 0], sw[:, 2] / 1e6, color="#b2182b", lw=2,
             label="Thermal power to boiler")
    ax1.plot(sw[:, 0], sw[:, 3] / 1e6, color="#2166ac", lw=2,
             label="Net electric power")
    i_best = int(np.argmax(sw[:, 3]))
    ax1.axvline(sw[i_best, 0], color="gray", ls=":", lw=1)
    ax1.annotate(f"optimum ≈ {sw[i_best, 0]:.0f} kg/s",
                 (sw[i_best, 0], sw[i_best, 3] / 1e6),
                 textcoords="offset points", xytext=(8, 8))
    ax1.set_xlabel("Loop mass flow (kg/s)")
    ax1.set_ylabel("Power (MW)")
    ax1.set_title(f"Output vs circulation rate "
                  f"(after {cfg.t_operate/YEAR:.0f} years)")
    ax1.legend()
    ax1.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "power_vs_flow.png"), dpi=130)
    plt.close(fig)

    # 3. Power vs time (rock depletion) --------------------------------------
    times = np.geomspace(0.05 * YEAR, 30 * YEAR, 40)
    st = sweep_time(cfg, mdot_opt, times)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.semilogx(st[:, 0], st[:, 2] / 1e6, color="#b2182b", lw=2,
                label="Thermal power")
    ax.semilogx(st[:, 0], st[:, 3] / 1e6, color="#2166ac", lw=2,
                label="Net electric power")
    ax.set_xlabel("Years of operation")
    ax.set_ylabel("Power (MW)")
    ax.set_title(f"Long-term output at {mdot_opt:.0f} kg/s "
                 f"(rock depletion, line-source model)")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(outdir, "power_vs_time.png"), dpi=130)
    plt.close(fig)

    return sw[i_best, 0]


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--mdot", type=float, default=None,
                   help="loop mass flow kg/s (default: find optimum)")
    p.add_argument("--years", type=float, default=10.0,
                   help="operating time in years (default 10)")
    p.add_argument("--gradient", type=float, default=28.0,
                   help="geothermal gradient C/km (default 28)")
    p.add_argument("--no-plots", action="store_true")
    args = p.parse_args()

    cfg = Config(geo_gradient=args.gradient / 1000.0,
                 t_operate=args.years * YEAR)

    if args.mdot is None:
        mdots = np.linspace(2, 60, 59)
        sw = sweep_flow(cfg, mdots, cfg.t_operate)
        mdot = float(sw[np.argmax(sw[:, 3]), 0])
        print(f"[flow sweep] optimum mass flow ≈ {mdot:.1f} kg/s "
              f"(maximizes net electric power)\n")
    else:
        mdot = args.mdot

    loop, plant = run_case(cfg, mdot, cfg.t_operate)
    print_report(cfg, mdot, loop, plant, cfg.t_operate)

    if not args.no_plots:
        outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "results")
        make_plots(cfg, outdir, mdot)
        print(f"\nPlots written to {outdir}/")


if __name__ == "__main__":
    main()
