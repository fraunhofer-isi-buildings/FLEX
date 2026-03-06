# FLEX-Community

## What It Does

FLEX-Community takes the **reference mode** operation results from a group of households and models how an energy community aggregator can generate profit by coordinating them. It does not re-run household simulation — it works entirely on top of precomputed hourly household profiles.

The model iterates over community scenario IDs. Each scenario defines a different aggregator configuration (e.g., different battery sizes), applied to the same fixed set of household operation results.

## Two Profit Mechanisms

These are fundamentally different in their logic and are computed separately:

### 1. P2P Trading Profit (Rule-Based)

The aggregator facilitates **peer-to-peer electricity trading** within the community in real time. When one household has PV surplus and another has a load deficit at the same hour, the aggregator routes electricity between them instead of letting it flow to and from the grid.

The calculation is purely arithmetic — no optimization involved:

$$\text{PV}_{\text{comm},t} = \sum_{h} \text{PV}_{h,t}, \qquad \text{Load}_{\text{comm},t} = \sum_{h} \text{Load}_{h,t}$$

$$\text{PV}^{\text{consumed}}_t = \min\!\left(\text{PV}_{\text{comm},t},\; \text{Load}_{\text{comm},t}\right)$$

$$\text{PV}^{\text{self}}_t = \sum_{h} \min\!\left(\text{PV}_{h,t},\; \text{Load}_{h,t}\right)$$

$$\text{P2P}_t = \text{PV}^{\text{consumed}}_t - \text{PV}^{\text{self}}_t$$

where $\text{PV}_{h,t}$ and $\text{Load}_{h,t}$ are the PV generation and electrical load of household $h$ at hour $t$ (from Ref results), $\text{PV}^{\text{consumed}}_t$ is the total community PV that can be consumed locally, $\text{PV}^{\text{self}}_t$ is the PV already consumed within each household, and $\text{P2P}_t$ is the additional PV consumption enabled by peer-to-peer trading.

The P2P profit comes from the spread between what the aggregator charges households for community electricity and what it pays them for their surplus PV:

$$p^{\text{sell}}_t = \lambda^{\text{elec}}_t \cdot f_{\text{sell}}, \qquad p^{\text{buy}}_t = \lambda^{\text{FiT}}_t \cdot f_{\text{buy}}$$

$$\text{P2P profit} = \sum_{t=1}^{8760} \text{P2P}_t \cdot \left( p^{\text{sell}}_t - p^{\text{buy}}_t \right)$$

where $\lambda^{\text{elec}}_t$ is the retail electricity price, $\lambda^{\text{FiT}}_t$ is the feed-in tariff, and $f_{\text{sell}}$, $f_{\text{buy}}$ are the aggregator's price factors (configured in `CommunityScenario`). Note that the sell and buy prices are based on **different** base prices (retail vs. feed-in).

This calculation is in `src/models/community/scenario.py` and `src/models/community/model.py`.

### 2. Aggregator Battery Optimization Profit (LP)

The aggregator operates a battery — either its own dedicated battery or, optionally, the combined capacity of household batteries — to **buy electricity cheaply and sell it at higher prices** (arbitrage).

This is a Pyomo LP solved in `src/models/community/model.py`:

**Objective** — maximize arbitrage profit:

$$\max \sum_{t=1}^{8760} \left( d_t \cdot \eta_d \cdot p^{\text{sell}}_t - c_t \cdot p^{\text{buy}}_t \right)$$

where:

* $c_t$ — battery charge at hour $t$ [kWh]
* $d_t$ — battery discharge at hour $t$ [kWh]
* $\eta_d$ — discharge efficiency (revenue is based on energy delivered after losses)
* $p^{\text{sell}}_t$, $p^{\text{buy}}_t$ — sell and buy prices as defined above

**Constraints:**

* **SoC dynamics:** $s_t = s_{t-1} + c_t \cdot \eta_c - d_t$, with $s_0 = 0$ and $\eta_c$ being the charge efficiency
* **Charge upper bound:** $c_t \leq F^{\text{feed}}_t$ — cannot charge more than the community's net PV surplus at hour $t$
* **Discharge upper bound:** $d_t \leq F^{\text{cons}}_t$ — cannot discharge more than the community's net load deficit at hour $t$
* **SoC upper bound:** depends on the control mode (see below)

where $F^{\text{feed}}_t = \sum_h \text{Feed2Grid}_{h,t}$ and $F^{\text{cons}}_t = \sum_h \text{Grid}_{h,t}$ are the community-level hourly grid feed-in and consumption, computed from the household Ref results.

The SoC upper bound depends on the `aggregator_household_battery_control` flag:

* $\text{ctrl} = 0$: aggregator operates only its own dedicated battery. $s_t \leq S_{\text{agg}}$ (constant).
* $\text{ctrl} = 1$: aggregator also controls household batteries. $s_t \leq S_{\text{agg}} + \sum_h (C^{\text{bat}}_h - \text{BatSoC}_{h,t})$, where $C^{\text{bat}}_h$ is the battery capacity of household $h$ and $\text{BatSoC}_{h,t}$ is its SoC from the Ref run (hourly-varying upper bound).

## Inputs

The community model reads operation results that have been pre-exported into community input tables (the `projects/test_community/main.py` helper functions `copy_operation_tables()` and `copy_household_ref_hour()` handle this):

| Table | Content |
|---|---|
| `CommunityScenario` | Community scenario parameters (battery size, charge/discharge efficiency, price factors, control mode, price column IDs) |
| `CommunityScenario_OperationScenario` | Operation scenario table copied from FLEX-Operation input |
| `CommunityScenario_Household_RefHour` | Hourly Ref results for all household scenarios — only 5 columns: `PhotovoltaicProfile`, `Grid`, `Load`, `Feed2Grid`, `BatSoC` |
| `CommunityScenario_Household_RefYear` | Annual Ref results: `TotalCost` per household scenario |
| `CommunityScenario_EnergyPrice` | Community-level electricity and feed-in price time series |
| `CommunityScenario_Component_Battery` | Battery parameter table (maps `ID_Battery` to capacity and efficiency) |

## Outputs

| Table | Resolution | Key columns |
|---|---|---|
| `CommunityResult_AggregatorHour` | Hourly, per community scenario | `p2p_trading`, `battery_charge`, `battery_discharge`, `battery_soc`, `buy_price`, `sell_price` |
| `CommunityResult_AggregatorYear` | Annual, per community scenario | `p2p_profit`, `opt_profit`, `total_profit` |

## Key Code Locations

| File | Role |
|---|---|
| `src/models/community/main.py` | Entry point — `run_community_model()` |
| `src/models/community/scenario.py` | Community scenario setup; P2P trading calculation |
| `src/models/community/model.py` | Aggregator P2P profit calculation; LP configuration, solving, result extraction |
| `src/models/community/aggregator.py` | Pyomo model definition: sets, variables, constraints, objective |
| `src/models/community/household.py` | Maps operation result rows to per-household objects |
| `src/models/community/data_collector.py` | Collects hourly and annual results and writes to output |

## How to Run

The community model depends on FLEX-Operation outputs. The typical workflow:

```bash
# 1. Run operation model to generate household results
python -m projects.test_operation.main

# 2. Copy operation results into community input format
#    (handled automatically by test_community/main.py)

# 3. Run community model
python -m projects.test_community.main
```

Output is written to `projects/test_community/output/`.
