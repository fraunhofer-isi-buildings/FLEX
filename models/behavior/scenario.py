import os
from collections import OrderedDict
from typing import Optional

import pandas as pd
from tqdm import tqdm
import numpy as np
from utils import func
from utils.config import Config
from utils.db import create_db_conn
from utils.tables import InputTables
from utils.tables import OutputTables


class BehaviorScenario:

    def __init__(self, config: "Config"):
        self.config = config
        self.db = create_db_conn(self.config)
        self.period_num = 8760
        self.person_profiles: Optional[pd.DataFrame] = None
        self.day_type = {
            1: 1,  # Monday
            2: 1,  # Tuesday
            3: 1,  # Wednesday
            4: 1,  # Thursday
            5: 1,  # Friday
            6: 2,  # Saturday
            0: 2,  # Sunday --> weekday % 7 = 0
        }
        self.import_scenario_data()

    def import_scenario_data(self):
        self.activity_tus_profile = self.db.read_dataframe(InputTables.BehaviorParam_Activity_TUSProfile.name)
        self.activity_start_prob = self.db.read_dataframe(InputTables.BehaviorParam_Activity_TUSStart.name)
        self.activity_change_prob = self.db.read_dataframe(InputTables.BehaviorParam_Activity_ChangeProb.name)
        self.activity_duration_prob = self.db.read_dataframe(InputTables.BehaviorParam_Activity_DurationProb.name)
        self.technology_trigger_prob = self.db.read_dataframe(InputTables.BehaviorParam_Technology_TriggerProbability.name)
        self.technology_power = self.db.read_dataframe(InputTables.BehaviorParam_Technology_Power.name)
        self.technology_duration = self.db.read_dataframe(InputTables.BehaviorParam_Technology_Duration.name)
        self.activities = self.db.read_dataframe(InputTables.BehaviorID_Activity.name)['name'].tolist()
        self.technologies = self.db.read_dataframe(InputTables.BehaviorID_Technology.name)['name'].tolist()

    def setup_person_activity_data(self):
        self.setup_teleworking_prob()
        self.setup_period_most_common_activity()
        self.setup_activity_start()
        self.setup_activity_duration()
        self.setup_activity_now()
        self.setup_activity_technology()
        self.setup_activity_location()

    def setup_teleworking_prob(self):
        self.teleworking_prob = {}
        df = self.db.read_dataframe(InputTables.BehaviorParam_TeleworkingProb.name)
        for index, row in df.iterrows():
            self.teleworking_prob[row["id_teleworking_type"]] = row["probability"]

    def setup_period_most_common_activity(self):
        self.period_most_common_activity = {}
        for id_person_type in tqdm(range(1, 5), desc="setting up period_most_common_activity"):
            for id_day_type in range(1, 3):
                od = OrderedDict([
                    ("id_day_type", id_day_type),
                    ("id_person_type", id_person_type),
                ])
                df = self.filter_dataframe_dynamic(self.activity_tus_profile.copy(), od_filter=od)
                for timeslot in range(1, 145):
                    period_activities = df[f't{timeslot}'].to_numpy()
                    d = {}
                    for id_activity in range(1, 18):
                        d[id_activity] = np.count_nonzero(period_activities == id_activity)
                    self.period_most_common_activity[(id_person_type, id_day_type, timeslot)] = d

    def get_period_most_common_activity(self, id_person_type: int, id_day_type: int, timeslot: int):
        return int(func.dict_sample(self.period_most_common_activity[(id_person_type, id_day_type, timeslot)]))

    def setup_activity_start(self):
        self.activity_start = {}
        for id_person_type in tqdm(range(1, 5), desc="setting up activity_start"):
            for id_day_type in range(1, 3):
                od = OrderedDict([
                    ("id_day_type", id_day_type),
                    ("id_person_type", id_person_type),
                ])
                df = self.filter_dataframe_dynamic(self.activity_start_prob.copy(), od_filter=od)
                d = {}
                for index, row in df.iterrows():
                    d[row["id_activity"]] = row["probability"]
                self.activity_start[(id_person_type, id_day_type)] = d

    def get_activity_start(self, id_person_type: int, id_day_type: int):
        return int(func.dict_sample(self.activity_start[(id_person_type, id_day_type)]))

    def setup_activity_duration(self):
        self.activity_duration = {}
        for id_person_type in tqdm(range(1, 5), desc="setting up activity_duration"):
            for id_day_type in range(1, 3):
                for id_activity in range(1, 18):
                    for timeslot in range(1, 145):
                        od = OrderedDict([
                            ("id_activity", id_activity),
                            ("t", timeslot),
                            ("id_day_type", id_day_type),
                            ("id_person_type", id_person_type),
                        ])  # these items are ranked from most to least important
                        df = self.filter_dataframe_dynamic(self.activity_duration_prob.copy(), od)
                        d = {}
                        for index, row in df.iterrows():
                            d[row["duration"]] = row["probability"]
                        self.activity_duration[(id_person_type, id_day_type, id_activity, timeslot)] = d

    def get_activity_duration(self, id_person_type: int, id_day_type: int, id_activity: int, timeslot: int):
        return int(func.dict_sample(self.activity_duration[(id_person_type, id_day_type, id_activity, timeslot)]))

    def setup_activity_now(self):
        self.activity_now = {}
        for id_person_type in tqdm(range(1, 5), desc="setting up activity_now"):
            for id_day_type in range(1, 3):
                for id_activity_before in range(1, 18):
                    for timeslot in range(1, 145):
                        od = OrderedDict([
                            ("id_activity_before", id_activity_before),
                            ("t", timeslot),
                            ("id_day_type", id_day_type),
                            ("id_person_type", id_person_type),
                        ])  # these items are ranked from most to least important
                        df = self.filter_dataframe_dynamic(self.activity_change_prob, od)
                        d = {}
                        for index, row in df.iterrows():
                            d[row["id_activity_now"]] = row["probability"]
                        self.activity_now[(id_person_type, id_day_type, id_activity_before, timeslot)] = d

    def get_activity_now(self, id_person_type: int, id_day_type: int, id_activity_before: int, timeslot: int):
        return int(func.dict_sample(self.activity_now[(id_person_type, id_day_type, id_activity_before, timeslot)]))

    def setup_activity_technology(self):
        self.activity_technology = {}
        for id_activity in range(1, 18):
            df = self.technology_trigger_prob.loc[self.technology_trigger_prob["id_activity"] == id_activity]
            d = {}
            for index, row in df.iterrows():
                d[row["id_technology"]] = row["value"]
            self.activity_technology[id_activity] = d

    def get_activity_technology(self, id_activity: int):
        return int(func.dict_sample(self.activity_technology[id_activity]))

    def setup_activity_location(self):
        df = self.db.read_dataframe(InputTables.BehaviorParam_Activity_Location.name)
        self.activity_location = {}
        for i, row in df.iterrows():
            self.activity_location[row["id_activity"]] = row["id_location"]

    def get_technology_power(self, id_technology: int):
        power = self.technology_power.loc[self.technology_power["id_technology"] == id_technology, ['value']]
        return power.iloc[0, 0]

    def get_technology_duration(self, id_technology: int):
        duration = self.technology_duration.loc[self.technology_duration["id_technology"] == id_technology, ['value']]
        return duration.iloc[0, 0]

    def load_person_profiles(self):
        # self.person_profiles = self.db.read_dataframe(OutputTables.BehaviorResult_PersonProfiles.name)
        self.person_profiles = pd.read_csv(
            os.path.join(self.config.output, f'{OutputTables.BehaviorResult_PersonProfiles.name}.csv')
        )
        return self.person_profiles

    @staticmethod
    def filter_dataframe_dynamic(df, od_filter: "OrderedDict"):
        while len(func.filter_df(df, od_filter)) == 0 and len(od_filter) > 1:
            od_filter.popitem()
        filtered_df = func.filter_df(df, od_filter)
        return filtered_df
