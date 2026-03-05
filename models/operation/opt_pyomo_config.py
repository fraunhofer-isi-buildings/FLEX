from dataclasses import dataclass
from typing import TYPE_CHECKING

from models.operation.boiler import is_hp_boiler
from models.operation.boiler import normalize_boiler_type
from models.operation.time_defs import HOURS_PER_YEAR as OP_HOURS_PER_YEAR

if TYPE_CHECKING:
    from models.operation.physics_model import OperationModel


@dataclass(frozen=True)
class ScenarioFlags:
    uses_hp: bool
    has_heating_element: bool
    has_space_heating_tank: bool
    has_hot_water_tank: bool
    has_battery: bool
    has_ev: bool
    has_pv: bool
    has_cooling: bool
    ev_v2b_enabled: bool

    @classmethod
    def from_model(cls, model: "OperationModel") -> "ScenarioFlags":
        scenario = model.scenario
        return cls(
            uses_hp=is_hp_boiler(scenario.boiler.type),
            has_heating_element=model.HeatingElement_power > 0,
            has_space_heating_tank=scenario.space_heating_tank.size > 0,
            has_hot_water_tank=scenario.hot_water_tank.size > 0,
            has_battery=scenario.battery.capacity > 0,
            has_ev=scenario.vehicle.capacity > 0,
            has_pv=scenario.pv.size > 0,
            has_cooling=scenario.space_cooling_technology.power > 0,
            ev_v2b_enabled=model.EVOptionV2B != 0,
        )


class OptConfig:
    HOURS_PER_YEAR = OP_HOURS_PER_YEAR

    def __init__(self, model: 'OperationModel'):
        self.model = model
        self.scenario = model.scenario
        self.flags = ScenarioFlags.from_model(model)
        self._hours_index = tuple(range(1, self.HOURS_PER_YEAR + 1))

    def _hours(self):
        return self._hours_index

    @staticmethod
    def _components(instance, names):
        return [getattr(instance, name) for name in names]

    def _fix_vars(self, instance, var_names, value=0):
        for var in self._components(instance, var_names):
            for var_data in var.values():
                var_data.fix(value)

    def _unfix_vars(self, instance, var_names):
        for var in self._components(instance, var_names):
            for var_data in var.values():
                var_data.fixed = False

    def _set_upper_bounds(self, instance, upper_bounds: dict):
        for var_name, ub in upper_bounds.items():
            var = getattr(instance, var_name)
            for var_data in var.values():
                var_data.setub(ub)

    def _set_lower_bounds(self, instance, lower_bounds: dict):
        for var_name, lb in lower_bounds.items():
            var = getattr(instance, var_name)
            for var_data in var.values():
                var_data.setlb(lb)

    def _set_bounds(self, instance, bounds: dict):
        for var_name, (lb, ub) in bounds.items():
            var = getattr(instance, var_name)
            for var_data in var.values():
                var_data.setlb(lb)
                var_data.setub(ub)

    @staticmethod
    def _to_indexed_dict(values):
        return {idx: val for idx, val in enumerate(values, start=1)}

    def _store_param_values(self, instance, param_name: str, values):
        getattr(instance, param_name).store_values(self._to_indexed_dict(values))

    @staticmethod
    def _set_rules_active(instance, rule_names, active: bool):
        for rule_name in rule_names:
            rule = getattr(instance, rule_name)
            if active:
                rule.activate()
            else:
                rule.deactivate()

    # @performance_counter
    def config_instance(self, instance):
        self.config_room_temperature(instance)
        self.config_vehicle(instance)
        self.config_static_params(instance)
        self.config_external_params(instance)
        self.config_prices(instance)
        # self.config_grid(instance)
        self.config_space_heating(instance)
        self.config_space_heating_tank(instance)
        self.config_hot_water_tank(instance)
        self.config_battery(instance)
        self.config_space_cooling_technology(instance)
        self.config_pv(instance)
        self.config_heating_element(instance)
        return instance

    def config_static_params(self, instance):
        instance.CPWater = self.model.CPWater
        # building parameters:
        # Use effective mass area (m2) to match 5R1C formulation used in physics_model.
        instance.Am = self.model.Am
        instance.Hve = self.scenario.building.Hve
        instance.Htr_w = self.scenario.building.Htr_w
        # parameters that have to be calculated:
        instance.Atot = self.model.Atot
        instance.Qi = self.model.Qi
        instance.Htr_em = self.model.Htr_em
        instance.Htr_3 = self.model.Htr_3
        instance.Htr_1 = self.model.Htr_1
        instance.Htr_2 = self.model.Htr_2
        instance.Htr_ms = self.model.Htr_ms
        instance.Htr_is = self.model.Htr_is
        instance.PHI_ia = self.model.PHI_ia
        instance.Cm = self.model.Cm
        instance.BuildingMassTemperatureStartValue = self.model.BuildingMassTemperatureStartValue

        # Battery parameters
        instance.BatteryChargeEfficiency = self.scenario.battery.charge_efficiency
        instance.BatteryDischargeEfficiency = self.scenario.battery.discharge_efficiency

        # EV parameters
        instance.EVChargeEfficiency = self.scenario.vehicle.charge_efficiency
        instance.EVDischargeEfficiency = self.scenario.vehicle.discharge_efficiency
        instance.EVCapacity = self.scenario.vehicle.capacity

        # Thermal storage heating parameters
        instance.T_TankStart_heating = self.scenario.space_heating_tank.temperature_start
        instance.M_WaterTank_heating = self.scenario.space_heating_tank.size
        instance.U_LossTank_heating = self.scenario.space_heating_tank.loss
        instance.T_TankSurrounding_heating = self.scenario.space_heating_tank.temperature_surrounding
        instance.A_SurfaceTank_heating = self.model.A_SurfaceTank_heating

        # Thermal storage DHW parameters
        instance.T_TankStart_DHW = self.scenario.hot_water_tank.temperature_start
        instance.M_WaterTank_DHW = self.scenario.hot_water_tank.size
        instance.U_LossTank_DHW = self.scenario.hot_water_tank.loss
        instance.T_TankSurrounding_DHW = self.scenario.hot_water_tank.temperature_surrounding
        instance.A_SurfaceTank_DHW = self.model.A_SurfaceTank_DHW

        # HP
        instance.SpaceHeating_MaxBoilerPower = self.model.SpaceHeating_MaxBoilerPower

        # Boiler
        instance.Boiler_COP = self.model.fuel_boiler_efficiency
        instance.Boiler_MaximalThermalPower = self.model.SpaceHeating_MaxBoilerPower

    def config_external_params(self, instance):
        self._store_param_values(instance, "Q_Solar", self.model.Q_Solar)
        self._store_param_values(instance, "T_outside", self.model.T_outside)
        self._store_param_values(instance, "HotWaterProfile", self.model.HotWaterProfile)
        self._store_param_values(instance, "BaseLoadProfile", self.model.BaseLoadProfile)
        self._store_param_values(instance, "PhotovoltaicProfile", self.model.PhotovoltaicProfile)
        self._store_param_values(
            instance,
            "VentilationSupplyTemperature",
            self.scenario.behavior.ventilation_supply_temperature,
        )

        if self.flags.uses_hp:
            self._store_param_values(instance, "SpaceHeatingHourlyCOP", self.model.SpaceHeatingHourlyCOP)
            self._store_param_values(instance, "SpaceHeatingHourlyCOP_tank", self.model.SpaceHeatingHourlyCOP_tank)
            self._store_param_values(instance, "HotWaterHourlyCOP", self.model.HotWaterHourlyCOP)
            self._store_param_values(instance, "HotWaterHourlyCOP_tank", self.model.HotWaterHourlyCOP_tank)
            for t in self._hours():
                # unfix heat pump parameters:
                instance.E_Heating_HP_out[t].fixed = False
                instance.E_DHW_HP_out[t].fixed = False

                # set boiler specifics to zero
                instance.Fuel[t].fix(0)
                instance.Q_DHW_Boiler_out[t].fix(0)
                instance.Q_Heating_Boiler_out[t].fix(0)

            # deactivate boiler functions
            self._set_rules_active(
                instance,
                [
                    "boiler_conversion_rule",
                    "max_fuel_boiler_power_rule",
                    "bypass_DHW_fuel_boiler_rule",
                    "calc_use_of_fuel_boiler_power_DHW_rule",
                ],
                active=False,
            )
            # activate heat pump functions
            self._set_rules_active(
                instance,
                [
                    "max_HP_power_rule",
                    "bypass_DHW_HP_rule",
                    "calc_use_of_HP_power_DHW_rule",
                ],
                active=True,
            )

        else:  # fuel based boiler instead of heat pump
            self._store_param_values(instance, "HotWaterHourlyCOP_tank", [0.0] * self.HOURS_PER_YEAR)
            self._store_param_values(instance, "HotWaterHourlyCOP", [0.0] * self.HOURS_PER_YEAR)
            self._store_param_values(instance, "SpaceHeatingHourlyCOP", [0.0] * self.HOURS_PER_YEAR)
            self._store_param_values(instance, "SpaceHeatingHourlyCOP_tank", [0.0] * self.HOURS_PER_YEAR)
            for t in self._hours():
                # unfix boiler parameters:
                instance.Fuel[t].fixed = False
                instance.Q_DHW_Boiler_out[t].fixed = False
                instance.Q_Heating_Boiler_out[t].fixed = False

                # fix heat pump parameters
                instance.E_Heating_HP_out[t].fix(0)
                instance.E_DHW_HP_out[t].fix(0)

            # activate boiler functions
            self._set_rules_active(
                instance,
                [
                    "boiler_conversion_rule",
                    "max_fuel_boiler_power_rule",
                    "bypass_DHW_fuel_boiler_rule",
                    "calc_use_of_fuel_boiler_power_DHW_rule",
                ],
                active=True,
            )
            # deactivate heat pump functions
            self._set_rules_active(
                instance,
                [
                    "max_HP_power_rule",
                    "bypass_DHW_HP_rule",
                    "calc_use_of_HP_power_DHW_rule",
                ],
                active=False,
            )

    def config_heating_element(self, instance):
        if self.model.HeatingElement_efficiency > 0:
            instance.HeatingElement_efficiency = self.model.HeatingElement_efficiency
        else:
            instance.HeatingElement_efficiency = 1  # to avoid that the model cant run
        if not self.flags.has_heating_element:
            self._fix_vars(
                instance,
                ["Q_HeatingElement", "Q_HeatingElement_heat", "Q_HeatingElement_DHW"],
                value=0,
            )
            instance.heating_element_rule.deactivate()
        else:
            self._set_upper_bounds(
                instance,
                {
                    "Q_HeatingElement": self.model.HeatingElement_power,
                    "Q_HeatingElement_heat": self.model.HeatingElement_power,
                    "Q_HeatingElement_DHW": self.model.HeatingElement_power,
                },
            )
            instance.heating_element_rule.activate()

    def config_prices(self, instance):
        self._store_param_values(instance, "ElectricityPrice", self.scenario.energy_price.electricity)
        self._store_param_values(instance, "FiT", self.scenario.energy_price.electricity_feed_in)
        if not self.flags.uses_hp:
            fuel_carrier = normalize_boiler_type(self.scenario.boiler.type)
            fuel_prices = getattr(self.scenario.energy_price, fuel_carrier)
        else:
            fuel_prices = [0.0] * self.HOURS_PER_YEAR
        self._store_param_values(instance, "FuelPrice", fuel_prices)

    def config_grid(self, instance):
        for t in self._hours():
            instance.Grid[t].setub(self.scenario.building.grid_power_max)
            instance.Feed2Grid[t].setub(self.scenario.building.grid_power_max)

    def config_space_heating(self, instance):
        if self.flags.uses_hp:
            for var_data in instance.E_Heating_HP_out.values():
                var_data.setub(self.model.SpaceHeating_MaxBoilerPower)
        else:
            for q_heat, q_dhw in zip(instance.Q_Heating_Boiler_out.values(), instance.Q_DHW_Boiler_out.values()):
                q_heat.setub(self.model.SpaceHeating_MaxBoilerPower)
                q_dhw.setub(self.model.SpaceHeating_MaxBoilerPower)

    def config_space_heating_tank(self, instance):
        if not self.flags.has_space_heating_tank:
            self._set_bounds(
                instance,
                {"Q_HeatingTank": (0, 0)},
            )
            self._fix_vars(instance, ["Q_HeatingTank_out", "Q_HeatingTank_in", "Q_HeatingTank"], value=0)

            instance.tank_energy_rule_heating.deactivate()
        else:
            self._unfix_vars(instance, ["Q_HeatingTank_out", "Q_HeatingTank_in", "Q_HeatingTank"])
            self._set_bounds(
                instance,
                {
                    "Q_HeatingTank": (
                        self.model.CPWater * self.scenario.space_heating_tank.size *
                        (273.15 + self.scenario.space_heating_tank.temperature_min),
                        self.model.CPWater * self.scenario.space_heating_tank.size *
                        (273.15 + self.scenario.space_heating_tank.temperature_max),
                    )
                },
            )
            instance.tank_energy_rule_heating.activate()

    def config_hot_water_tank(self, instance):
        if not self.flags.has_hot_water_tank:
            self._set_bounds(instance, {"Q_DHWTank": (0, 0)})
            self._fix_vars(instance, ["Q_DHWTank_out", "Q_DHWTank_in", "Q_DHWTank"], value=0)
            self._set_upper_bounds(instance, {"E_DHW_HP_out": self.model.SpaceHeating_MaxBoilerPower})  # TODO
            instance.tank_energy_rule_DHW.deactivate()
        else:
            self._unfix_vars(instance, ["Q_DHWTank_out", "Q_DHWTank_in", "Q_DHWTank"])
            self._set_bounds(
                instance,
                {
                    "Q_DHWTank": (
                        self.model.CPWater * self.scenario.hot_water_tank.size *
                        (273.15 + self.scenario.hot_water_tank.temperature_min),
                        self.model.CPWater * self.scenario.hot_water_tank.size *
                        (273.15 + self.scenario.hot_water_tank.temperature_max),
                    )
                },
            )
            self._set_upper_bounds(instance, {"E_DHW_HP_out": self.model.SpaceHeating_MaxBoilerPower})
            instance.tank_energy_rule_DHW.activate()

    def config_battery(self, instance):
        if not self.flags.has_battery:
            self._fix_vars(
                instance,
                ["Grid2Bat", "Bat2Load", "BatSoC", "BatCharge", "BatDischarge", "PV2Bat"],
                value=0,
            )
            instance.BatCharge_rule.deactivate()
            instance.BatDischarge_rule.deactivate()
            instance.BatSoC_rule.deactivate()
        else:
            # check if pv exists:
            if self.flags.has_pv:
                for t in self._hours():
                    instance.PV2Bat[t].fixed = False
                    instance.PV2Bat[t].setub(self.scenario.battery.charge_power_max)
            else:
                self._fix_vars(instance, ["PV2Bat"], value=0)

            # variables have to be unfixed in case they were fixed in a previous run
            self._unfix_vars(
                instance,
                ["Grid2Bat", "Bat2Load", "BatSoC", "BatCharge", "BatDischarge"],
            )
            self._set_upper_bounds(
                instance,
                {
                    "Grid2Bat": self.scenario.battery.charge_power_max,
                    "Bat2Load": self.scenario.battery.discharge_power_max,
                    "BatSoC": self.scenario.battery.capacity,
                    "BatCharge": self.scenario.battery.charge_power_max,
                    "BatDischarge": self.scenario.battery.discharge_power_max,
                },
            )
            instance.BatCharge_rule.activate()
            instance.BatDischarge_rule.activate()
            instance.BatSoC_rule.activate()

    def config_room_temperature(self, instance):
        # in winter only 3°C increase to keep comfort level and in summer maximum reduction of 3°C
        max_target_temperature, min_target_temperature = self.model.generate_target_indoor_temperature(
            temperature_offset=3)
        for t_room, ub, lb in zip(instance.T_Room.values(), max_target_temperature, min_target_temperature):
            t_room.setub(float(ub))
            t_room.setlb(float(lb))

    def config_space_cooling_technology(self, instance):
        if not self.flags.has_cooling:
            self._fix_vars(instance, ["Q_RoomCooling", "E_RoomCooling"], value=0)
            self._store_param_values(instance, "CoolingHourlyCOP", [0.0] * self.HOURS_PER_YEAR)

            instance.E_RoomCooling_with_cooling_rule.deactivate()
        else:
            self._unfix_vars(instance, ["Q_RoomCooling", "E_RoomCooling"])
            self._set_upper_bounds(instance, {"Q_RoomCooling": self.scenario.space_cooling_technology.power})
            self._store_param_values(instance, "CoolingHourlyCOP", self.model.CoolingHourlyCOP)

            instance.E_RoomCooling_with_cooling_rule.activate()

    def _fix_no_ev_vars(self, instance):
        self._fix_vars(
            instance,
            ["Grid2EV", "Bat2EV", "PV2EV", "EVSoC", "EVCharge", "EVDischarge", "EV2Load", "EV2Bat"],
            value=0,
        )
        for t in self._hours():
            instance.EVDemandProfile[t] = 0
        instance.EVCharge_rule.deactivate()
        instance.EVDischarge_rule.deactivate()
        instance.EVSoC_rule.deactivate()

    def _config_ev_charge_sources(self, instance):
        if self.flags.has_pv:
            for var_data in instance.PV2EV.values():
                var_data.fixed = False
        else:
            self._fix_vars(instance, ["PV2EV"], value=0)

    def _config_ev_bounds_and_home_availability(self, instance):
        max_discharge_ev = self.model.create_upper_bound_ev_discharge()
        self._unfix_vars(
            instance,
            ["Grid2EV", "Bat2EV", "EVSoC", "EVCharge", "EVDischarge", "EV2Load", "EV2Bat"],
        )

        for t in self._hours():
            instance.EVSoC[t].setub(self.scenario.vehicle.capacity)
            instance.EVCharge[t].setub(self.scenario.vehicle.charge_power_max)
            instance.EVDischarge[t].setub(max_discharge_ev[t - 1])
            instance.EVDemandProfile[t] = self.model.EVDemandProfile[t - 1]
            if self.model.EVAtHomeProfile[t - 1] == 0:
                instance.Grid2EV[t].fix(0)
                instance.Bat2EV[t].fix(0)
                instance.PV2EV[t].fix(0)
                instance.EVCharge[t].fix(0)
                instance.EV2Load[t].fix(0)
                instance.EV2Bat[t].fix(0)

    def _config_ev_v2b(self, instance):
        if self.flags.has_battery:
            if not self.flags.ev_v2b_enabled:
                self._fix_vars(instance, ["EV2Bat", "EV2Load"], value=0)
            return
        for t in self._hours():
            instance.EV2Bat[t].fix(0)
            instance.Bat2EV[t].fix(0)
            if not self.flags.ev_v2b_enabled:
                instance.EV2Load[t].fix(0)

    def config_vehicle(self, instance):
        if not self.flags.has_ev:
            self._fix_no_ev_vars(instance)
            return
        self._config_ev_charge_sources(instance)
        self._config_ev_bounds_and_home_availability(instance)
        self._config_ev_v2b(instance)
        instance.EVCharge_rule.activate()
        instance.EVDischarge_rule.activate()
        instance.EVSoC_rule.activate()

    def config_pv(self, instance):
        if not self.flags.has_pv:
            self._fix_vars(instance, ["PV2Load", "PV2Bat", "PV2Grid"], value=0)
            instance.UseOfPV_rule.deactivate()
        else:
            for pv2load, pv2grid in zip(instance.PV2Load.values(), instance.PV2Grid.values()):
                pv2load.fixed = False
                pv2grid.fixed = False
            instance.UseOfPV_rule.activate()
