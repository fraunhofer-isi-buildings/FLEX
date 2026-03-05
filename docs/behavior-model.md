# FLEX-Behavior

## What It Does

FLEX-Behavior generates stochastic, behavior-derived energy demand profiles for residential households. Instead of using fixed load profiles, it simulates how occupants spend their time throughout the day and translates those activities into appliance electricity demand, hot water demand, and occupancy patterns.

The model runs in two stages:

1. **Person-level simulation** (`gen_person_profiles`): For each person type (defined by household role and teleworking status), the model generates multiple sample activity trajectories at **10-minute resolution** using a Markov chain. Each trajectory encodes: what activity the person is doing, which technology/appliance they are using, their location (home/away), and the resulting electricity and hot water demand.

2. **Household-level aggregation** (`gen_household_profiles`): For each household type, persons are assembled into a household, their profiles are aggregated, and base loads (lighting, always-on appliances) are added. The result is an **hourly** time series of appliance electricity demand, hot water demand, and occupancy — ready for use by FLEX-Operation.

## The Markov Chain Approach

Activity transitions are modeled as a first-order Markov chain: the probability of switching from one activity to another at each 10-minute step is derived from a **Time Use Survey (TUS)** — a large-scale diary dataset in which respondents record their activities throughout the day. FLEX preprocesses TUS data (see `src/models/behavior/tus_process/`) to extract transition probabilities stratified by person type, day type (weekday/weekend), and time of day.

This means the output profiles are stochastic: each model run (with a different random seed) produces a different but statistically consistent trajectory. The default configuration generates 5 sample trajectories per person type and 1 sample household per household type.

## Inputs

| Table | Content |
|---|---|
| `BehaviorScenario_Household` | Household type definitions (which person types compose each household) |
| `BehaviorScenario_Person` | Person type definitions (role, teleworking type) |
| `BehaviorParam_Activity_*` | Markov transition probabilities, duration distributions from TUS |
| `BehaviorParam_Technology_*` | Appliance power and usage duration per activity |
| `BehaviorID_*` | Lookup tables for activity, person type, location, technology IDs |

## Outputs

| Table | Resolution | Key columns |
|---|---|---|
| `BehaviorResult_PersonProfiles` | 10-minute, 8 per day × 365 = 52,560 rows | `activity_{type}_{sample}`, `technology_*`, `appliance_electricity_*`, `hot_water_*`, `location_*` |
| `BehaviorResult_HouseholdProfiles` | Hourly, 8,760 rows | `appliance_electricity_{ht}_{sample}`, `hot_water_*`, `occupancy_*` |

The household profiles table is the primary handoff to FLEX-Operation, linked via `OperationScenario_BehaviorProfile`.

## Key Code Locations

| File | Role |
|---|---|
| `src/models/behavior/main.py` | Entry point — `gen_person_profiles()` and `gen_household_profiles()` |
| `src/models/behavior/person.py` | Markov chain simulation at the individual level |
| `src/models/behavior/household.py` | Member aggregation, lighting and base load addition |
| `src/models/behavior/scenario.py` | Loads TUS parameters and person profiles into memory |
| `src/models/behavior/tus_process/` | Offline preprocessing of raw TUS data into transition probability tables |

## How to Run

```bash
python -m projects.test_behavior.main
```

Output is written to `projects/test_behavior/output/`.
