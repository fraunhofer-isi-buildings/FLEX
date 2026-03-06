# FLEX-Behavior

## What It Does

FLEX-Behavior generates stochastic, behavior-derived energy demand profiles for residential households. Instead of using fixed load profiles, it simulates how occupants spend their time throughout the day and translates those activities into appliance electricity demand, hot water demand, and occupancy patterns.

The model runs in two stages:

1. **Person-level simulation** (`gen_person_profiles`): For each person type (defined by household role and teleworking status), the model generates multiple sample activity trajectories at **10-minute resolution** using a Markov chain. Each trajectory encodes: what activity the person is doing, which technology/appliance they are using, their location (home/away), and the resulting electricity and hot water demand.

2. **Household-level aggregation** (`gen_household_profiles`): For each household type, persons are assembled into a household, their profiles are aggregated, and base loads (lighting, always-on appliances) are added. The result is an **hourly** time series of appliance electricity demand, hot water demand, and occupancy — ready for use by FLEX-Operation.

## The Markov Chain Approach

Activity transitions are modeled as a first-order Markov chain: the probability of switching from one activity to another at each 10-minute step is derived from a **Time Use Survey (TUS)** — a large-scale diary dataset in which respondents record their activities throughout the day. FLEX preprocesses TUS data (see `src/models/behavior/tus_process/`) to extract transition probabilities stratified by person type, day type (weekday/weekend), and time of day.

This means the output profiles are stochastic: each model run (with a different random seed) produces a different but statistically consistent trajectory. The default configuration generates 5 sample trajectories per person type and 1 sample household per household type.

### Person types

| ID | Description |
|---|---|
| 1 | Working adult, full-time employed |
| 2 | Working adult, part-time employed |
| 3 | Student (age < 20) |
| 4 | Retired / unemployed (age 66+) |

Non-working types (3, 4) have special handling: if the Markov chain samples a "working" activity, it is replaced by the most common activity at that time slot from the TUS data.

### Teleworking

Each day, the model randomly decides whether a person works from home based on `BehaviorParam_TeleworkingProb`. This probability varies by teleworking type. Activities with location type "variable" (e.g., work) are then assigned home or away accordingly.

## Inputs

| Table | Content |
|---|---|
| `BehaviorScenario_Household` | Household type definitions (which person types compose each household) |
| `BehaviorScenario_Person` | Person type definitions (role, teleworking type) |
| `BehaviorParam_Activity_ChangeProb` | Markov transition probabilities from TUS |
| `BehaviorParam_Activity_DurationProb` | Activity duration distributions from TUS |
| `BehaviorParam_Activity_TUSProfile` | Raw TUS activity sequences (144 slots/day) |
| `BehaviorParam_Activity_TUSStart` | Day-start activity probabilities |
| `BehaviorParam_Activity_Location` | Activity → location mapping (home / away / variable) |
| `BehaviorParam_Technology_TriggerProbability` | Activity → appliance mapping probabilities |
| `BehaviorParam_Technology_Power` | Appliance power ratings (Watt) |
| `BehaviorParam_Technology_Duration` | Appliance usage duration (in 10-min slots) |
| `BehaviorParam_TeleworkingProb` | Work-from-home probability per teleworking type |
| `BehaviorID_*` | Lookup tables for activity, person type, location, technology IDs |

## Outputs

| Table | Resolution | Key columns |
|---|---|---|
| `BehaviorResult_PersonProfiles` | 10-minute (144/day × 365 = 52,560 rows) | `activity_p{type}t{telework}s{sample}`, `technology_*`, `appliance_electricity_*`, `hot_water_*`, `location_*` |
| `BehaviorResult_HouseholdProfiles` | Hourly (8,760 rows) | `appliance_electricity_ht{type}s{sample}`, `hot_water_*`, `occupancy_*` |

The household profiles table is the primary handoff to FLEX-Operation, linked via `OperationScenario_BehaviorProfile`.

## Key Code Locations

| File | Role |
|---|---|
| `src/models/behavior/main.py` | Entry point — `gen_person_profiles()` and `gen_household_profiles()` |
| `src/models/behavior/person.py` | Markov chain simulation at the individual level |
| `src/models/behavior/household.py` | Member aggregation, lighting and base load addition |
| `src/models/behavior/scenario.py` | Loads TUS parameters and person profiles into memory |
| `src/models/behavior/constants.py` | Named constants (activity IDs, person type IDs, mark functions) |
| `src/models/behavior/tus_process/` | Offline preprocessing of raw TUS data into transition probability tables |

## How to Run

```bash
python -m projects.test_behavior.main
```

Output is written to `projects/test_behavior/output/`.
