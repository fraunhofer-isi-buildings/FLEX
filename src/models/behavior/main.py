import os.path
import random

import numpy as np
import pandas as pd
from tqdm import tqdm
from src.models.behavior.constants import person_mark
from src.models.behavior.household import Household
from src.models.behavior.person import Person
from src.models.behavior.scenario import BehaviorScenario
from src.utils.config import Config
from src.utils.db import create_db_conn
from src.utils.func import get_logger
from src.utils.func import get_time_cols_hour
from src.utils.func import get_time_cols_10min
from src.utils.tables import InputTables
from src.utils.tables import OutputTables

logger = get_logger(__name__)
PERSON_SAMPLE_SIZE = 5
HOUSEHOLD_SAMPLE_SIZE = 1
DEFAULT_SEED = 42


def gen_person_profiles(
    config: "Config",
    seed: int = DEFAULT_SEED,
    person_sample_size: int = PERSON_SAMPLE_SIZE,
):
    random.seed(seed)
    np.random.seed(seed)
    person_profiles = {}
    db = create_db_conn(config)
    scenario = BehaviorScenario(config=config)
    scenario.setup_person_activity_data()
    person_scenarios = db.read_dataframe(InputTables.BehaviorScenario_Person.name)
    for index, row in tqdm(person_scenarios.iterrows(), total=len(person_scenarios), desc="generating person profiles"):
        for sample in range(1, person_sample_size + 1):
            person = Person(
                scenario=scenario,
                id_person_type=row["id_person_type"],
                id_teleworking_type=row["id_teleworking_type"]
            )
            person.setup()
            mark = person_mark(person.id_person_type, person.id_teleworking_type, sample)
            person_profiles[f"activity_{mark}"] = person.activity_profile
            person_profiles[f"technology_{mark}"] = person.technology_profile
            person_profiles[f"appliance_electricity_{mark}"] = person.appliance_electricity_demand
            person_profiles[f"hot_water_{mark}"] = person.hot_water_demand
            person_profiles[f"location_{mark}"] = person.location

    person_profiles_df = pd.DataFrame(person_profiles)
    person_profiles_df = pd.concat([get_time_cols_10min(), person_profiles_df], axis=1)
    person_profiles_df.to_csv(
        os.path.join(config.output, f'{OutputTables.BehaviorResult_PersonProfiles.name}.csv'),
        index=False
    )


def gen_household_profiles(
    config: "Config",
    seed: int = DEFAULT_SEED,
    household_sample_size: int = HOUSEHOLD_SAMPLE_SIZE,
    person_sample_size: int = PERSON_SAMPLE_SIZE,
):
    random.seed(seed)
    np.random.seed(seed)
    household_profiles = {}
    db = create_db_conn(config)
    scenario = BehaviorScenario(config=config)
    scenario.load_person_profiles()
    household_scenarios = db.read_dataframe(InputTables.BehaviorScenario_Household.name)
    household_type_ids = household_scenarios["id_household_type"].unique()
    for id_household_type in tqdm(household_type_ids, total=len(household_type_ids), desc="generating household profiles"):
        for sample in range(1, household_sample_size + 1):
            household = Household(
                scenario=scenario,
                id_household_type=id_household_type,
            )
            household.setup_household_members(
                household_df=household_scenarios.loc[household_scenarios["id_household_type"] == id_household_type],
                person_sample_size=person_sample_size
            )
            household.aggregate_household_member_profiles()
            household.add_lighting_electricity_demand()
            household.add_base_appliance_electricity_demand()
            mark = f"ht{household.id_household_type}s{sample}"
            household_profiles[f"appliance_electricity_{mark}"] = household.appliance_electricity_demand
            household_profiles[f"hot_water_{mark}"] = household.hot_water_demand
            household_profiles[f"occupancy_{mark}"] = household.occupancy

    household_profiles_df = pd.DataFrame(household_profiles)
    household_profiles_df = pd.concat([get_time_cols_hour(), household_profiles_df], axis=1)
    household_profiles_df.to_csv(
        os.path.join(config.output, f'{OutputTables.BehaviorResult_HouseholdProfiles.name}.csv'),
        index=False
    )
    db.write_dataframe(
        table_name=OutputTables.BehaviorResult_HouseholdProfiles.name,
        data_frame=household_profiles_df,
        if_exists="replace"
    )
