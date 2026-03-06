# FLEX Model Documentation

```{toctree}
:maxdepth: 1
:caption: Contents

project-overview
model-architecture

behavior-model
operation-model
community-model

configuration
```

## Quick Start

Run all commands from the repository root.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run each model module independently
python -m projects.test_behavior.main
python -m projects.test_operation.main
python -m projects.test_community.main
```

## Repository Layout

```text
FLEX_cnb/
├── src/
│   ├── models/
│   │   ├── behavior/
│   │   │   ├── constants.py                    # Named constants and defaults
│   │   │   ├── household.py                    # Household-level aggregation
│   │   │   ├── main.py                         # Entry: gen_person_profiles / gen_household_profiles
│   │   │   ├── person.py                       # Person-level Markov chain simulation
│   │   │   ├── scenario.py                     # Scenario loading and data preparation
│   │   │   └── tus_process/                    # TUS data preprocessing and Markov model fitting
│   │   ├── operation/
│   │   │   ├── boiler.py                       # Boiler/heat pump type logic
│   │   │   ├── component_registry.py           # Component parameter registration
│   │   │   ├── components.py                   # Component dataclass definitions
│   │   │   ├── data_collector.py               # Result aggregation and persistence
│   │   │   ├── dispatch_opt.py                 # Optimization dispatch (SEMS mode)
│   │   │   ├── dispatch_ref.py                 # Reference dispatch (no control)
│   │   │   ├── input_tables.py                 # Input table loading
│   │   │   ├── main.py                         # Entry: run_operation_model
│   │   │   ├── opt_pyomo_config.py             # Pyomo parameter and set configuration
│   │   │   ├── opt_pyomo_structure.py          # Pyomo objective and constraint definitions
│   │   │   ├── physics_model.py                # Energy flow and physical state computation
│   │   │   ├── rc_equations.py                 # Building RC thermal model equations
│   │   │   ├── result_registry.py              # Output variable registry
│   │   │   ├── scenario.py                     # Scenario and component setup
│   │   │   ├── solver.py                       # Solver selection and invocation
│   │   │   ├── time_defs.py                    # Time index and resolution definitions
│   │   │   └── validation.py                   # Input validation
│   │   └── community/
│   │       ├── aggregator.py                   # Aggregator LP objective and structure
│   │       ├── data_collector.py               # Community result collection
│   │       ├── household.py                    # Household object within the community
│   │       ├── main.py                         # Entry: run_community_model
│   │       ├── model.py                        # Community optimization model
│   │       ├── scenario.py                     # Community scenario setup and P2P calculation
│   │       └── validation.py                   # Community input validation
│   ├── plotters/
│   │   ├── behavior/person_activity_share.py
│   │   ├── operation/household_load_balance.py
│   │   ├── community/aggregator_profit.py
│   │   ├── community/battery_operation.py
│   │   └── community/p2p_trading_amount.py
│   └── utils/
│       ├── config.py                           # Project path and config management
│       ├── db.py                               # File-based I/O and project initialization
│       ├── file_store.py                       # Unified table read/write (parquet / CSV / Excel)
│       ├── func.py                             # General utility functions
│       ├── parquet.py                          # Parquet read/write helpers
│       ├── plotter.py                          # Shared plotting utilities
│       └── tables.py                           # Input/output table name registry
├── projects/                                   # Example projects and test scenarios
├── docs/                                       # Documentation (Markdown)
└── README.md
```
