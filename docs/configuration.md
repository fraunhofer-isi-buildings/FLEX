# Configuration & Data Format

## Solver Configuration

FLEX-Operation and FLEX-Community solve LP models using [Pyomo](http://www.pyomo.org/). The solver is configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `FLEX_OPERATION_SOLVER` | `gurobi` | Solver name. Any Pyomo-supported solver works (e.g. `gurobi`, `cplex`, `glpk`, `highs`). |
| `FLEX_OPERATION_SOLVER_INTERFACE` | `shell` | `shell` (subprocess) or `persistent` (in-process, only for gurobi/cplex). |
| `FLEX_OPERATION_SOLVER_OPTIONS` | *(empty)* | Comma-separated `key=value` pairs passed to the solver (e.g. `TimeLimit=300,MIPGap=0.01`). |

Example:

```bash
export FLEX_OPERATION_SOLVER=highs
export FLEX_OPERATION_SOLVER_INTERFACE=shell
python -m projects.test_operation.main
```

[Gurobi](https://www.gurobi.com/) is recommended and requires a license (free for academics). [HiGHS](https://highs.dev/) is a high-quality open-source alternative.

## Other Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLEX_OPERATION_HOUR_FILE_FORMAT` | `parquet` | Format for hourly result files: `parquet` or `csv`. |
| `FLEX_OPERATION_CLEAN_START` | `1` | Set to `0` to keep existing output files and only run pending scenarios. |

## Input Data Format

### Supported file formats

Input tables are read from the project's `input/` folder. The following formats are supported, in order of lookup priority:

1. `.csv`
2. `.xlsx`
3. `.parquet.gzip`
4. `.parquet`

File names must exactly match the table names defined in `src/utils/tables.py` (e.g. `OperationScenario.xlsx`, `OperationScenario_Component_Battery.xlsx`).

### Table name registry

All input and output table names are defined as enums in `src/utils/tables.py`:

* `InputTables` — 17 Behavior tables, 17 Operation tables, 6 Community tables
* `OutputTables` — 2 Behavior, 6 Operation, 2 Community

### Time series conventions

* All hourly time series have exactly **8,760 rows** (one non-leap year).
* Behavior person-level profiles have **52,560 rows** (10-minute resolution: 144 slots/day × 365 days).
* The year is assumed to start on a Tuesday (matching 2019).

## Output Data Format

### Per-scenario files

Hourly results are written as one file per scenario:

```text
OperationResult_RefHour_S1.parquet.gzip
OperationResult_RefHour_S2.parquet.gzip
OperationResult_OptHour_S1.parquet.gzip
...
```

### Aggregate files

Monthly and annual results are written per-scenario first (`_S{id}` suffix), then automatically merged into a single file after all scenarios complete:

```text
OperationResult_RefYear.csv       ← merged from _S1, _S2, ...
OperationResult_OptYear.csv
OperationResult_RefMonth.csv      ← (if monthly output is enabled)
```

The merge deduplicates by `ID_Scenario` (keeping the latest) and removes the per-scenario files.

## Parallel Execution

For large scenario sweeps, use `run_operation_model_parallel()`:

```python
from src.models.operation.main import run_operation_model_parallel
from src.utils.config import Config

config = Config("my_project", "/path/to/project")
run_operation_model_parallel(
    config=config,
    task_num=4,         # number of parallel workers
    save_hour=True,
    run_ref=True,
    run_opt=True,
)
```

This splits scenarios across workers using joblib, writes results to temporary `task_{id}/` subdirectories, then merges everything back into the main `output/` folder.

## Creating Your Own Project

1. Create a project directory with `input/` and `output/` subfolders:
   ```text
   my_project/
   ├── input/
   │   ├── OperationScenario.xlsx
   │   ├── OperationScenario_Component_Building.xlsx
   │   ├── ...
   │   └── OperationScenario_RegionWeather.xlsx
   └── output/
   ```

2. Populate input tables. Use `projects/test_operation/input/` as a template — column names and formats must match exactly.

3. Write a runner script:
   ```python
   from src.models.operation.main import run_operation_model
   from src.utils.config import Config
   from src.utils.db import prepare_project_run

   config = Config("my_project", "/path/to/my_project")
   prepare_project_run(config)
   run_operation_model(config, save_hour=True)
   ```

4. For FLEX-Community, you need to export Operation results into Community input format. See `projects/test_community/main.py` for the helper functions `copy_operation_tables()` and `copy_household_ref_hour()` that automate this.
