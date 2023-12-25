import os
from typing import List

import pandas as pd
from utils.tables import InputTables


class TUSActivityProfileProcessor:

    def __init__(self):
        self.path = os.path.abspath(os.path.dirname(__file__))
        self.input_dir = os.path.join(self.path, '../input')
        self.output_dir = os.path.join(self.path, '../output')
        # input tables
        self.ActivityRelation = "Relation_TUSActivity.xlsx"
        self.TUS_ActivityProfile = "TUS_ActivityProfile.xlsx"
        self.TUS_HouseholdInfo = "TUS_Households.xlsx"
        self.TUS_PersonInfo = "TUS_Persons.xlsx"
        # output tables
        self.Result_ActivityProfile = f"{InputTables.BehaviorParam_Activity_TUSProfile.name}_starting4am.xlsx"
        # definition
        self.define_person_types()
        self.define_day_types()

    def define_person_types(self):
        """
        alterx: age range (0-85)
        pc7: employment type: 1: full-time employed; 2: part-time employed; -2: unemployed
        ha6x: ?
        """
        self.person_types = {
            1: {'alterx': range(20, 66), 'pc7': [1]},
            2: {'alterx': range(20, 66), 'pc7': [2]},
            3: {'alterx': range(0, 20), 'ha6x': [3]},
            4: {'alterx': range(66, 86), 'pc7': [-2]},
        }

    def define_day_types(self):
        """
        wtagfei: day of the week
        """
        self.day_types = {
            1: {'wtagfei': [1, 2, 3, 4, 5]},
            2: {'wtagfei': [6, 7]},
        }

    def generate_input_activity_profile(self):
        df = self.convert_tus_activity_profile()
        df_out = pd.DataFrame()
        for person_key, person_filter in self.person_types.items():
            for day_key, day_filter in self.day_types.items():
                df_filtered = df[df["id_persx"].isin(self.filter_person(person_filter))]
                df_filtered = df_filtered[df_filtered["wtagfei"].isin(day_filter["wtagfei"])]
                df_filtered.drop(columns=['id_hhx', 'id_persx', 'id_tagx', 'monat', "wtagfei"], inplace=True)
                df_filtered.insert(loc=0, column='id_person_type', value=person_key)
                df_filtered.insert(loc=1, column='id_day_type', value=day_key)
                df_out = pd.concat([df_out, df_filtered], ignore_index=True)
        df_out.to_excel(os.path.join(self.output_dir, self.Result_ActivityProfile), index=False)

    def convert_tus_activity_profile(self):
        self.prepare_activity_relation()
        df = pd.read_excel(os.path.join(self.input_dir, self.TUS_ActivityProfile))
        ID_COLS = ["id_hhx", "id_persx", "id_tagx", "monat", "wtagfei"]
        TIME_COLS = [f'tb1_{i}' for i in range(1, 145)]
        cols = ID_COLS + TIME_COLS
        df = df[cols].dropna(axis="index")
        for i, row in df.iterrows():
            for col in TIME_COLS:
                df.at[i, col] = self.activity_relation[row[col]]
        for col in TIME_COLS:
            new_col = f't{col.split("_")[1]}'
            df.rename(columns={col: new_col}, inplace=True)
        return df

    def prepare_activity_relation(self):
        df = pd.read_excel(os.path.join(self.input_dir, self.ActivityRelation))
        self.activity_relation = {}
        for index, row in df.iterrows():
            self.activity_relation[row["id_survey_activity"]] = row["id_activity"]

    def filter_person(self, person_filter: dict) -> List[int]:
        self.households = pd.read_excel(os.path.join(self.input_dir, self.TUS_HouseholdInfo))
        self.persons = pd.read_excel(os.path.join(self.input_dir, self.TUS_PersonInfo))
        df_person = self.persons[~self.persons.pb3.isin([11, 10, 9, 7, 5, 4])]
        df_person = df_person[~df_person.soz.eq(4)]
        for key, value in person_filter.items():
            if key in df_person.columns:
                df_person = df_person[df_person[key].isin(value)]
        if 'ha1x' in list(person_filter.keys()):
            df_household = self.households[~self.households.ha1x.isin(person_filter["ha1x"])]
            df_person = df_person[df_person.id_hhx.isin(df_household['id_hhx'].tolist())]
        return df_person['id_persx'].tolist()







