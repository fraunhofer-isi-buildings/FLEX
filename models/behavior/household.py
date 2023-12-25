from typing import List, Optional, TYPE_CHECKING
import random
import pandas as pd

if TYPE_CHECKING:
    from models.behavior.scenario import BehaviorScenario


class Household:

    def __init__(self, scenario: "BehaviorScenario", id_household_type: int):
        self.scenario = scenario
        self.id_household_type = id_household_type
        self.household_members: List[str] = []

    def setup_household_members(self, household_df: pd.DataFrame, person_sample_size: int = 1):
        for index, row in household_df.iterrows():
            for _ in range(0, row["value"]):
                self.household_members.append(
                    f'p{row["id_person_type"]}t{row["id_teleworking_type"]}s{random.randint(1, person_sample_size)}'
                )

    def aggregate_household_member_profiles(self):
        self.appliance_electricity_demand = self.aggregate_household_demand("appliance_electricity")
        self.hot_water_demand = self.aggregate_household_demand("hot_water")
        self.occupancy = self.aggregate_location()

    def aggregate_household_demand(self, end_use: str) -> List[float]:
        household_demand = [0] * 8760
        for member in self.household_members:
            member_demand = self.scenario.person_profiles[f'{end_use}_{member}'].to_numpy()
            for hour in range(0, 8760):
                household_demand[hour] += member_demand[hour * 6:hour * 6 + 6].sum()/6
        return household_demand

    def aggregate_location(self) -> List[int]:
        occupancy = [0] * 8760
        for hour in range(0, 8760):
            total_occupancy = 0
            for member in self.household_members:
                member_location = self.scenario.person_profiles[f'location_{member}'].to_numpy(dtype='float32')
                total_occupancy += member_location[hour * 6:hour * 6 + 6].sum()/6
            if total_occupancy > 0.5:
                occupancy[hour] = 1
        return occupancy

    def add_lighting_electricity_demand(self):

        def household_is_asleep(hour):
            asleep = True
            for member in self.household_members:
                member_id_activity = self.scenario.person_profiles[f'activity_{member}'].to_numpy(dtype='float32')
                if member_id_activity[hour * 6] != 1:
                    asleep = False
            return asleep

        lighting_power = self.scenario.get_technology_power(36)
        for hour in range(0, 8760):
            if self.occupancy[hour] == 1 and hour % 24 > 15 and household_is_asleep(hour):
                self.appliance_electricity_demand[hour] += lighting_power

    def add_base_appliance_electricity_demand(self):
        modem_power = self.scenario.get_technology_power(35)
        refrigerator_power = self.scenario.get_technology_power(37)
        for hour in range(0, 8760):
            self.appliance_electricity_demand[hour] += (modem_power + refrigerator_power)



