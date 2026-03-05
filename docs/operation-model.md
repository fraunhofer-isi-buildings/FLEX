# FLEX-Operation

## What It Does

FLEX-Operation models the hourly energy system dispatch of a single household over a full year (8,760 hours). Given a household's technology configuration — heating system, PV, battery storage, EV, thermal tanks — and the corresponding demand and weather inputs, it calculates how the system operates hour by hour, along with the resulting energy consumption and cost.

The model runs each scenario ID independently and produces separate result files per scenario.

## Ref vs. Opt: The Central Distinction

Every scenario is run in both modes (unless disabled), and the comparison between them is typically the core research output:

**Reference mode** (`dispatch_ref.py`) simulates a household with **no smart control**. Devices operate by simple, reactive rules:
* The heat pump runs whenever space heating or hot water demand exceeds tank capacity.
* The EV charges immediately when it arrives home.
* The battery charges from PV surplus and discharges to cover load, following a basic priority order.
* There is no lookahead, no price awareness.

**Optimization mode** (`dispatch_opt.py`) simulates a household with a **Smart Energy Management System (SEMS)**. A Pyomo LP is solved for the full year simultaneously:
* **Objective**: minimize total annual energy cost:

$$\min \sum_{t=1}^{8760} \left( P^{\text{grid}}_t \cdot \lambda^{\text{elec}}_t \right) - \sum_{t=1}^{8760} \left( P^{\text{feed}}_t \cdot \lambda^{\text{FiT}}_t \right) + C_{\text{fuel}}$$
* Flexible devices (battery, EV, thermal tanks, heat pump) are scheduled optimally given energy balance constraints, device capacity limits, and comfort bounds (room temperature, tank temperature).
* The result represents the theoretical maximum value of full demand flexibility.

The difference in annual cost between Ref and Opt is the economic value of SEMS, which is reported in `OperationResult_EnergyCostChange`.

## Technology Components

Each component is a dataclass defined in `src/models/operation/components.py` and parameterized via its own input table:

| Component | Key parameters |
|---|---|
| `Building` | Floor area, thermal conductances (Hop, Htr_w, Hve), window areas by orientation, supply temperature |
| `Boiler` | Type (heat pump / fuel boiler / district heating), COP/efficiency |
| `HeatingElement` | Backup electric resistance heater power and efficiency |
| `SpaceHeatingTank` | Size, thermal loss, min/max temperature |
| `HotWaterTank` | Size, thermal loss, min/max temperature |
| `SpaceCoolingTechnology` | Cooling COP and rated power |
| `PV` | Installed capacity, orientation, hourly generation profile |
| `Battery` | Capacity, charge/discharge efficiency and power limits |
| `Vehicle` | Battery capacity, consumption rate, V2H capability, parking and driving profiles |

The presence or absence of each component is controlled by the scenario table — a `NULL` component ID means that technology is not installed.

## The RC Thermal Model

Building thermal dynamics are modeled using a **5R1C simplified resistance-capacitance (RC) model** based on ISO 13790. The equations are implemented in `src/models/operation/rc_equations.py` and used in both Ref and Opt dispatch.

The model tracks two temperatures: **room air temperature** (`T_Room`) and **thermal mass temperature** (`T_BuildingMass`). Solar gains, internal gains, ventilation heat recovery, and the heat pump output all enter as heat flows. In Opt mode, the thermal mass acts as an implicit thermal storage: the optimizer can pre-heat the building when electricity is cheap.

## Inputs

| Table | Content |
|---|---|
| `OperationScenario` | Main scenario table — one row per scenario, links all component IDs |
| `OperationScenario_Component_*` | Parameter tables for each technology (Battery, Boiler, Building, etc.) |
| `OperationScenario_EnergyPrice` | Hourly electricity, feed-in, and fuel price time series |
| `OperationScenario_RegionWeather` | Hourly outdoor temperature and solar irradiance |
| `OperationScenario_BehaviorProfile` | Hourly behavior profiles from FLEX-Behavior (optional) |
| `OperationScenario_DrivingProfile_*` | EV parking and driving distance profiles |

## Outputs

Results are written per scenario (suffix `_S{id}`) and per mode (Ref / Opt):

| Table | Resolution | Key variables |
|---|---|---|
| `OperationResult_RefHour_S{id}` / `OptHour_S{id}` | Hourly | `Grid`, `Load`, `Feed2Grid`, `PhotovoltaicProfile`, `BatSoC`, `BatCharge`, `BatDischarge`, `EVSoC`, `T_Room`, `Q_RoomHeating`, `Q_DHWTank`, ... (~40 variables) |
| `OperationResult_RefMonth_S{id}` / `OptMonth_S{id}` | Monthly | Summed energy flows |
| `OperationResult_RefYear_S{id}` / `OptYear_S{id}` | Annual | Total energy and cost summary per scenario |

The full list of output variables and their aggregation rules is defined in `src/models/operation/result_registry.py`.

## Key Code Locations

| File | Role |
|---|---|
| `src/models/operation/main.py` | Entry point — `run_operation_model()` |
| `src/models/operation/scenario.py` | Loads all component parameters into the `OperationScenario` object |
| `src/models/operation/dispatch_ref.py` | Rule-based reference dispatch logic |
| `src/models/operation/dispatch_opt.py` | LP optimization dispatch — calls Pyomo solver |
| `src/models/operation/physics_model.py` | Shared physical state computation (energy flows, SoC updates) |
| `src/models/operation/opt_pyomo_structure.py` | Pyomo model definition: sets, variables, constraints, objective |
| `src/models/operation/opt_pyomo_config.py` | Populates Pyomo parameters from scenario data |
| `src/models/operation/rc_equations.py` | Building thermal model equations |
| `src/models/operation/solver.py` | Solver configuration (defaults to Gurobi) |
| `src/models/operation/result_registry.py` | Defines which variables are saved and how they are aggregated |

## How to Run

```bash
python -m projects.test_operation.main
```

Output is written to `projects/test_operation/output/`.
