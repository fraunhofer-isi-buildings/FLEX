# FLEX-Community

## What It Does

FLEX-Community takes the **reference mode** operation results from a group of households and models how an energy community aggregator can generate profit by coordinating them. It does not re-run household simulation — it works entirely on top of precomputed hourly household profiles.

The model iterates over community scenario IDs. Each scenario defines a different aggregator configuration (e.g., different battery sizes), applied to the same fixed set of household operation results.

## Two Profit Mechanisms

These are fundamentally different in their logic and are computed separately:

### 1. P2P Trading Profit (Rule-Based)

The aggregator facilitates **peer-to-peer electricity trading** within the community in real time. When one household has PV surplus and another has a load deficit at the same hour, the aggregator routes electricity between them instead of letting it flow to and from the grid.

The calculation is purely arithmetic — no optimization involved:

$$\text{PV}_{\text{comm},t} = \sum_{h} \text{PV}_{h,t}$$

$$\text{Load}_{\text{comm},t} = \sum_{h} \text{Load}_{h,t}$$

$$\text{PV}^{\text{consumed}}_t = \min\!\left(\text{PV}_{\text{comm},t},\; \text{Load}_{\text{comm},t}\right)$$

$$\text{PV}^{\text{self}}_t = \sum_{h} \min\!\left(\text{PV}_{h,t},\; \text{Load}_{h,t}\right)$$

$$\text{P2P}_t = \text{PV}^{\text{consumed}}_t - \text{PV}^{\text{self}}_t$$

The P2P profit comes from the spread between what the aggregator charges households for community electricity (a fraction of the retail price) and what it pays them for their surplus PV (a fraction of the feed-in tariff). The buy/sell price factors are scenario parameters (`aggregator_buy_price_factor`, `aggregator_sell_price_factor`).

This calculation is in `src/models/community/scenario.py`.

### 2. Aggregator Battery Optimization Profit (LP)

The aggregator operates a battery — either its own dedicated battery or, optionally, the combined capacity of household batteries — to **buy electricity cheaply and sell it at higher prices** (arbitrage).

This is a Pyomo LP solved in `src/models/community/model.py`:

* **Objective**:

$$\max \sum_{t=1}^{8760} \left( d_t \cdot \eta_{\text{dis}} \cdot p^{\text{sell}}_t \;-\; c_t \cdot p^{\text{buy}}_t \right)$$

* Where $p^{\text{buy}}_t = \lambda^{\text{FiT}}_t \cdot f_{\text{buy}}$ and $p^{\text{sell}}_t = \lambda^{\text{elec}}_t \cdot f_{\text{sell}}$
* Constraints: battery SoC dynamics, charge/discharge power limits, SoC upper bound

The SoC upper bound depends on the `aggregator_household_battery_control` flag:
* `ctrl = 0`: aggregator operates only its own dedicated battery.
* `ctrl = 1`: aggregator also controls household batteries — available capacity is the aggregator battery plus the unused capacity across all household batteries (`battery_capacity − household_BatSoC`).

## Inputs

The community model reads operation results that have been pre-exported into community input tables (the `projects/test_community/main.py` helper function `copy_operation_tables` handles this):

| Table | Content |
|---|---|
| `CommunityScenario` | Community scenario parameters (battery size, price factors, control mode) |
| `CommunityScenario_OperationScenario` | Operation scenario table copied from FLEX-Operation input |
| `CommunityScenario_Household_RefHour` | Hourly Ref results for all household scenarios: `PhotovoltaicProfile`, `Grid`, `Load`, `Feed2Grid`, `BatSoC` |
| `CommunityScenario_Household_RefYear` | Annual Ref results: `TotalCost` per household scenario |
| `CommunityScenario_EnergyPrice` | Community-level electricity and feed-in price time series |
| `CommunityScenario_Component_Battery` | Battery capacity table (maps `ID_Battery` to capacity in Wh) |

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
| `src/models/community/model.py` | Aggregator LP: configures parameters, solves, extracts result |
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
