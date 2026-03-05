from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.models.operation.component_registry import OperationScenarioComponent

_COMPONENTS = [
    OperationScenarioComponent.Building,
    OperationScenarioComponent.Boiler,
    OperationScenarioComponent.HeatingElement,
    OperationScenarioComponent.SpaceHeatingTank,
    OperationScenarioComponent.HotWaterTank,
    OperationScenarioComponent.SpaceCoolingTechnology,
    OperationScenarioComponent.PV,
    OperationScenarioComponent.Battery,
    OperationScenarioComponent.Vehicle,
    OperationScenarioComponent.EnergyPrice,
    OperationScenarioComponent.Behavior,
]

_HOUR_RESULT_FIELDS = ("PhotovoltaicProfile", "Grid", "Load", "Feed2Grid", "BatSoC")
_YEAR_RESULT_FIELDS = ("TotalCost",)


class Household:

    def __init__(self, operation_scenario_id):
        self.operation_scenario_id: int = operation_scenario_id
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
        row = operation_scenario.loc[operation_scenario["ID_Scenario"] == self.operation_scenario_id].iloc[0]
        for component_info in _COMPONENTS:
            attr = f"id_{component_info.name}"
            if not hasattr(self, attr):
                continue
            if component_info.id_name in row.index:
                setattr(self, attr, row[component_info.id_name])

    def setup_operation_result_hour(self, df: pd.DataFrame):
        operation_result_hour = df.loc[df["ID_Scenario"] == self.operation_scenario_id]
        for field in _HOUR_RESULT_FIELDS:
            if field in operation_result_hour.columns:
                setattr(self, f"{field}_hour", operation_result_hour[field].to_numpy())

    def setup_operation_result_year(self, df: pd.DataFrame):
        operation_result_year: Dict[str, float] = (
            df.loc[df["ID_Scenario"] == self.operation_scenario_id].iloc[0].to_dict()
        )
        for field in _YEAR_RESULT_FIELDS:
            if field in operation_result_year:
                setattr(self, f"{field}_year", operation_result_year[field])
