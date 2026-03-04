from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.operation.model_base import OperationModel


class OptConfig:
    HOURS_PER_YEAR = 8760

    def __init__(self, model: 'OperationModel'):
        self.model = model
        self.scenario = model.scenario

    def _hours(self):
        return range(1, self.HOURS_PER_YEAR + 1)

    def _fix_vars(self, instance, var_names, value=0):
        for t in self._hours():
            for var_name in var_names:
                instance.__dict__[var_name][t].fix(value)

    def _unfix_vars(self, instance, var_names):
        for t in self._hours():
            for var_name in var_names:
                instance.__dict__[var_name][t].fixed = False

    def _set_upper_bounds(self, instance, upper_bounds: dict):
        for t in self._hours():
            for var_name, ub in upper_bounds.items():
                instance.__dict__[var_name][t].setub(ub)

    def _set_lower_bounds(self, instance, lower_bounds: dict):
        for t in self._hours():
            for var_name, lb in lower_bounds.items():
                instance.__dict__[var_name][t].setlb(lb)

    def _set_bounds(self, instance, bounds: dict):
        for t in self._hours():
            for var_name, (lb, ub) in bounds.items():
                instance.__dict__[var_name][t].setlb(lb)
                instance.__dict__[var_name][t].setub(ub)

    @staticmethod
    def _to_indexed_dict(values):
        return {idx: val for idx, val in enumerate(values, start=1)}

    def _store_param_values(self, instance, param_name: str, values):
        instance.__dict__[param_name].store_values(self._to_indexed_dict(values))

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
        instance.Am = self.scenario.building.Am_factor
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

        if self.scenario.boiler.type in ["Air_HP", "Ground_HP", "Electric"]:
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
            instance.boiler_conversion_rule.deactivate()
            instance.max_fuel_boiler_power_rule.deactivate()
            instance.bypass_DHW_fuel_boiler_rule.deactivate()
            instance.calc_use_of_fuel_boiler_power_DHW_rule.deactivate()
            # activate heat pump functions
            instance.max_HP_power_rule.activate()
            instance.bypass_DHW_HP_rule.activate()
            instance.calc_use_of_HP_power_DHW_rule.activate()

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
            instance.boiler_conversion_rule.activate()
            instance.max_fuel_boiler_power_rule.activate()
            instance.bypass_DHW_fuel_boiler_rule.activate()
            instance.calc_use_of_fuel_boiler_power_DHW_rule.activate()
            # deactivate heat pump functions
            instance.max_HP_power_rule.deactivate()
            instance.bypass_DHW_HP_rule.deactivate()
            instance.calc_use_of_HP_power_DHW_rule.deactivate()

    def config_heating_element(self, instance):
        if self.model.HeatingElement_efficiency > 0:
            instance.HeatingElement_efficiency = self.model.HeatingElement_efficiency
        else:
            instance.HeatingElement_efficiency = 1  # to avoid that the model cant run
        if self.model.HeatingElement_power == 0:
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
        if self.scenario.boiler.type not in ['Air_HP', 'Ground_HP', "Electric"]:
            fuel_prices = self.scenario.energy_price.__dict__[self.scenario.boiler.type]
        else:
            fuel_prices = [0.0] * self.HOURS_PER_YEAR
        self._store_param_values(instance, "FuelPrice", fuel_prices)

    def config_grid(self, instance):
        for t in self._hours():
            instance.Grid[t].setub(self.scenario.building.grid_power_max)
            instance.Feed2Grid[t].setub(self.scenario.building.grid_power_max)

    def config_space_heating(self, instance):
        for t in self._hours():
            instance.T_BuildingMass[t].setub(100)
        if self.scenario.boiler.type in ["Air_HP", "Ground_HP", "Electric"]:
            for t in self._hours():
                instance.E_Heating_HP_out[t].setub(self.model.SpaceHeating_MaxBoilerPower)
        else:
            for t in self._hours():
                instance.Q_Heating_Boiler_out[t].setub(self.model.SpaceHeating_MaxBoilerPower)
                instance.Q_DHW_Boiler_out[t].setub(self.model.SpaceHeating_MaxBoilerPower)

    def config_space_heating_tank(self, instance):
        if self.scenario.space_heating_tank.size == 0:
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
        if self.scenario.hot_water_tank.size == 0:
            self._fix_vars(instance, ["Q_DHWTank_out", "Q_DHWTank_in", "Q_DHWTank"], value=0)
            self._set_bounds(instance, {"Q_DHWTank": (0, 0)})
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
        if self.scenario.battery.capacity == 0:
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
            if self.scenario.pv.size > 0:
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
        for t in self._hours():
            instance.T_Room[t].setub(max_target_temperature[t - 1])
            instance.T_Room[t].setlb(min_target_temperature[t - 1])

    def config_space_cooling_technology(self, instance):
        if self.scenario.space_cooling_technology.power == 0:
            self._fix_vars(instance, ["Q_RoomCooling", "E_RoomCooling"], value=0)
            self._store_param_values(instance, "CoolingHourlyCOP", [0.0] * self.HOURS_PER_YEAR)

            instance.E_RoomCooling_with_cooling_rule.deactivate()
        else:
            self._unfix_vars(instance, ["Q_RoomCooling", "E_RoomCooling"])
            self._set_upper_bounds(instance, {"Q_RoomCooling": self.scenario.space_cooling_technology.power})
            self._store_param_values(instance, "CoolingHourlyCOP", self.model.CoolingHourlyCOP)

            instance.E_RoomCooling_with_cooling_rule.activate()

    def config_vehicle(self, instance):
        max_discharge_ev = self.model.create_upper_bound_ev_discharge()
        if self.scenario.vehicle.capacity == 0:  # no EV is implemented
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
        else:
            # if there is a PV installed:
            if self.scenario.pv.size > 0:
                for t in self._hours():
                    instance.PV2EV[t].fixed = False
            else:  # if there is no PV, EV can not be charged by it
                self._fix_vars(instance, ["PV2EV"], value=0)

            # unfix variables
            self._unfix_vars(
                instance,
                ["Grid2EV", "Bat2EV", "EVSoC", "EVCharge", "EVDischarge", "EV2Load", "EV2Bat"],
            )

            for t in self._hours():
                # set upper bounds
                instance.EVSoC[t].setub(self.scenario.vehicle.capacity)
                instance.EVCharge[t].setub(self.scenario.vehicle.charge_power_max)
                instance.EVDischarge[t].setub(max_discharge_ev[t - 1])
                instance.EVDemandProfile[t] = self.model.EVDemandProfile[t-1]
                # fix variables when EV is not at home:
                if self.model.EVAtHomeProfile[t-1] == 0:
                    instance.Grid2EV[t].fix(0)
                    instance.Bat2EV[t].fix(0)
                    instance.PV2EV[t].fix(0)
                    instance.EVCharge[t].fix(0)
                    instance.EV2Load[t].fix(0)
                    instance.EV2Bat[t].fix(0)

            # in case there is a stationary battery available:
            if self.scenario.battery.capacity > 0:
                if self.model.EVOptionV2B == 0:
                    self._fix_vars(instance, ["EV2Bat", "EV2Load"], value=0)

            # in case there is no stationary battery available:
            else:
                for t in self._hours():
                    instance.EV2Bat[t].fix(0)
                    instance.Bat2EV[t].fix(0)
                    if self.model.EVOptionV2B == 0:
                        instance.EV2Load[t].fix(0)

            instance.EVCharge_rule.activate()
            instance.EVDischarge_rule.activate()
            instance.EVSoC_rule.activate()

    def config_pv(self, instance):
        if self.scenario.pv.size == 0:
            self._fix_vars(instance, ["PV2Load", "PV2Bat", "PV2Grid"], value=0)
            instance.UseOfPV_rule.deactivate()
        else:
            for t in self._hours():
                instance.PV2Load[t].fixed = False
                instance.PV2Grid[t].fixed = False
                # instance.PV2Load[t].setub(self.scenario.building.grid_power_max)
            instance.UseOfPV_rule.activate()
