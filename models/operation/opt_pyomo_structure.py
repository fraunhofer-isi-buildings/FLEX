import numpy as np
import pyomo.environ as pyo
from models.operation.rc_equations import mean_thermal_mass_temperature
from models.operation.rc_equations import next_thermal_mass_temperature
from models.operation.rc_equations import phi_m
from models.operation.rc_equations import phi_mtot
from models.operation.rc_equations import phi_st
from models.operation.rc_equations import room_temperature
from models.operation.rc_equations import surface_temperature
from models.operation.time_defs import HOURS_PER_YEAR as OP_HOURS_PER_YEAR


class OptInstance:
    HOURS_PER_YEAR = OP_HOURS_PER_YEAR
    # Tiny tie-break penalties to reduce LP degeneracy while keeping
    # energy/fuel costs dominant.
    EPS_BATTERY_THROUGHPUT = 1e-6
    EPS_EV_THROUGHPUT = 9e-7
    EPS_INTER_STORAGE_TRANSFER = 7e-7
    EPS_HEATING_ELEMENT_USE = 5e-7
    EPS_THERMAL_TANK_THROUGHPUT = 3e-7

    # @performance_counter
    def create_instance(self):
        model = self.setup_model()
        instance = model.create_instance()
        return instance

    def setup_model(self):
        m = pyo.AbstractModel()
        self.setup_sets(m)
        self.setup_params(m)
        self.setup_variables(m)
        self.setup_constraint_space_heating_tank(m)
        self.setup_constraint_space_heating_room(m)
        self.setup_constraint_thermal_mass_temperature(m)
        self.setup_constraint_room_temperature(m)
        self.setup_constraint_heating_element(m)
        self.setup_constraint_hot_water(m)
        self.setup_constraint_heat_pump(m)
        self.setup_constraint_boiler(m)
        self.setup_constraint_space_cooling(m)
        self.setup_constraint_pv(m)
        self.setup_constraint_battery(m)
        self.setup_constraint_ev(m)
        self.setup_constraint_electricity_demand(m)
        self.setup_constraint_electricity_supply(m)
        self.setup_objective(m)
        return m

    @staticmethod
    def setup_sets(m):
        m.t = pyo.Set(initialize=np.arange(1, OptInstance.HOURS_PER_YEAR + 1))

    @staticmethod
    def setup_params(m):
        # time dependent parameters:
        # external parameters:
        # outside temperature
        m.T_outside = pyo.Param(m.t, mutable=True)
        # solar gains:
        m.Q_Solar = pyo.Param(m.t, mutable=True)
        m.ElectricityPrice = pyo.Param(m.t, mutable=True)
        m.FuelPrice = pyo.Param(m.t, mutable=True)
        # Feed in Tariff of Photovoltaic
        m.FiT = pyo.Param(m.t, mutable=True)

        # heating
        # Boiler
        m.Boiler_COP = pyo.Param(mutable=True)
        m.Boiler_MaximalThermalPower = pyo.Param(mutable=True, within=pyo.Any)
        # COP of heat pump
        m.SpaceHeatingHourlyCOP = pyo.Param(m.t, mutable=True)
        # COP of heatpump for charging buffer storage
        m.SpaceHeatingHourlyCOP_tank = pyo.Param(m.t, mutable=True)
        # hot water
        m.HotWaterProfile = pyo.Param(m.t, mutable=True)
        # COP for hot water
        m.HotWaterHourlyCOP = pyo.Param(m.t, mutable=True)
        # COP for hot water when charging DHW storage
        m.HotWaterHourlyCOP_tank = pyo.Param(m.t, mutable=True)

        # time independent parameters:
        m.SpaceHeating_MaxBoilerPower = pyo.Param(mutable=True)
        m.CPWater = pyo.Param(mutable=True)

        # electricity load profile
        m.BaseLoadProfile = pyo.Param(m.t, mutable=True)
        # PV
        m.PhotovoltaicProfile = pyo.Param(m.t, mutable=True)
        # Electric vehicle
        m.EVDemandProfile = pyo.Param(m.t, mutable=True)

        # COP of cooling
        m.CoolingHourlyCOP = pyo.Param(m.t, mutable=True)

        # ventilation supply temperature
        m.VentilationSupplyTemperature = pyo.Param(m.t, mutable=True)

        # heating element
        m.HeatingElement_efficiency = pyo.Param(mutable=True)

        # heating tank
        m.U_LossTank_heating = pyo.Param(mutable=True)
        m.A_SurfaceTank_heating = pyo.Param(mutable=True)
        m.M_WaterTank_heating = pyo.Param(mutable=True)
        m.T_TankSurrounding_heating = pyo.Param(mutable=True)
        m.T_TankStart_heating = pyo.Param(mutable=True)

        # DHW tank
        m.U_LossTank_DHW = pyo.Param(mutable=True)
        m.A_SurfaceTank_DHW = pyo.Param(mutable=True)
        m.M_WaterTank_DHW = pyo.Param(mutable=True)
        m.T_TankSurrounding_DHW = pyo.Param(mutable=True)
        m.T_TankStart_DHW = pyo.Param(mutable=True)

        # battery
        m.BatteryChargeEfficiency = pyo.Param(mutable=True)
        m.BatteryDischargeEfficiency = pyo.Param(mutable=True)

        # electric vehicle
        m.EVChargeEfficiency = pyo.Param(mutable=True)
        m.EVDischargeEfficiency = pyo.Param(mutable=True)
        m.EVCapacity = pyo.Param(mutable=True)

        # building parameters
        m.Am = pyo.Param(mutable=True)
        m.Atot = pyo.Param(mutable=True)
        m.Qi = pyo.Param(mutable=True)
        m.Htr_w = pyo.Param(mutable=True)
        m.Htr_em = pyo.Param(mutable=True)
        m.Htr_ms = pyo.Param(mutable=True)
        m.Htr_is = pyo.Param(mutable=True)
        m.Hve = pyo.Param(mutable=True)
        m.Htr_1 = pyo.Param(mutable=True)
        m.Htr_2 = pyo.Param(mutable=True)
        m.Htr_3 = pyo.Param(mutable=True)
        m.PHI_ia = pyo.Param(mutable=True)
        m.Cm = pyo.Param(mutable=True)
        m.BuildingMassTemperatureStartValue = pyo.Param(mutable=True)

    @staticmethod
    def setup_variables(m):
        # space heating
        m.Q_HeatingTank_in = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_HeatingTank_out = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_HeatingTank = pyo.Var(m.t, within=pyo.NonNegativeReals)  # energy in the tank
        m.Q_HeatingTank_bypass = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.E_Heating_HP_out = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_RoomHeating = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_Heating_Boiler_out = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Fuel = pyo.Var(m.t, within=pyo.NonNegativeReals)

        # heating element
        m.Q_HeatingElement = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_HeatingElement_DHW = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_HeatingElement_heat = pyo.Var(m.t, within=pyo.NonNegativeReals)

        # Temperatures (room and thermal mass)
        m.T_Room = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.T_BuildingMass = pyo.Var(m.t, within=pyo.NonNegativeReals, bounds=(0, 100))

        # space cooling
        m.Q_RoomCooling = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.E_RoomCooling = pyo.Var(m.t, within=pyo.NonNegativeReals)

        # hot water
        m.Q_DHWTank_out = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_DHWTank = pyo.Var(m.t, within=pyo.NonNegativeReals)  # energy in the tank
        m.Q_DHWTank_in = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.E_DHW_HP_out = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_DHWTank_bypass = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Q_DHW_Boiler_out = pyo.Var(m.t, within=pyo.NonNegativeReals)

        # PV
        m.PV2Load = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.PV2Bat = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.PV2Grid = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.PV2EV = pyo.Var(m.t, within=pyo.NonNegativeReals)

        # battery
        m.BatSoC = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.BatCharge = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.BatDischarge = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Bat2Load = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Bat2EV = pyo.Var(m.t, within=pyo.NonNegativeReals)

        # EV
        m.EVSoC = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.EVCharge = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.EVDischarge = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.EV2Bat = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.EV2Load = pyo.Var(m.t, within=pyo.NonNegativeReals)

        # grid
        m.Grid = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Grid2Load = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Grid2Bat = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Grid2EV = pyo.Var(m.t, within=pyo.NonNegativeReals)

        # Electric Load and Electricity fed back to the grid
        m.Load = pyo.Var(m.t, within=pyo.NonNegativeReals)
        m.Feed2Grid = pyo.Var(m.t, within=pyo.NonNegativeReals)

    @staticmethod
    def setup_constraint_space_heating_tank(m):
        def tank_energy_heating(m, t):
            if t == 1:
                return m.Q_HeatingTank[t] == \
                       m.CPWater * m.M_WaterTank_heating * (273.15 + m.T_TankStart_heating) - \
                       m.Q_HeatingTank_out[t]
            else:
                return m.Q_HeatingTank[t] == \
                       m.Q_HeatingTank[t - 1] - m.Q_HeatingTank_out[t] + m.Q_HeatingTank_in[t] - \
                       m.U_LossTank_heating * m.A_SurfaceTank_heating * \
                       ((m.Q_HeatingTank[t] / (m.M_WaterTank_heating * m.CPWater)) -
                        (m.T_TankSurrounding_heating + 273.15))
        m.tank_energy_rule_heating = pyo.Constraint(m.t, rule=tank_energy_heating)

    @staticmethod
    def setup_constraint_space_heating_room(m):
        def room_heating(m, t):
            return m.Q_RoomHeating[t] == m.Q_HeatingTank_out[t] + m.Q_HeatingTank_bypass[t]
        m.room_heating_rule = pyo.Constraint(m.t, rule=room_heating)

    @staticmethod
    def setup_constraint_thermal_mass_temperature(m):
        def thermal_mass_temperature_rc(m, t):
            if t == 1:
                Tm_start = m.BuildingMassTemperatureStartValue
            else:
                Tm_start = m.T_BuildingMass[t - 1]
            PHI_m = phi_m(am=m.Am, atot=m.Atot, qi=m.Qi, q_solar=m.Q_Solar[t])
            PHI_st = phi_st(am=m.Am, atot=m.Atot, htr_w=m.Htr_w, qi=m.Qi, q_solar=m.Q_Solar[t])
            T_sup = m.VentilationSupplyTemperature[t]
            PHI_mtot = phi_mtot(
                phi_m_val=PHI_m,
                htr_em=m.Htr_em,
                t_outside=m.T_outside[t],
                htr_3=m.Htr_3,
                phi_st_val=PHI_st,
                htr_w=m.Htr_w,
                htr_1=m.Htr_1,
                phi_ia=m.PHI_ia,
                q_hc=m.Q_RoomHeating[t] - m.Q_RoomCooling[t],
                hve=m.Hve,
                t_sup=T_sup,
                htr_2=m.Htr_2,
            )
            return m.T_BuildingMass[t] == next_thermal_mass_temperature(
                tm_prev=Tm_start,
                cm=m.Cm,
                htr_3=m.Htr_3,
                htr_em=m.Htr_em,
                phi_mtot_val=PHI_mtot,
            )
        m.thermal_mass_temperature_rule = pyo.Constraint(m.t, rule=thermal_mass_temperature_rc)

    @staticmethod
    def setup_constraint_room_temperature(m):

        def room_temperature_rc(m, t):
            if t == 1:
                Tm_start = m.BuildingMassTemperatureStartValue
            else:
                Tm_start = m.T_BuildingMass[t - 1]
            PHI_st = phi_st(am=m.Am, atot=m.Atot, htr_w=m.Htr_w, qi=m.Qi, q_solar=m.Q_Solar[t])
            T_m = mean_thermal_mass_temperature(tm_now=m.T_BuildingMass[t], tm_prev=Tm_start)
            T_sup = m.VentilationSupplyTemperature[t]
            T_s = surface_temperature(
                htr_ms=m.Htr_ms,
                t_m=T_m,
                phi_st_val=PHI_st,
                htr_w=m.Htr_w,
                t_outside=m.T_outside[t],
                htr_1=m.Htr_1,
                t_sup=T_sup,
                phi_ia=m.PHI_ia,
                q_hc=m.Q_RoomHeating[t] - m.Q_RoomCooling[t],
                hve=m.Hve,
            )
            T_air = room_temperature(
                htr_is=m.Htr_is,
                t_s=T_s,
                hve=m.Hve,
                t_sup=T_sup,
                phi_ia=m.PHI_ia,
                q_hc=m.Q_RoomHeating[t] - m.Q_RoomCooling[t],
            )
            return m.T_Room[t] == T_air

        m.room_temperature_rule = pyo.Constraint(m.t, rule=room_temperature_rc)

    @staticmethod
    def setup_constraint_hot_water(m):

        def tank_energy_DHW(m, t):
            if t == 1:
                return (
                        m.Q_DHWTank[t]
                        == m.CPWater
                        * m.M_WaterTank_DHW
                        * (273.15 + m.T_TankStart_DHW)
                        - m.Q_DHWTank_out[t]
                )
            else:
                return m.Q_DHWTank[t] == m.Q_DHWTank[t - 1] - m.Q_DHWTank_out[
                    t
                ] + m.Q_DHWTank_in[t] - m.U_LossTank_DHW * m.A_SurfaceTank_DHW * (
                               m.Q_DHWTank[t] / (m.M_WaterTank_DHW * m.CPWater)
                               - (m.T_TankSurrounding_DHW + 273.15)
                       )

        m.tank_energy_rule_DHW = pyo.Constraint(m.t, rule=tank_energy_DHW)

        # (14) DHW profile coverage
        def calc_hot_water_profile(m, t):
            return m.HotWaterProfile[t] == m.Q_DHWTank_out[t] + m.Q_DHWTank_bypass[t]

        m.SupplyOfDHW_rule = pyo.Constraint(m.t, rule=calc_hot_water_profile)

    @staticmethod
    def setup_constraint_heat_pump(m):
        def calc_supply_of_space_heating_HP(m, t):
            return (
                    m.Q_HeatingTank_bypass[t] * m.SpaceHeatingHourlyCOP_tank[t] +
                    m.Q_HeatingTank_in[t] * m.SpaceHeatingHourlyCOP[t] ==
                    m.E_Heating_HP_out[t] * m.SpaceHeatingHourlyCOP_tank[t] * m.SpaceHeatingHourlyCOP[t] +
                    m.Q_HeatingElement_heat[t]
            )

        m.calc_use_of_HP_power_DHW_rule = pyo.Constraint(
            m.t, rule=calc_supply_of_space_heating_HP
        )

        def calc_supply_of_DHW_HP(m, t):
            return (
                    m.Q_DHWTank_bypass[t] * m.HotWaterHourlyCOP_tank[t] +
                    m.Q_DHWTank_in[t] * m.HotWaterHourlyCOP[t] ==
                    m.E_DHW_HP_out[t] * m.HotWaterHourlyCOP_tank[t] * m.HotWaterHourlyCOP[t] +
                    m.Q_HeatingElement_DHW[t]
            )

        m.bypass_DHW_HP_rule = pyo.Constraint(m.t, rule=calc_supply_of_DHW_HP)

        def constrain_heating_max_power_HP(m, t):
            return (
                    m.E_DHW_HP_out[t] + m.E_Heating_HP_out[t]
                    <= m.SpaceHeating_MaxBoilerPower
            )

        m.max_HP_power_rule = pyo.Constraint(m.t, rule=constrain_heating_max_power_HP)

    @staticmethod
    def setup_constraint_boiler(m):
        def calc_supply_of_space_heating_fuel_boiler(m, t):
            return (m.Q_HeatingTank_bypass[t] + m.Q_HeatingTank_in[t] ==
                    m.Q_Heating_Boiler_out[t] + m.Q_HeatingElement_heat[t])

        m.calc_use_of_fuel_boiler_power_DHW_rule = pyo.Constraint(
            m.t, rule=calc_supply_of_space_heating_fuel_boiler
        )

        def calc_supply_of_DHW_fuel_boiler(m, t):
            return (
                    m.Q_DHWTank_bypass[t] + m.Q_DHWTank_in[t] ==
                    m.Q_DHW_Boiler_out[t] + m.Q_HeatingElement_DHW[t]
            )

        m.bypass_DHW_fuel_boiler_rule = pyo.Constraint(m.t, rule=calc_supply_of_DHW_fuel_boiler)

        def constrain_heating_max_power_fuel_boiler(m, t):
            return (
                    m.Q_DHW_Boiler_out[t] + m.Q_Heating_Boiler_out[t]
                    <= m.Boiler_MaximalThermalPower
            )

        m.max_fuel_boiler_power_rule = pyo.Constraint(m.t, rule=constrain_heating_max_power_fuel_boiler)

        def calc_boiler_conversion(m, t):
            return (
                    m.Q_DHW_Boiler_out[t] + m.Q_Heating_Boiler_out[t] == m.Fuel[t] * m.Boiler_COP
            )

        m.boiler_conversion_rule = pyo.Constraint(m.t, rule=calc_boiler_conversion)

    @staticmethod
    def setup_constraint_heating_element(m):
        def calc_heating_element(m, t):
            return m.Q_HeatingElement_DHW[t] + m.Q_HeatingElement_heat[t] == m.Q_HeatingElement[t]
        m.heating_element_rule = pyo.Constraint(m.t, rule=calc_heating_element)

    @staticmethod
    def setup_constraint_space_cooling(m):
        def calc_E_RoomCooling_with_cooling(m, t):
            return m.E_RoomCooling[t] == m.Q_RoomCooling[t] / m.CoolingHourlyCOP[t]
        m.E_RoomCooling_with_cooling_rule = pyo.Constraint(m.t, rule=calc_E_RoomCooling_with_cooling)

    @staticmethod
    def setup_constraint_pv(m):

        def calc_UseOfPV(m, t):
            return m.PhotovoltaicProfile[t] == \
                   m.PV2EV[t] + m.PV2Load[t] + m.PV2Bat[t] + m.PV2Grid[t]
        m.UseOfPV_rule = pyo.Constraint(m.t, rule=calc_UseOfPV)

        def calc_SumOfFeedin(m, t):
            return m.Feed2Grid[t] == m.PV2Grid[t]
        m.SumOfFeedin_rule = pyo.Constraint(m.t, rule=calc_SumOfFeedin)

    @staticmethod
    def setup_constraint_battery(m):

        def calc_BatCharge(m, t):
            return m.BatCharge[t] == m.PV2Bat[t] + m.Grid2Bat[t] + m.EV2Bat[t]
        m.BatCharge_rule = pyo.Constraint(m.t, rule=calc_BatCharge)

        def calc_BatDischarge(m, t):
            return m.BatDischarge[t] == m.Bat2Load[t] + m.Bat2EV[t]
        m.BatDischarge_rule = pyo.Constraint(m.t, rule=calc_BatDischarge)

        def calc_BatSoC(m, t):
            if t == 1:
                return m.BatSoC[t] == 0 + m.BatCharge[t] * m.BatteryChargeEfficiency - \
                       m.BatDischarge[t] * (1 + (1 - m.BatteryDischargeEfficiency))
            else:
                return m.BatSoC[t] == m.BatSoC[t - 1] + m.BatCharge[t] * m.BatteryChargeEfficiency - \
                       m.BatDischarge[t] * (1 + (1 - m.BatteryDischargeEfficiency))
        m.BatSoC_rule = pyo.Constraint(m.t, rule=calc_BatSoC)

    @staticmethod
    def setup_constraint_ev(m):

        def calc_EVCharge(m, t):
            return m.EVCharge[t] == m.PV2EV[t] + m.Grid2EV[t] + m.Bat2EV[t]
        m.EVCharge_rule = pyo.Constraint(m.t, rule=calc_EVCharge)

        def calc_EVDischarge(m, t):
            return m.EVDischarge[t] == m.EVDemandProfile[t] + m.EV2Load[t] + m.EV2Bat[t]
        m.EVDischarge_rule = pyo.Constraint(m.t, rule=calc_EVDischarge)

        def calc_EVSoC(m, t):
            if t == 1:
                return m.EVSoC[t] == m.EVCapacity + \
                                     m.EVCharge[t] * m.EVChargeEfficiency - \
                                     m.EVDischarge[t] / m.EVDischargeEfficiency
            else:
                return m.EVSoC[t] == m.EVSoC[t - 1] + \
                                     m.EVCharge[t] * m.EVChargeEfficiency - \
                                     m.EVDischarge[t] / m.EVDischargeEfficiency
        m.EVSoC_rule = pyo.Constraint(m.t, rule=calc_EVSoC)

    @staticmethod
    def setup_constraint_electricity_demand(m):

        def calc_SumOfLoads_with_cooling(m, t):
            return m.Load[t] == \
                   m.BaseLoadProfile[t] + \
                   m.E_Heating_HP_out[t] + \
                   m.Q_HeatingElement[t] / m.HeatingElement_efficiency + \
                   m.E_RoomCooling[t] + \
                   m.E_DHW_HP_out[t]
        m.SumOfLoads_with_cooling_rule = pyo.Constraint(m.t, rule=calc_SumOfLoads_with_cooling)

    @staticmethod
    def setup_constraint_electricity_supply(m):

        def calc_UseOfGrid(m, t):
            return m.Grid[t] == m.Grid2Load[t] + m.Grid2Bat[t] + m.Grid2EV[t]
        m.UseOfGrid_rule = pyo.Constraint(m.t, rule=calc_UseOfGrid)

        def calc_SupplyOfLoads(m, t):
            return m.Load[t] == m.Grid2Load[t] + m.PV2Load[t] + m.Bat2Load[t] + m.EV2Load[t]
        m.SupplyOfLoads_rule = pyo.Constraint(m.t, rule=calc_SupplyOfLoads)

    @staticmethod
    def setup_objective(m):
        def minimize_cost(m):
            rule = sum(
                m.Grid[t] * m.ElectricityPrice[t]
                + m.Fuel[t] * m.FuelPrice[t]
                - m.Feed2Grid[t] * m.FiT[t]
                + OptInstance.EPS_BATTERY_THROUGHPUT * (m.BatCharge[t] + m.BatDischarge[t])
                + OptInstance.EPS_EV_THROUGHPUT * (m.EVCharge[t] + m.EVDischarge[t])
                + OptInstance.EPS_INTER_STORAGE_TRANSFER * (m.Bat2EV[t] + m.EV2Bat[t])
                + OptInstance.EPS_HEATING_ELEMENT_USE * m.Q_HeatingElement[t]
                + OptInstance.EPS_THERMAL_TANK_THROUGHPUT * (
                    m.Q_HeatingTank_in[t]
                    + m.Q_HeatingTank_out[t]
                    + m.Q_DHWTank_in[t]
                    + m.Q_DHWTank_out[t]
                )
                for t in m.t
            )
            return rule
        m.total_operation_cost_rule = pyo.Objective(rule=minimize_cost, sense=pyo.minimize)

    @staticmethod
    def create_dict(values) -> dict:
        dictionary = {}
        for index, value in enumerate(values, start=1):
            dictionary[index] = value
        return dictionary
