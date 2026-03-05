# Architecture

FLEX models residential energy systems across three levels of abstraction, each handled by a dedicated module that runs in sequence:

| Module | Level | Core question |
|--------|-------|--------------|
| FLEX-Behavior | Demand | What do households consume, and when? |
| FLEX-Operation | Dispatch | How does the household energy system operate, optimally or otherwise? |
| FLEX-Community | Community | How can an aggregator profit by coordinating a group of households? |

**Shared data organization.** All three modules follow the same pattern:

* Each module has a main scenario table where every row defines one independent configuration.
* The model iterates over all rows and writes separate result files per scenario ID — e.g., `OperationResult_RefHour_S1`, `_S2`, ...
* Parameter sweeps require no code changes: add rows to the scenario table, re-run, get more results.
* FLEX-Community adds a second layer — each `CommunityScenario` ID assembles a fixed set of operation scenarios into a community with a particular aggregator configuration (e.g., different battery sizes).

**How the modules connect.** Each module's output becomes part of the next module's input:

* **Behavior → Operation**: `BehaviorResult_HouseholdProfiles` provides hourly appliance electricity demand, hot water demand, and occupancy, which FLEX-Operation reads as behavioral input when coupling is enabled.
* **Operation → Community**: `OperationResult_RefHour_S{id}` provides hourly PV generation, grid import/export, load, and battery SoC per household scenario. `OperationResult_RefYear_S{id}` provides the corresponding annual cost. FLEX-Community reads only Ref mode outputs — it never re-runs household simulation, only aggregates and optimizes on top of already-computed results.

All table names are defined as enums in `src/utils/tables.py`. Hourly result tables are stored as parquet files; monthly and annual summaries as CSV.
