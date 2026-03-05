from typing import TYPE_CHECKING
import random
import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from models.behavior.scenario import BehaviorScenario

from models.behavior.constants import (
    LIGHTING_TECHNOLOGY_ID,
    MODEM_TECHNOLOGY_ID,
    REFRIGERATOR_TECHNOLOGY_ID,
    person_mark,
)


class Household:

    def __init__(self, scenario: "BehaviorScenario", id_household_type: int):
        self.scenario = scenario
        self.id_household_type = id_household_type
        self.household_members: List[str] = []

    def setup_household_members(self, household_df: pd.DataFrame, person_sample_size: int = 1):
        for index, row in household_df.iterrows():
            for _ in range(0, row["value"]):
                self.household_members.append(
                    person_mark(row["id_person_type"], row["id_teleworking_type"], random.randint(1, person_sample_size))
                )

    def aggregate_household_member_profiles(self):
        self.appliance_electricity_demand = self.aggregate_household_demand("appliance_electricity")
        self.hot_water_demand = self.aggregate_household_demand("hot_water")
        self.occupancy = self.aggregate_location()

    def aggregate_household_demand(self, end_use: str) -> np.ndarray:
        demand = np.zeros(8760)
        for member in self.household_members:
            raw = self.scenario.person_profiles[f'{end_use}_{member}'].to_numpy()
            demand += raw.reshape(8760, 6).mean(axis=1)
        return demand

    def aggregate_location(self) -> np.ndarray:
        total_at_home = np.zeros(8760)
        for member in self.household_members:
            raw = self.scenario.person_profiles[f'location_{member}'].to_numpy(dtype='float32')
            total_at_home += raw.reshape(8760, 6).mean(axis=1)
        return (total_at_home > 0.5).astype(int)

    def add_lighting_electricity_demand(self):
        lighting_power = self.scenario.get_technology_power(LIGHTING_TECHNOLOGY_ID)
        # Pre-extract activity arrays to avoid repeated DataFrame column lookups per hour
        activity_arrays = [
            self.scenario.person_profiles[f'activity_{m}'].to_numpy(dtype='float32')
            for m in self.household_members
        ]
        hours = np.arange(8760)
        # All members asleep = activity at first 10-min slot of each hour equals 1 (sleep activity)
        all_asleep = np.ones(8760, dtype=bool)
        for arr in activity_arrays:
            all_asleep &= (arr[hours * 6] == 1)
        lighting_mask = (self.occupancy == 1) & (hours % 24 > 15) & all_asleep
        self.appliance_electricity_demand[lighting_mask] += lighting_power

    def add_base_appliance_electricity_demand(self):
        modem_power = self.scenario.get_technology_power(MODEM_TECHNOLOGY_ID)
        refrigerator_power = self.scenario.get_technology_power(REFRIGERATOR_TECHNOLOGY_ID)
        self.appliance_electricity_demand += (modem_power + refrigerator_power)



