# FLEX-Operation

## What It Does

FLEX-Operation models the hourly energy system dispatch of a single household over a full year (8,760 hours). Given a household's technology configuration — heating system, PV, battery storage, EV, thermal tanks — and the corresponding demand and weather inputs, it calculates how the system operates hour by hour, along with the resulting energy consumption and cost.

The model runs each scenario ID independently and produces separate result files per scenario.

## Ref vs. Opt: The Central Distinction

Every scenario is run in both modes (unless disabled), and the comparison between them is typically the core research output:

**Reference mode** (`dispatch_ref.py`) simulates a household with **no smart control**. The code follows two distinct execution paths depending on the heating system type:

* **Heat pump path** (`run_heatpump_ref`):
  * Space heating demand is computed via the RC thermal model; excess demand beyond HP capacity goes to the heating element.
  * PV surplus follows a fixed priority chain: load → battery → EV → DHW tank → grid feed-in.
  * DHW tank temperature is tracked iteratively; an HP power cap check ensures total HP electrical input stays within rated capacity.
* **Fuel boiler path** (`run_fuel_boiler_ref`):
  * Space heating and DHW are supplied by the fuel boiler (gas, oil, solids, or district heating).
  * Fuel consumption:

    $$\text{Fuel}_t = \frac{Q^{\text{boiler,heat}}_t + Q^{\text{boiler,DHW}}_t}{\eta_{\text{boiler}}}$$

    where $Q^{\text{boiler,heat}}_t$ and $Q^{\text{boiler,DHW}}_t$ are the thermal output for space heating and DHW [kWh], and $\eta_{\text{boiler}}$ is the boiler efficiency.
  * The electrical load only includes base loads, the heating element, and cooling.

In both paths: the EV charges immediately when it arrives home; the battery follows a charge-from-PV / discharge-to-load rule; there is no lookahead or price awareness.

**Optimization mode** (`dispatch_opt.py`) simulates a household with a **Smart Energy Management System (SEMS)**. A Pyomo LP is solved for the full year simultaneously:

* **Objective**: minimize total annual energy cost:

$$\min \sum_{t=1}^{8760} \Big( \text{Grid}_t \cdot \lambda^{\text{elec}}_t + \text{Fuel}_t \cdot \lambda^{\text{fuel}}_t - \text{Feed2Grid}_t \cdot \lambda^{\text{FiT}}_t + \varepsilon_t \Big)$$

where:

* $\text{Grid}_t$ — electricity purchased from the grid at hour $t$ [kWh]
* $\text{Fuel}_t$ — fuel consumed (gas, oil, etc.) at hour $t$ [kWh]
* $\text{Feed2Grid}_t$ — PV electricity fed back to the grid [kWh]
* $\lambda^{\text{elec}}_t$, $\lambda^{\text{fuel}}_t$, $\lambda^{\text{FiT}}_t$ — electricity price, fuel price, and feed-in tariff [€/kWh]
* $\varepsilon_t$ — tie-break penalty (see below)

The tie-break term adds tiny penalties on storage throughput and heating element use to prevent degenerate LP solutions:

$$\begin{aligned}
\varepsilon_t = \;&\epsilon_1 (\text{BatCharge}_t + \text{BatDischarge}_t) + \epsilon_2 (\text{EVCharge}_t + \text{EVDischarge}_t) \\
              +\;&\epsilon_3 (\text{Bat2EV}_t + \text{EV2Bat}_t) + \epsilon_4 \, Q^{\text{HE}}_t + \epsilon_5 \sum Q^{\text{tank}}_t
\end{aligned}$$

with $\epsilon_1 = 10^{-6}$, $\epsilon_2 = 9 \times 10^{-7}$, $\epsilon_3 = 7 \times 10^{-7}$, $\epsilon_4 = 5 \times 10^{-7}$, $\epsilon_5 = 3 \times 10^{-7}$. These values are small enough to never override energy cost decisions.

### Key LP Constraints

**Battery state of charge:**

$$\text{BatSoC}_t = \text{BatSoC}_{t-1} + \text{BatCharge}_t \cdot \eta^{\text{bat}}_c - \text{BatDischarge}_t \cdot (2 - \eta^{\text{bat}}_d)$$

where $\eta^{\text{bat}}_c$ and $\eta^{\text{bat}}_d$ are charge and discharge efficiencies, and $\text{BatSoC}_0 = 0$. The term $(2 - \eta^{\text{bat}}_d)$ is a linearized approximation of $1/\eta^{\text{bat}}_d$.

**EV state of charge:**

$$\text{EVSoC}_t = \text{EVSoC}_{t-1} + \text{EVCharge}_t \cdot \eta^{\text{ev}}_c - \frac{\text{EVDischarge}_t}{\eta^{\text{ev}}_d}$$

where $\eta^{\text{ev}}_c$ and $\eta^{\text{ev}}_d$ are EV charge and discharge efficiencies, and $\text{EVSoC}_0 = C_{\text{ev}}$ (EV battery starts fully charged). $\text{EVDischarge}_t$ includes driving demand, vehicle-to-home (V2H), and vehicle-to-battery flows.

**Electricity demand (load composition):**

$$\text{Load}_t = \text{BaseLoad}_t + E^{\text{HP,heat}}_t + \frac{Q^{\text{HE}}_t}{\eta_{\text{HE}}} + E^{\text{cool}}_t + E^{\text{HP,DHW}}_t$$

where $\text{BaseLoad}_t$ is the appliance demand, $E^{\text{HP,heat}}_t$ and $E^{\text{HP,DHW}}_t$ are heat pump electrical input for space heating and DHW, $Q^{\text{HE}}_t / \eta_{\text{HE}}$ is heating element electricity, and $E^{\text{cool}}_t$ is cooling electricity.

**Electricity supply (load balance):**

$$\text{Load}_t = \text{Grid2Load}_t + \text{PV2Load}_t + \text{Bat2Load}_t + \text{EV2Load}_t$$

**PV allocation:**

$$\text{PV}_t = \text{PV2Load}_t + \text{PV2Bat}_t + \text{PV2EV}_t + \text{PV2Grid}_t$$

**Thermal tank energy balance** (space heating tank; DHW tank follows the same structure):

$$Q^{\text{tank}}_t = Q^{\text{tank}}_{t-1} + Q^{\text{in}}_t - Q^{\text{out}}_t - U \cdot A \cdot \left( \frac{Q^{\text{tank}}_t}{M \cdot c_p} - T_{\text{surr}} \right)$$

where $Q^{\text{tank}}_t$ is the thermal energy stored [kJ], $Q^{\text{in}}_t$ and $Q^{\text{out}}_t$ are heat flows in/out, $U$ is the tank heat loss coefficient, $A$ is the tank surface area, $M$ is the water mass, $c_p$ is the specific heat of water, and $T_{\text{surr}}$ is the surrounding temperature [K]. The term $Q^{\text{tank}}_t / (M \cdot c_p)$ converts stored energy to absolute temperature.

Flexible devices (battery, EV, thermal tanks, heat pump) are scheduled optimally given these energy balance constraints, device capacity limits, and comfort bounds (room temperature ±3 °C, tank temperature min/max). The result represents the theoretical maximum value of full demand flexibility.

The difference in annual cost between Ref and Opt quantifies the economic value of SEMS. This can be computed from `OperationResult_RefYear` and `OperationResult_OptYear` (`TotalCost` column).

## Technology Components

Each component is a dataclass defined in `src/models/operation/components.py` and parameterized via its own input table:

| Component | Input table | Key parameters |
|---|---|---|
| `Building` | `_Component_Building` | Floor area ($A_f$), thermal conductances ($H_{op}$, $H_{tr,w}$, $H_{ve}$), mass/area factors, window areas by orientation, supply temperature, ventilation heat recovery |
| `Boiler` | `_Component_Boiler` | Type (heat pump / fuel boiler / district heating), Carnot efficiency factor, fuel boiler efficiency |
| `HeatingElement` | `_Component_HeatingElement` | Backup electric resistance heater power and efficiency |
| `SpaceHeatingTank` | `_Component_SpaceHeatingTank` | Size, thermal loss, start/min/max temperature |
| `HotWaterTank` | `_Component_HotWaterTank` | Size, thermal loss, start/min/max temperature |
| `SpaceCoolingTechnology` | `_Component_SpaceCoolingTechnology` | Cooling COP ($\eta_{\text{cool}}$) and rated power |
| `PV` | `_Component_PV` | Installed capacity (`size`), orientation |
| `Battery` | `_Component_Battery` | Capacity, charge/discharge efficiency and power limits |
| `Vehicle` | `_Component_Vehicle` | Battery capacity, consumption rate, charge/discharge efficiency, V2H capability (`charge_bidirectional`), driving profile IDs |
| `EnergyPrice` | `_Component_EnergyPrice` | IDs selecting which electricity, feed-in, and fuel price columns to use from the price time series table |
| `Behavior` | `_Component_Behavior` | Temperature setpoints (at-home / not-at-home), shading parameters, demand profile type ID |

All 11 component IDs in the scenario table are **required** — `NULL` / `NaN` values are not allowed and will cause a validation error. Instead, "technology not installed" is represented by pointing to a component row whose **key capacity parameter is zero**. For example, to model a household without PV, the scenario references a PV entry with `size = 0`; without a battery, it references a Battery entry with `capacity = 0`.

The model detects these zero-capacity entries via `ScenarioFlags` (in `opt_pyomo_config.py`) and responds by fixing the corresponding decision variables to zero and deactivating the related constraints. The flags are:

| Flag | Condition | Effect when False |
|---|---|---|
| `has_pv` | `pv.size > 0` | PV flow variables fixed to 0 |
| `has_battery` | `battery.capacity > 0` | Battery charge/discharge/SoC fixed to 0 |
| `has_ev` | `vehicle.capacity > 0` | All EV variables fixed to 0 |
| `has_cooling` | `space_cooling_technology.power > 0` | Cooling variables fixed to 0 |
| `has_heating_element` | `heating_element.power > 0` | Heating element variables fixed to 0 |
| `has_space_heating_tank` | `space_heating_tank.size > 0` | Tank variables fixed to 0, energy balance deactivated |
| `has_hot_water_tank` | `hot_water_tank.size > 0` | DHW tank variables fixed to 0, energy balance deactivated |

## The RC Thermal Model

Building thermal dynamics are modeled using a **5R1C simplified resistance-capacitance (RC) model** based on ISO 13790. The equations are implemented in `src/models/operation/rc_equations.py` and used in both Ref and Opt dispatch.

The model tracks two state variables: **thermal mass temperature** $T^m_t$ and **room air temperature** $T^{\text{room}}_t$.

**Thermal mass update** (ISO 13790 Eq. C.4):

$$T^m_t = \frac{T^m_{t-1} \left(\frac{C_m}{3600} - \frac{H_{tr,3} + H_{tr,em}}{2}\right) + \Phi_{m,tot}}{\frac{C_m}{3600} + \frac{H_{tr,3} + H_{tr,em}}{2}}$$

**Room air temperature** (ISO 13790 Eq. C.11):

$$T^{\text{room}}_t = \frac{H_{tr,is} \cdot T_s + H_{ve} \cdot T_{sup} + \Phi_{ia} + Q_{hc}}{H_{tr,is} + H_{ve}}$$

where:

* $C_m$ — building thermal mass capacity [J/K]
* $H_{tr,3}$, $H_{tr,em}$, $H_{tr,is}$, $H_{ve}$ — heat transfer coefficients for different thermal paths (transmission, exterior mass, interior surface, ventilation) [W/K]
* $\Phi_{m,tot}$ — total heat flow to the thermal mass, aggregated from solar gains ($Q_{\text{solar}}$), internal gains ($Q_i$), heating/cooling input ($Q_{hc}$), and outdoor temperature via thermal bridges (ISO 13790 Eq. C.5)
* $T_s$ — interior surface temperature, computed from $T^m$ and heat flows (ISO 13790 Eq. C.10)
* $T_{sup}$ — ventilation supply temperature [°C]
* $\Phi_{ia}$ — internal air heat gain [W]
* $Q_{hc}$ — net heating (+) or cooling (−) power delivered to the room [W]

In Opt mode, the thermal mass acts as an implicit thermal storage: the optimizer can pre-heat the building when electricity is cheap.

## Inputs

| Table | Content |
|---|---|
| `OperationScenario` | Main scenario table — one row per scenario, links all component IDs |
| `OperationScenario_Component_*` | Parameter tables for each technology (Battery, Boiler, Building, etc.) |
| `OperationScenario_Component_Behavior` | Behavior parameters: temperature setpoints, shading, demand profile type |
| `OperationScenario_Component_EnergyPrice` | Maps scenario to price column IDs in the price time series |
| `OperationScenario_EnergyPrice` | Hourly electricity, feed-in, and fuel price time series |
| `OperationScenario_RegionWeather` | Hourly outdoor temperature, solar irradiance, PV generation profiles |
| `OperationScenario_BehaviorProfile` | Hourly behavior profiles from FLEX-Behavior (appliance demand, hot water, occupancy) |
| `OperationScenario_DrivingProfile_*` | EV parking and driving distance profiles |

## Outputs

Results are written per scenario (suffix `_S{id}`) and per mode (Ref / Opt):

| Table | Resolution | Content |
|---|---|---|
| `OperationResult_RefHour_S{id}` / `OptHour_S{id}` | Hourly (8,760 rows) | 53 variables — see `result_registry.py` for the full list |
| `OperationResult_RefMonth_S{id}` / `OptMonth_S{id}` | Monthly (12 rows) | Summed energy flows |
| `OperationResult_RefYear_S{id}` / `OptYear_S{id}` | Annual (1 row) | Total energy and cost summary including `TotalCost` |

Hourly results are stored as parquet (default) or CSV. Monthly and annual results are CSV and are automatically merged across scenarios into a single file (e.g. `OperationResult_RefYear.csv`) after all scenarios complete.

The full output variable list is defined in `src/models/operation/result_registry.py`. Key variables include:

* **Thermal:** `T_Room`, `T_BuildingMass`, `Q_RoomHeating`, `Q_RoomCooling`, `Q_HeatingTank_in/out`, `Q_DHWTank_in/out`
* **Electrical:** `Grid`, `Load`, `Feed2Grid`, `PV2Load`, `PV2Bat`, `PV2Grid`, `PV2EV`
* **Storage:** `BatSoC`, `BatCharge`, `BatDischarge`, `EVSoC`, `EVCharge`, `EVDischarge`
* **Fuel:** `Fuel`, `FuelPrice`
* **COP:** `SpaceHeatingHourlyCOP`, `HotWaterHourlyCOP`, `CoolingHourlyCOP`

## Key Code Locations

| File | Role |
|---|---|
| `src/models/operation/main.py` | Entry point — `run_operation_model()`, `run_operation_model_parallel()` |
| `src/models/operation/scenario.py` | Loads all component parameters into the `OperationScenario` object |
| `src/models/operation/dispatch_ref.py` | Rule-based reference dispatch (HP path + fuel boiler path) |
| `src/models/operation/dispatch_opt.py` | LP optimization dispatch — calls Pyomo solver |
| `src/models/operation/physics_model.py` | Shared physical state computation (energy flows, COP, SoC updates) |
| `src/models/operation/opt_pyomo_structure.py` | Pyomo model definition: sets, variables, constraints, objective |
| `src/models/operation/opt_pyomo_config.py` | Populates Pyomo parameters from scenario data; activates/deactivates constraints |
| `src/models/operation/rc_equations.py` | Building thermal model equations (ISO 13790 5R1C) |
| `src/models/operation/components.py` | 11 component dataclasses |
| `src/models/operation/boiler.py` | Boiler type classification (HP vs. fuel) and normalization |
| `src/models/operation/solver.py` | Environment-variable-driven solver factory |
| `src/models/operation/result_registry.py` | Defines which variables are saved and how they are aggregated |

## How to Run

```bash
python -m projects.test_operation.main
```

Output is written to `projects/test_operation/output/`.
