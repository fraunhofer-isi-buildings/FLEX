from typing import Dict, Optional

import numpy as np
import pandas as pd

from models.operation.constants import OperationScenarioComponent


class Household:

    def __init__(self, operation_scenario_id):
        self.operation_scenario_id: int = operation_scenario_id
        self.id_region: Optional[int] = None
        self.id_building: Optional[int] = None
        self.id_boiler: Optional[int] = None
        self.id_space_heating_tank: Optional[int] = None
        self.id_hot_water_tank: Optional[int] = None
        self.id_space_cooling_technology: Optional[int] = None
        self.id_pv: Optional[int] = None
        self.id_battery: Optional[int] = None
        self.id_vehicle: Optional[int] = None
        self.id_energy_price: Optional[int] = None
        self.id_behavior: Optional[int] = None
        self.id_heating_element: Optional[int] = None
        # hour results from operation model
        self.PhotovoltaicProfile_hour: Optional[np.array] = None
        self.Grid_hour: Optional[np.array] = None
        self.Load_hour: Optional[np.array] = None
        self.Feed2Grid_hour: Optional[np.array] = None
        self.BatSoC_hour: Optional[np.array] = None
        # year results from operation model
        self.TotalCost_year: Optional[float] = None

    def setup_component_ids(self, operation_scenario: pd.DataFrame):
        component_scenario_ids: Dict[str, int] = operation_scenario.loc[operation_scenario["ID_Scenario"] ==
                                                                        self.operation_scenario_id].iloc[0].to_dict()
        del component_scenario_ids["ID_Scenario"]
        for id_component, component_scenario_id in component_scenario_ids.items():
            component_info = OperationScenarioComponent.__dict__[id_component.replace("ID_", "")]
            if f'id_{component_info.name}' in self.__dict__.keys():
                setattr(self, f'id_{component_info.name}', component_scenario_id)

    def setup_operation_result_hour(self, df: pd.DataFrame):
        operation_result_hour: pd.DataFrame = df.loc[df["ID_Scenario"] == self.operation_scenario_id]
        for key in self.__dict__.keys():
            if key.endswith("_hour"):
                key_remove_tail = key[:-5]
                if key_remove_tail in operation_result_hour.columns:
                    self.__setattr__(key, operation_result_hour[key_remove_tail].to_numpy())

    def setup_operation_result_year(self, df: pd.DataFrame):
        operation_result_year: Dict[str, float] = df.loc[df["ID_Scenario"] ==
                                                         self.operation_scenario_id].iloc[0].to_dict()
        for key in self.__dict__.keys():
            if key.endswith("_year"):
                key_remove_tail = key[:-5]
                if key_remove_tail in operation_result_year.keys():
                    self.__setattr__(key, operation_result_year[key_remove_tail])
