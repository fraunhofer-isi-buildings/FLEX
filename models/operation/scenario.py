from dataclasses import dataclass
from typing import Optional, Dict

import numpy as np
import pandas as pd

from models.operation.components import Battery
from models.operation.components import Behavior
from models.operation.components import Boiler
from models.operation.components import Building
from models.operation.components import EnergyPrice
from models.operation.components import HeatingElement
from models.operation.components import HotWaterTank
from models.operation.components import PV
from models.operation.components import SpaceCoolingTechnology
from models.operation.components import SpaceHeatingTank
from models.operation.components import Vehicle
from models.operation.boiler import normalize_boiler_type
from models.operation.component_registry import OperationScenarioComponent
from models.operation.time_defs import HOURS_PER_YEAR as OP_HOURS_PER_YEAR
from utils.config import Config
from utils.tables import InputTables


@dataclass(eq=False)
class OperationScenario:
    HOURS_PER_YEAR = OP_HOURS_PER_YEAR
    ENERGY_PRICE_CARRIERS = (
        "electricity",
        "electricity_feed_in",
        "solids",
        "liquids",
        "gases",
        "district_heating",
    )
    config: "Config"
    scenario_id: int
    input_tables: Optional[Dict[str, pd.DataFrame]]
    input_indexes: Optional[Dict[str, Dict[int, dict]]] = None
    building: Optional["Building"] = None
    boiler: Optional["Boiler"] = None
    space_heating_tank: Optional["SpaceHeatingTank"] = None
    hot_water_tank: Optional["HotWaterTank"] = None
    space_cooling_technology: Optional["SpaceCoolingTechnology"] = None
    pv: Optional["PV"] = None
    battery: Optional["Battery"] = None
    vehicle: Optional["Vehicle"] = None
    energy_price: Optional["EnergyPrice"] = None
    behavior: Optional["Behavior"] = None
    heating_element: Optional["HeatingElement"] = None
    temperature: Optional[np.ndarray] = None
    radiation_north: Optional[np.ndarray] = None
    radiation_south: Optional[np.ndarray] = None
    radiation_east: Optional[np.ndarray] = None
    radiation_west: Optional[np.ndarray] = None

    def __post_init__(self):
        if self.input_indexes is None:
            self.input_indexes = self.build_input_indexes(self.input_tables)
        self.setup_components()
        self.validate_required_components()
        self.setup_region_weather_and_pv_generation()
        self.setup_energy_price()
        self.setup_behavior()

    @staticmethod
    def build_input_indexes(input_tables: Dict[str, pd.DataFrame]) -> Dict[str, Dict[int, dict]]:
        indexes: Dict[str, Dict[int, dict]] = {}
        scenario_table = input_tables[InputTables.OperationScenario.name]
        indexes[InputTables.OperationScenario.name] = (
            scenario_table.set_index("ID_Scenario").to_dict(orient="index")
        )
        for name, value in vars(OperationScenarioComponent).items():
            if name.startswith("_"):
                continue
            component_info = getattr(OperationScenarioComponent, name, None)
            if component_info is None:
                continue
            df = input_tables[component_info.table_name]
            indexes[component_info.table_name] = (
                df.set_index(component_info.id_name).to_dict(orient="index")
            )
        return indexes

    def get_component_scenario_ids(self) -> dict:
        row = self.input_indexes[InputTables.OperationScenario.name].get(self.scenario_id)
        if row is None:
            raise ValueError(f"Scenario {self.scenario_id} not found in OperationScenario.")
        return {k: v for k, v in row.items() if k.startswith("ID_")}

    def setup_components(self):
        component_ids = self.get_component_scenario_ids()
        for id_component, component_scenario_id in component_ids.items():
            component_info = getattr(OperationScenarioComponent, id_component.replace("ID_", ""), None)
            if component_info is None:
                continue
            if hasattr(self, component_info.name):
                row = self.input_indexes[component_info.table_name].get(int(component_scenario_id))
                if row is None:
                    raise ValueError(
                        f"{component_info.table_name}.{component_info.id_name}={component_scenario_id} "
                        f"not found for scenario {self.scenario_id}."
                    )
                instance = component_info.class_var()
                instance.set_params(row)
                if component_info.name == "boiler" and getattr(instance, "type", None) is not None:
                    instance.type = normalize_boiler_type(instance.type)
                setattr(self, component_info.name, instance)

    def validate_required_components(self):
        required = [
            "building",
            "boiler",
            "space_heating_tank",
            "hot_water_tank",
            "space_cooling_technology",
            "pv",
            "battery",
            "vehicle",
            "energy_price",
            "behavior",
            "heating_element",
        ]
        missing = [name for name in required if getattr(self, name) is None]
        if missing:
            raise ValueError(
                f"Scenario {self.scenario_id} is missing required components: {missing}"
            )

    def setup_region_weather_and_pv_generation(self):
        df = self.input_tables[InputTables.OperationScenario_RegionWeather.name]
        self.temperature = df["temperature"].to_numpy()
        self.radiation_north = df["radiation_north"].to_numpy()
        self.radiation_south = df["radiation_south"].to_numpy()
        self.radiation_east = df["radiation_east"].to_numpy()
        self.radiation_west = df["radiation_west"].to_numpy()
        self.pv.generation = df[f"pv_generation_{self.pv.orientation}"].to_numpy() * self.pv.size

    def setup_energy_price(self):
        profile_table_name = OperationScenarioComponent.EnergyPrice.profile_table_name
        if profile_table_name is None:
            profile_table_name = InputTables.OperationScenario_EnergyPrice.name
        df = self.input_tables[profile_table_name]
        for carrier in self.ENERGY_PRICE_CARRIERS:
            id_attr = f"id_{carrier}"
            value = getattr(self.energy_price, id_attr, None)
            if value is None:
                continue
            energy_price_column = f"{carrier}_{value}"
            if energy_price_column not in df.columns:
                raise ValueError(
                    f"Energy price column '{energy_price_column}' not found for scenario {self.scenario_id}."
                )
            setattr(self.energy_price, carrier, df[energy_price_column].to_numpy())

    def setup_behavior(self):
        behavior_df = self.input_tables[InputTables.OperationScenario_BehaviorProfile.name]
        self.behavior.appliance_electricity_demand = self.setup_appliance_electricity_demand_profile(behavior_df)
        self.behavior.hot_water_demand = self.setup_hot_water_demand_profile(behavior_df)
        self.setup_target_temperature(behavior_df)
        self.setup_ventilation_supply_temperature(behavior_df)
        self.setup_driving_profiles()

    def setup_appliance_electricity_demand_profile(self, behavior_df: pd.DataFrame):
        shape = behavior_df[f'appliance_electricity_dpt{self.building.id_demand_profile_type}'].to_numpy()
        shape_sum = shape.sum()
        annual_demand = (
            self.building.appliance_electricity_demand_per_person * self.building.person_num
        )
        return annual_demand * shape / shape_sum

    def setup_hot_water_demand_profile(self, behavior_df: pd.DataFrame):
        shape = behavior_df[f'hot_water_dpt{self.building.id_demand_profile_type}'].to_numpy()
        shape_sum = shape.sum()
        annual_demand = (
            self.building.hot_water_demand_per_person * self.building.person_num
        )
        return annual_demand * shape / shape_sum

    def setup_target_temperature(self, behavior: pd.DataFrame):
        column = f"occupancy_dpt{self.building.id_demand_profile_type}"
        at_home = behavior[column].to_numpy()
        at_home_mask = at_home == 1
        (
            self.behavior.target_temperature_array_max,
            self.behavior.target_temperature_array_min,
        ) = (
            np.where(
                at_home_mask,
                self.behavior.target_temperature_at_home_max,
                self.behavior.target_temperature_not_at_home_max,
            ),
            np.where(
                at_home_mask,
                self.behavior.target_temperature_at_home_min,
                self.behavior.target_temperature_not_at_home_min,
            ),
        )

    def setup_ventilation_supply_temperature(self, behavior: pd.DataFrame):
        if self.building.ventilation_heat_recovery:
            self.behavior.ventilation_supply_temperature = behavior[f'ventilation_supply_temperature_dpt{self.building.id_demand_profile_type}'].to_numpy()
        else:
            self.behavior.ventilation_supply_temperature = self.temperature

    def setup_driving_profiles(self):
        parking_home = self.input_tables[InputTables.OperationScenario_DrivingProfile_ParkingHome.name]
        distance = self.input_tables[InputTables.OperationScenario_DrivingProfile_Distance.name]

        if self.vehicle.capacity == 0:
            self.behavior.vehicle_at_home = np.zeros((self.HOURS_PER_YEAR,))
            self.behavior.vehicle_distance = np.zeros((self.HOURS_PER_YEAR,))
            self.behavior.vehicle_demand = np.zeros((self.HOURS_PER_YEAR,))
        else:
            self.behavior.vehicle_at_home = parking_home[str(self.vehicle.id_parking_at_home_profile)].to_numpy()
            self.behavior.vehicle_distance = distance[str(self.vehicle.id_distance_profile)].to_numpy()
            self.behavior.vehicle_demand = self.behavior.vehicle_distance * self.vehicle.consumption_rate
