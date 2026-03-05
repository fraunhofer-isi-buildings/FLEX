from abc import ABC
import logging

import numpy as np
from typing import Union
from models.operation.boiler import classify_boiler_type
from models.operation.boiler import is_hp_boiler
from models.operation.boiler import normalize_boiler_type
from models.operation.rc_equations import mean_thermal_mass_temperature
from models.operation.rc_equations import next_thermal_mass_temperature
from models.operation.rc_equations import phi_m
from models.operation.rc_equations import phi_mtot
from models.operation.rc_equations import phi_st
from models.operation.rc_equations import room_temperature
from models.operation.rc_equations import surface_temperature
from models.operation.scenario import OperationScenario
from models.operation.time_defs import HOURS_PER_YEAR as OP_HOURS_PER_YEAR


class OperationModel(ABC):
    HOURS_PER_YEAR = OP_HOURS_PER_YEAR

    def __init__(self, scenario: "OperationScenario"):
        self.scenario = scenario
        self.CPWater = 4200 / 3600
        self.setup_operation_model_params()

    def setup_operation_model_params(self):
        self.setup_time_params()
        self.setup_region_params()
        self.setup_building_params()
        self.setup_space_heating_params()
        self.setup_hot_water_params()
        self.setup_space_cooling_params()
        self.setup_pv_params()
        self.setup_battery_params()
        self.setup_ev_params()
        self.setup_energy_price_params()
        self.setup_behavior_params()
        self.setup_heating_element_params()

    def setup_time_params(self):
        self.Hour = np.arange(1, self.HOURS_PER_YEAR + 1)
        self.DayHour = np.tile(np.arange(1, 25), self.HOURS_PER_YEAR // 24)

    def setup_region_params(self):
        self.T_outside = self.scenario.temperature  # °C
        self.Q_Solar = self.calculate_solar_gain()  # W

    def setup_building_params(self):
        """
        The thermal dynamics of building is modeled following...
        provide the link, so the equation numbers can make sense
        """
        self.Am = (self.scenario.building.Am_factor * self.scenario.building.Af)  # Effective mass related area [m^2]
        self.Cm = self.scenario.building.CM_factor * self.scenario.building.Af
        self.Atot = (4.5 * self.scenario.building.Af)  # 7.2.2.2: Area of all surfaces facing the building zone
        self.Qi = self.scenario.building.internal_gains * self.scenario.building.Af
        self.Htr_w = self.scenario.building.Htr_w
        self.Htr_ms = np.float_(9.1) * self.Am  # from 12.2.2 Equ. (64)
        self.Htr_is = np.float_(3.45) * self.Atot
        self.Htr_em = 1 / (1 / self.scenario.building.Hop - 1 / self.Htr_ms)  # from 12.2.2 Equ. (63)
        self.Htr_1 = np.float_(1) / (np.float_(1) / self.scenario.building.Hve + np.float_(1) / self.Htr_is)  # Equ. C.6
        self.Htr_2 = self.Htr_1 + self.scenario.building.Htr_w  # Equ. C.7
        self.Htr_3 = 1 / (1 / self.Htr_2 + 1 / self.Htr_ms)  # Equ.C.8
        self.Hve = self.scenario.building.Hve
        self.PHI_ia = 0.5 * self.Qi  # Equ. C.1
        _, _, _, mass_temperature = self.calculate_heating_and_cooling_demand(static=True)
        self.BuildingMassTemperatureStartValue = mass_temperature[-1]

        self.Q_RoomHeating, self.Q_RoomCooling, self.T_Room, self.T_BuildingMass = \
            self.calculate_heating_and_cooling_demand(thermal_start_temperature=self.BuildingMassTemperatureStartValue,
                                                      static=False)

    def setup_space_heating_params(self):
        logger = logging.getLogger(f"{self.scenario.config.project_name}")
        boiler_type = normalize_boiler_type(self.scenario.boiler.type)
        logger.info(
            "Scenario %s boiler setup: type=%s class=%s",
            self.scenario.scenario_id,
            boiler_type,
            classify_boiler_type(boiler_type),
        )
        if is_hp_boiler(boiler_type):
            self.SpaceHeatingHourlyCOP = self.calc_cop(
                outside_temperature=self.scenario.temperature,
                supply_temperature=self.scenario.building.supply_temperature,
                efficiency=self.scenario.boiler.carnot_efficiency_factor,
                source=boiler_type,
            )
            self.SpaceHeatingHourlyCOP_tank = self.calc_cop(
                outside_temperature=self.scenario.temperature,
                supply_temperature=self.scenario.building.supply_temperature + 10,
                efficiency=self.scenario.boiler.carnot_efficiency_factor,
                source=boiler_type,
            )
        else:
            self.SpaceHeatingHourlyCOP = np.ones(shape=self.HOURS_PER_YEAR)
            self.SpaceHeatingHourlyCOP_tank = np.ones(shape=self.HOURS_PER_YEAR)

        self.fuel_boiler_efficiency = self.scenario.boiler.fuel_boiler_efficiency
        self.T_TankStart_heating = self.scenario.space_heating_tank.temperature_start
        self.M_WaterTank_heating = self.scenario.space_heating_tank.size
        self.U_LossTank_heating = self.scenario.space_heating_tank.loss
        self.T_TankSurrounding_heating = (self.scenario.space_heating_tank.temperature_surrounding)
        self.A_SurfaceTank_heating = self.calculate_surface_area_from_volume(self.scenario.space_heating_tank.size)
        self.SpaceHeating_MaxBoilerPower = self.generate_maximum_electric_or_thermal_power()
        self.Q_TankEnergyMin_heating = self.CPWater * self.scenario.space_heating_tank.size * (273.15 + self.scenario.space_heating_tank.temperature_min)
        self.Q_TankEnergyMax_heating = self.CPWater * self.scenario.space_heating_tank.size * (273.15 + self.scenario.space_heating_tank.temperature_max)

    def setup_heating_element_params(self):
        self.HeatingElement_efficiency = self.scenario.heating_element.efficiency
        self.HeatingElement_power = self.scenario.heating_element.power

    def setup_hot_water_params(self):
        boiler_type = normalize_boiler_type(self.scenario.boiler.type)
        # Use the same centralized boiler technology for both SH and DHW.
        if is_hp_boiler(boiler_type):
            self.HotWaterHourlyCOP = self.calc_cop(
                outside_temperature=self.scenario.temperature,
                supply_temperature=self.scenario.building.supply_temperature,
                efficiency=self.scenario.boiler.carnot_efficiency_factor,
                source=boiler_type,
            )
            self.HotWaterHourlyCOP_tank = self.calc_cop(
                outside_temperature=self.scenario.temperature,
                supply_temperature=self.scenario.building.supply_temperature + 10,
                efficiency=self.scenario.boiler.carnot_efficiency_factor,
                source=boiler_type,
            )
        else:
            self.HotWaterHourlyCOP = np.ones(shape=self.HOURS_PER_YEAR)
            self.HotWaterHourlyCOP_tank = np.ones(shape=self.HOURS_PER_YEAR)

        self.T_TankStart_DHW = self.scenario.hot_water_tank.temperature_start
        self.M_WaterTank_DHW = self.scenario.hot_water_tank.size
        self.U_LossTank_DHW = self.scenario.hot_water_tank.loss
        self.T_TankSurrounding_DHW = self.scenario.hot_water_tank.temperature_surrounding
        self.A_SurfaceTank_DHW = self.calculate_surface_area_from_volume(self.scenario.hot_water_tank.size)
        self.Q_TankEnergyMin_DHW = self.CPWater * self.scenario.hot_water_tank.size * (273.15 + self.scenario.hot_water_tank.temperature_min)
        self.Q_TankEnergyMax_DHW = self.CPWater * self.scenario.hot_water_tank.size * (273.15 + self.scenario.hot_water_tank.temperature_max)

    def calculate_surface_area_from_volume(self, volume: float) -> float:
        # V = h * pi * r2 -> h = V/(r2*pi), A = 2r*pi*h + 2pi*r2 -> A = 2r*pi*V/(r2*pi) + 2pi*r2 = 2V/r + 2pi*r2
        # derivative of area: 0 = 4pi*r - 4V/r2  -> V = pi*r3  -> r = sqrt^3(V/pi)
        if volume == 0:
            return 0
        V = volume / 1_000  # from l into m^3
        r = np.cbrt(V / np.pi)
        h = V / (r ** 2 * np.pi)
        return np.round(2 * r * np.pi * h + 2 * np.pi * r ** 2, 2)

    def setup_space_cooling_params(self):
        self.CoolingCOP = self.scenario.space_cooling_technology.efficiency
        self.CoolingHourlyCOP = (np.ones(self.HOURS_PER_YEAR, ) * self.CoolingCOP)

    def setup_pv_params(self):
        self.PhotovoltaicProfile = self.scenario.pv.generation

    def setup_battery_params(self):
        self.ChargeEfficiency = self.scenario.battery.charge_efficiency
        self.DischargeEfficiency = self.scenario.battery.discharge_efficiency

    def setup_ev_params(self):
        self.EVDemandProfile = self.scenario.behavior.vehicle_demand
        self.EVAtHomeProfile = self.scenario.behavior.vehicle_at_home
        self.EVChargeEfficiency = self.scenario.vehicle.charge_efficiency
        self.EVDischargeEfficiency = self.scenario.vehicle.discharge_efficiency
        self.EVOptionV2B = self.scenario.vehicle.charge_bidirectional
        # if self.scenario.vehicle.capacity > 0:
        #     self.test_vehicle_profile()  # test if vehicle makes model infeasible

    def setup_energy_price_params(self):
        self.ElectricityPrice = self.scenario.energy_price.electricity  # C/Wh
        self.FiT = self.scenario.energy_price.electricity_feed_in  # C/Wh

    def setup_behavior_params(self):
        self.HotWaterProfile = self.scenario.behavior.hot_water_demand
        self.BaseLoadProfile = self.scenario.behavior.appliance_electricity_demand

    def calculate_heating_and_cooling_demand(
            self, thermal_start_temperature: float = 15, static=False
    ) -> (np.array, np.array, np.array, np.array):
        """
        if "static" is True, then the RC model will calculate a static heat demand calculation for the first hour of
        the year by using this hour 100 times. This way a good approximation of the thermal mass temperature of the
        building in the beginning of the calculation is achieved. Solar gains are set to 0.
        Returns: heating demand, cooling demand, indoor air temperature, temperature of the thermal mass
        """
        heating_power_10 = self.scenario.building.Af * 10

        if self.scenario.space_cooling_technology.power == 0:
            T_air_max = np.full((self.HOURS_PER_YEAR,), 100)
            # if no cooling is adopted --> raise max air temperature to 100 so it will never cool:
        else:
            T_air_max = self.scenario.behavior.target_temperature_array_max

        if static:
            Q_solar = np.array([0] * 100)
            T_outside = np.array([self.scenario.temperature[0]] * 100)
            T_air_min = np.array(
                [self.scenario.behavior.target_temperature_array_min[0]] * 100
            )
            time = np.arange(100)

            Tm_t = np.zeros(shape=(100,))  # thermal mass temperature
            T_sup = np.zeros(shape=(100,))
            heating_demand = np.zeros(shape=(100,))
            cooling_demand = np.zeros(shape=(100,))
            room_temperature = np.zeros(shape=(100,))

        else:
            Q_solar = self.Q_Solar
            T_outside = self.T_outside
            T_air_min = self.scenario.behavior.target_temperature_array_min
            time = np.arange(self.HOURS_PER_YEAR)

            Tm_t = np.zeros(shape=(self.HOURS_PER_YEAR,))  # thermal mass temperature
            T_sup = np.zeros(shape=(self.HOURS_PER_YEAR,))
            heating_demand = np.zeros(shape=(self.HOURS_PER_YEAR,))
            cooling_demand = np.zeros(shape=(self.HOURS_PER_YEAR,))
            room_temperature = np.zeros(shape=(self.HOURS_PER_YEAR,))

        am = self.Am
        atot = self.Atot
        qi = self.Qi
        htr_w = self.Htr_w
        htr_em = self.Htr_em
        htr_3 = self.Htr_3
        htr_2 = self.Htr_2
        htr_1 = self.Htr_1
        phi_ia = self.PHI_ia
        hve = self.Hve
        cm = self.Cm
        htr_ms = self.Htr_ms
        htr_is = self.Htr_is

        for t in time:
            t_sup = self.scenario.behavior.ventilation_supply_temperature[t]
            T_sup[t] = t_sup
            tm_prev = thermal_start_temperature if t == 0 else Tm_t[t - 1]
            phi_m_val = phi_m(am=am, atot=atot, qi=qi, q_solar=Q_solar[t])
            phi_st_val = phi_st(am=am, atot=atot, htr_w=htr_w, qi=qi, q_solar=Q_solar[t])

            tm_0, t_air_0 = self._rc_step(
                tm_prev=tm_prev,
                q_hc=0.0,
                t_sup=t_sup,
                t_outside=T_outside[t],
                phi_m_val=phi_m_val,
                phi_st_val=phi_st_val,
                cm=cm,
                htr_3=htr_3,
                htr_em=htr_em,
                htr_2=htr_2,
                htr_w=htr_w,
                htr_1=htr_1,
                phi_ia=phi_ia,
                hve=hve,
                htr_ms=htr_ms,
                htr_is=htr_is,
            )
            _, t_air_10 = self._rc_step(
                tm_prev=tm_prev,
                q_hc=heating_power_10,
                t_sup=t_sup,
                t_outside=T_outside[t],
                phi_m_val=phi_m_val,
                phi_st_val=phi_st_val,
                cm=cm,
                htr_3=htr_3,
                htr_em=htr_em,
                htr_2=htr_2,
                htr_w=htr_w,
                htr_1=htr_1,
                phi_ia=phi_ia,
                hve=hve,
                htr_ms=htr_ms,
                htr_is=htr_is,
            )
            _, t_air_10_c = self._rc_step(
                tm_prev=tm_prev,
                q_hc=-heating_power_10,
                t_sup=t_sup,
                t_outside=T_outside[t],
                phi_m_val=phi_m_val,
                phi_st_val=phi_st_val,
                cm=cm,
                htr_3=htr_3,
                htr_em=htr_em,
                htr_2=htr_2,
                htr_w=htr_w,
                htr_1=htr_1,
                phi_ia=phi_ia,
                hve=hve,
                htr_ms=htr_ms,
                htr_is=htr_is,
            )

            if T_air_min[t] <= t_air_0 <= T_air_max[t]:
                q_hc_real = 0.0
            elif t_air_0 < T_air_min[t]:
                heating_demand[t] = heating_power_10 * (T_air_min[t] - t_air_0) / (t_air_10 - t_air_0)
                q_hc_real = heating_demand[t]
            else:
                cooling_demand[t] = heating_power_10 * (T_air_max[t] - t_air_0) / (t_air_10_c - t_air_0)
                q_hc_real = -cooling_demand[t]

            tm_real, t_air_real = self._rc_step(
                tm_prev=tm_prev,
                q_hc=q_hc_real,
                t_sup=t_sup,
                t_outside=T_outside[t],
                phi_m_val=phi_m_val,
                phi_st_val=phi_st_val,
                cm=cm,
                htr_3=htr_3,
                htr_em=htr_em,
                htr_2=htr_2,
                htr_w=htr_w,
                htr_1=htr_1,
                phi_ia=phi_ia,
                hve=hve,
                htr_ms=htr_ms,
                htr_is=htr_is,
            )
            Tm_t[t] = tm_real
            room_temperature[t] = t_air_real

        return heating_demand, cooling_demand, room_temperature, Tm_t

    @staticmethod
    def _rc_step(
        tm_prev: float,
        q_hc: float,
        t_sup: float,
        t_outside: float,
        phi_m_val: float,
        phi_st_val: float,
        cm: float,
        htr_3: float,
        htr_em: float,
        htr_2: float,
        htr_w: float,
        htr_1: float,
        phi_ia: float,
        hve: float,
        htr_ms: float,
        htr_is: float,
    ) -> tuple[float, float]:
        phi_mtot_val = phi_mtot(
            phi_m_val=phi_m_val,
            htr_em=htr_em,
            t_outside=t_outside,
            htr_3=htr_3,
            phi_st_val=phi_st_val,
            htr_w=htr_w,
            htr_1=htr_1,
            phi_ia=phi_ia,
            q_hc=q_hc,
            hve=hve,
            t_sup=t_sup,
            htr_2=htr_2,
        )
        tm_now = next_thermal_mass_temperature(
            tm_prev=tm_prev,
            cm=cm,
            htr_3=htr_3,
            htr_em=htr_em,
            phi_mtot_val=phi_mtot_val,
        )
        t_m = mean_thermal_mass_temperature(tm_now=tm_now, tm_prev=tm_prev)
        t_s = surface_temperature(
            htr_ms=htr_ms,
            t_m=t_m,
            phi_st_val=phi_st_val,
            htr_w=htr_w,
            t_outside=t_outside,
            htr_1=htr_1,
            t_sup=t_sup,
            phi_ia=phi_ia,
            q_hc=q_hc,
            hve=hve,
        )
        t_air = room_temperature(
            htr_is=htr_is,
            t_s=t_s,
            hve=hve,
            t_sup=t_sup,
            phi_ia=phi_ia,
            q_hc=q_hc,
        )
        return tm_now, t_air

    def generate_target_indoor_temperature(self, temperature_offset: Union[int, float]) -> (np.array, np.array):
        """
        This function modifies the exogenous target temperature range, so that
        1. the building will not be pre-heated (or pre-cooled) to too-high (or too-low) temperature;
        2. the optimization will not be infeasible if the building is heated above maximum temperature by radiation.

        Args:
            temperature_offset: int or float, temperature the optimization can pre-heat or pre-cool the building

        Returns: array of the maximum temperature, array of minimum temperature
        """
        indoor_temp = self.T_Room
        target_min = self.scenario.behavior.target_temperature_array_min
        target_max = self.scenario.behavior.target_temperature_array_max
        temperature_max_winter = target_min + temperature_offset
        within_base_band = (indoor_temp >= temperature_max_winter) & (indoor_temp <= target_max + 0.01)

        max_temperature = indoor_temp + temperature_offset
        min_temperature = indoor_temp - temperature_offset
        low_mask = indoor_temp < temperature_max_winter
        min_temperature[low_mask] = target_min[low_mask]

        if self.scenario.space_cooling_technology.power > 0:
            max_temperature[within_base_band] = target_max[within_base_band]

        return max_temperature, min_temperature

    @staticmethod
    def calc_cop(
            outside_temperature: np.array,
            supply_temperature: float,
            efficiency: float,
            source: str,
    ) -> np.array:
        """
        Args:
            outside_temperature:
            supply_temperature: temperature that the heating system needs (eg. 35 low temperature, 65 hot)
            efficiency: carnot efficiency factor
            source: refers to the heat source (air, ground...) is saved in the boiler class as "name"

        Returns: numpy array of the hourly COP
        """
        source = normalize_boiler_type(source)
        if source == "air_hp":
            COP = np.array(
                [
                    efficiency
                    * (supply_temperature + 273.15)
                    / (supply_temperature - temp)
                    for temp in outside_temperature
                ]
            )
        elif source == "ground_hp":
            # for the ground source heat pump the temperature of the source is 10°C
            COP = np.array(
                [
                    efficiency
                    * (supply_temperature + 273.15)
                    / (supply_temperature - 10)
                    for temp in outside_temperature
                ]
            )
        elif source == "electric":
            COP = np.ones(shape=len(outside_temperature))
        else:
            raise ValueError(
                f"calc_cop only supports electric heating techs {['air_hp', 'ground_hp', 'electric']}. "
                f"Got source='{source}'."
            )
        # check maximum COP, COP should not go to infinity for high outside temperatures
        COP[COP > 18] = 18
        # check minimum COP, COP can not be lower than 1
        COP[COP < 1] = 1
        return COP

    def generate_maximum_electric_or_thermal_power(self) -> float:
        """
        Calculates the necessary HP power for each building through the 5R1C reference model.
        The maximum heating power then will be rounded to the next 500 W.
        Then we divide the thermal power by the worst COP of the HP which is calculated at design conditions
        (coldest day) and the respective source and supply temperature. For conventional boilers the thermal power
        is provided as output
        """
        # calculate the heating demand in reference mode:
        max_heating_demand = self.Q_RoomHeating.max()
        max_dhw_demand = self.scenario.behavior.hot_water_demand.max()
        # round to the next 500 W
        max_thermal_power = np.ceil((max_heating_demand + max_dhw_demand) / 500) * 500
        # distinguish between electric heating systems and conventional ones:
        boiler_type = normalize_boiler_type(self.scenario.boiler.type)
        if is_hp_boiler(boiler_type):
            # calculate the design condition COP
            worst_COP = OperationModel.calc_cop(
                outside_temperature=[min(self.scenario.temperature)],  # get coldest hour of the year
                supply_temperature=self.scenario.building.supply_temperature,
                efficiency=self.scenario.boiler.carnot_efficiency_factor,
                source=boiler_type,
            )
            max_electric_power_float = max_thermal_power / worst_COP
            # round the maximum electric power to the next 100 W:
            max_electric_power = np.ceil(max_electric_power_float[0] / 100) * 100
            return max_electric_power
        else:
            # if the heating system is conventional the carnot efficiency factor of the system is treated as the
            # efficiency of the system itself:
            max_thermal_power_float = max_thermal_power / self.scenario.boiler.carnot_efficiency_factor
            # round the maximum electric power to the next 100 W:
            max_thermal_power = np.ceil(max_thermal_power_float / 100) * 100
            return max_thermal_power

    def generate_solar_gain_rate(self):
        outside_temperature = self.scenario.temperature
        shading_threshold_temperature = self.scenario.behavior.shading_threshold_temperature
        shading_solar_reduction_rate = self.scenario.behavior.shading_solar_reduction_rate
        return np.where(
            outside_temperature >= shading_threshold_temperature,
            1 - shading_solar_reduction_rate,
            1.0,
        )

    def calculate_solar_gain(self) -> np.array:
        """return: 8760h solar gains, calculated with solar radiation and the effective window area."""

        area_window_east_west = self.scenario.building.effective_window_area_west_east
        area_window_south = self.scenario.building.effective_window_area_south
        area_window_north = self.scenario.building.effective_window_area_north

        Q_solar_north = np.outer(np.array(self.scenario.radiation_north), area_window_north)
        Q_solar_east = np.outer(np.array(self.scenario.radiation_east), area_window_east_west / 2)
        Q_solar_south = np.outer(np.array(self.scenario.radiation_south), area_window_south)
        Q_solar_west = np.outer(np.array(self.scenario.radiation_west), area_window_east_west / 2)

        solar_gain_rate = self.generate_solar_gain_rate()
        Q_solar = (Q_solar_north + Q_solar_south + Q_solar_east + Q_solar_west).squeeze() * solar_gain_rate
        return Q_solar

    def create_upper_bound_ev_discharge(self) -> np.array:
        """
        Returns: array that limits the discharge of the EV when it is at home and can use all capacity in one hour
        when not at home (unlimited if not at home because this is endogenously derived)
        """
        at_home = np.round(self.scenario.behavior.vehicle_at_home).astype(int) == 1
        return np.where(
            at_home,
            self.scenario.vehicle.discharge_power_max,
            self.scenario.vehicle.capacity,
        )

    def test_vehicle_profile(self) -> None:
        # test if the vehicle driving profile can be achieved by vehicle capacity:
        counter = 0
        for i, status in enumerate(self.scenario.behavior.vehicle_at_home):
            # add vehicle demand while driving up:
            if round(status) == 0:
                counter += self.scenario.behavior.vehicle_demand[i]
                # check if counter exceeds capacity:
                assert counter <= self.scenario.vehicle.capacity, (
                    "the driving profile exceeds the total capacity of "
                    "the EV. The EV will run out of electricity before "
                    "returning home."
                )
            else:  # vehicle returns home -> counter is set to 0
                counter = 0
