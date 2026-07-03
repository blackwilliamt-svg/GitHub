# Deep Closed-Loop Geothermal Ground Heat-Transfer Model

A physics model of an 8-mile-deep (12.87 km) closed loop of 8-inch steel pipe
that harvests geothermal heat and converts it to electricity with a
steam-turbine plant at the surface.

```
   surface heat exchanger (boiler) ──► steam ──► turbine ──► generator
        ▲ hot fluid          │ cooled fluid (re-injected at ~50 °C)
        │                    ▼
   ┌── UP LEG ──┐      ┌── DOWN LEG ──┐
   │ insulated  │      │  bare steel  │   8-inch bore steel pipe
   │ (VIT)      │      │ (heat pickup)│
   └─────┬──────┘      └──────┬───────┘
         └──────── bottom ────┘            8 miles down, rock ≈ 375 °C
```

## What the model captures

| Effect | Method |
|---|---|
| Ground temperature vs depth | Linear geothermal gradient (default 28 °C/km) |
| Rock-to-pipe heat flow & long-term depletion | Transient infinite line-source solution `R_g(t) = [ln(4αt/r²) − γ] / 4πk` |
| Pipe wall / insulation / fluid convection | Series radial resistances; Dittus–Boelter for internal convection |
| Fluid heating along the pipe | Exact exponential march per segment, `T_out = T_g + (T_in − T_g)·e^(−dz/τ)` with relaxation length `τ = ṁ·cp·R` |
| Circulation pressure | Darcy friction (Haaland) **minus thermosiphon buoyancy assist** from the cold-down / hot-up density difference |
| Surface plant | Saturated-steam Rankine cycle from an embedded steam table: pinch-limited boiler, isentropic turbine (η=0.80), 40 °C condenser |

The down leg is bare steel so it picks up heat over its full length; the up
leg is modeled as vacuum-insulated tubing (k ≈ 0.02 W/m·K), which raises its
radial resistance ~11× so the hot fluid arrives at the surface with almost no
loss.

## Running

```bash
pip install numpy matplotlib
python3 geothermal/ground_loop_model.py              # sweep flow, find optimum, plot
python3 geothermal/ground_loop_model.py --mdot 8     # single case
python3 geothermal/ground_loop_model.py --years 30 --gradient 32
```

## Headline results (defaults: 28 °C/km, 10 years of operation)

* Rock at 8 miles: **≈ 375 °C**
* Optimal circulation: **≈ 8 kg/s** — a real trade-off: more flow harvests
  more heat but returns it colder, which collapses the steam-cycle efficiency.
* Fluid returns to the surface at **≈ 183 °C**, raising ~1.7 kg/s of steam at
  ~7.5 bar.
* **≈ 4.5 MW thermal → ≈ 0.9 MW net electric** from a single loop.
* The loop is **fully self-circulating**: the thermosiphon head (~59 bar)
  dwarfs the friction drop (~0.7 bar), so no circulation pump power is needed
  (in practice the flow would be throttled to the optimum).
* Output declines slowly (logarithmically) over decades as the rock around
  the borehole depletes — see `results/power_vs_time.png`.

![Temperature profile](results/temperature_profile.png)
![Power vs flow](results/power_vs_flow.png)
![Power vs time](results/power_vs_time.png)

## Key limitations

* Loop fluid treated as constant-property pressurized liquid water (at
  12.9 km the ~126 MPa hydrostatic pressure keeps it dense; supercritical
  property variation is ignored).
* The two legs are assumed not to thermally interfere through the rock.
* Boiler pinch analysis reduced to fixed hot-end (15 K) and cold-end (10 K)
  approaches; single-pressure saturated cycle (no superheat/reheat).
* No drilling/materials feasibility judgment — 8 miles is roughly the depth
  of the deepest borehole ever drilled (Kola, 12.3 km), and 375 °C exceeds
  common casing/cement ratings. This is a heat-transfer model, not a
  drilling plan.

All physical parameters (gradient, rock properties, insulation, pinch
temperatures, efficiencies) are fields on `Config` in
`ground_loop_model.py` and can be changed in one place.
