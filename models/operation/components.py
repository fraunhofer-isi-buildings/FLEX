from dataclasses import dataclass
from typing import Optional

import numpy as np


class OperationComponent:
    def set_params(self, params: dict):
        for param_name, param_value in params.items():
            if hasattr(self, param_name):
                setattr(self, param_name, param_value)


@dataclass
class Building(OperationComponent):
    Af: Optional[float] = None
    Hop: Optional[float] = None
    Htr_w: Optional[float] = None
    Hve: Optional[float] = None
    CM_factor: Optional[float] = None
    Am_factor: Optional[float] = None
    internal_gains: Optional[float] = None
    effective_window_area_west_east: Optional[float] = None
    effective_window_area_south: Optional[float] = None
    effective_window_area_north: Optional[float] = None
    grid_power_max: Optional[float] = None
    supply_temperature: Optional[float] = None
    person_num: Optional[int] = None
    appliance_electricity_demand_per_person: Optional[float] = None
    hot_water_demand_per_person: Optional[float] = None
    id_demand_profile_type: Optional[int] = None
    ventilation_heat_recovery: Optional[bool] = None


@dataclass
class Boiler(OperationComponent):
    type: Optional[str] = None
    carnot_efficiency_factor: Optional[float] = None
    fuel_boiler_efficiency: Optional[float] = None


@dataclass
class HeatingElement(OperationComponent):
    power: Optional[float] = None
    efficiency: Optional[float] = None


@dataclass
class SpaceHeatingTank(OperationComponent):
    size: Optional[float] = None
    loss: Optional[float] = None
    temperature_start: Optional[float] = None
    temperature_max: Optional[float] = None
    temperature_min: Optional[float] = None
    temperature_surrounding: Optional[float] = None


@dataclass
class HotWaterTank(OperationComponent):
    size: Optional[float] = None
    loss: Optional[float] = None
    temperature_start: Optional[float] = None
    temperature_max: Optional[float] = None
    temperature_min: Optional[float] = None
    temperature_surrounding: Optional[float] = None


@dataclass
class SpaceCoolingTechnology(OperationComponent):
    efficiency: Optional[float] = None
    power: Optional[float] = None


@dataclass
class PV(OperationComponent):
    size: Optional[float] = None
    generation: Optional[np.ndarray] = None
    orientation: Optional[str] = None


@dataclass
class Battery(OperationComponent):
    capacity: Optional[float] = None
    charge_efficiency: Optional[float] = None
    discharge_efficiency: Optional[float] = None
    charge_power_max: Optional[float] = None
    discharge_power_max: Optional[float] = None


@dataclass
class Vehicle(OperationComponent):
    capacity: Optional[float] = None
    consumption_rate: Optional[float] = None
    charge_efficiency: Optional[float] = None
    charge_power_max: Optional[float] = None
    discharge_efficiency: Optional[float] = None
    discharge_power_max: Optional[float] = None
    charge_bidirectional: Optional[float] = None
    id_parking_at_home_profile: Optional[int] = None
    id_distance_profile: Optional[int] = None


@dataclass
class EnergyPrice(OperationComponent):
    id_electricity: Optional[int] = None
    id_electricity_feed_in: Optional[int] = None
    id_solids: Optional[int] = None
    id_liquids: Optional[int] = None
    id_gases: Optional[int] = None
    id_district_heating: Optional[int] = None
    electricity: Optional[np.ndarray] = None
    electricity_feed_in: Optional[np.ndarray] = None
    solids: Optional[np.ndarray] = None
    liquids: Optional[np.ndarray] = None
    gases: Optional[np.ndarray] = None
    district_heating: Optional[np.ndarray] = None


@dataclass
class Behavior(OperationComponent):
    target_temperature_at_home_max: Optional[float] = None
    target_temperature_at_home_min: Optional[float] = None
    target_temperature_not_at_home_max: Optional[float] = None
    target_temperature_not_at_home_min: Optional[float] = None
    shading_solar_reduction_rate: Optional[float] = None
    shading_threshold_temperature: Optional[float] = None
    # initialized in the scenario setup process
    target_temperature_array_max: Optional[np.ndarray] = None
    target_temperature_array_min: Optional[np.ndarray] = None
    hot_water_demand: Optional[np.ndarray] = None
    appliance_electricity_demand: Optional[np.ndarray] = None
    vehicle_at_home: Optional[np.ndarray] = None
    vehicle_distance: Optional[np.ndarray] = None
    vehicle_demand: Optional[np.ndarray] = None
    ventilation_supply_temperature: Optional[np.ndarray] = None
