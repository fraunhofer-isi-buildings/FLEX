import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from models.operation.constants import OperationResultVar
from models.operation.model_base import OperationModel
from models.operation.solver import get_solver_name


@dataclass
class LinopyResultModel:
    total_cost: float


class LinopyOperationModel(OperationModel):
    """Linopy implementation aligned with OptOperationModel structure."""

    HOURS_PER_YEAR = 8760
    HOUR_DIM = "hour"

    EXTERNAL_RESULT_VARS = {
        "T_outside",
        "Q_Solar",
        "SpaceHeatingHourlyCOP",
        "SpaceHeatingHourlyCOP_tank",
        "HotWaterProfile",
        "HotWaterHourlyCOP",
        "HotWaterHourlyCOP_tank",
        "CoolingHourlyCOP",
        "PhotovoltaicProfile",
        "EVDemandProfile",
        "ElectricityPrice",
        "FiT",
        "FuelPrice",
        "BaseLoadProfile",
    }

    def __init__(self, scenario):
        super().__init__(scenario)
        self.logger = logging.getLogger(f"{self.scenario.config.project_name}")
        self.hours = np.arange(1, self.HOURS_PER_YEAR + 1)
        self.hour_index = pd.Index(self.hours, name=self.HOUR_DIM)
        self._var = {}

    @staticmethod
    def _iter_result_var_names():
        for key in OperationResultVar.__dict__:
            if not key.startswith("_"):
                yield key

    def _arr(self, values, dtype=float):
        return np.asarray(values, dtype=dtype)

    def _zeros(self):
        return np.zeros((self.HOURS_PER_YEAR,), dtype=float)

    def _is_hp(self) -> bool:
        return self.scenario.boiler.type in ["Air_HP", "Ground_HP", "Electric"]

    def _has_cooling(self) -> bool:
        return float(self.scenario.space_cooling_technology.power or 0) > 0

    def _has_battery(self) -> bool:
        return float(self.scenario.battery.capacity or 0) > 0

    def _has_ev(self) -> bool:
        return float(self.scenario.vehicle.capacity or 0) > 0

    def _has_pv(self) -> bool:
        return float(self.scenario.pv.size or 0) > 0

    def _has_space_heating_tank(self) -> bool:
        return float(self.scenario.space_heating_tank.size or 0) > 0

    def _has_hot_water_tank(self) -> bool:
        return float(self.scenario.hot_water_tank.size or 0) > 0

    def _da(self, values):
        import xarray as xr

        return xr.DataArray(self._arr(values), coords={self.HOUR_DIM: self.hours}, dims=(self.HOUR_DIM,))

    def _at(self, expr, hour: int):
        return expr.loc[{self.HOUR_DIM: hour}]

    def _ati(self, expr, idx: int):
        return expr.isel({self.HOUR_DIM: idx})

    def _add_var(self, model, name, lower=0, upper=None):
        resolved_upper = np.inf if upper is None else upper
        self._var[name] = model.add_variables(
            lower=lower,
            upper=resolved_upper,
            coords=[self.hour_index],
            name=name,
        )
        return self._var[name]

    def _fix_zero(self, model, name):
        model.add_constraints(self._var[name] == 0)

    def _add_ub(self, model, name, ub):
        model.add_constraints(self._var[name] <= ub)

    def _add_lb(self, model, name, lb):
        model.add_constraints(self._var[name] >= lb)

    def _build_model(self):
        import linopy

        model = linopy.Model()

        # Time-varying parameters
        p_elec_price = self._da(self.ElectricityPrice)
        p_fit = self._da(self.FiT)
        p_hot_water_profile = self._da(self.HotWaterProfile)
        p_hot_water_cop = self._da(self.HotWaterHourlyCOP)
        p_hot_water_cop_tank = self._da(self.HotWaterHourlyCOP_tank)
        p_space_heating_cop = self._da(self.SpaceHeatingHourlyCOP)
        p_space_heating_cop_tank = self._da(self.SpaceHeatingHourlyCOP_tank)
        p_base_load = self._da(self.BaseLoadProfile)
        p_pv = self._da(self.PhotovoltaicProfile)
        p_ev_demand = self._da(self.EVDemandProfile)
        p_cooling_cop = self._da(self.CoolingHourlyCOP)
        a_t_outside = self._arr(self.T_outside)
        a_q_solar = self._arr(self.Q_Solar)
        a_t_sup = self._arr(self.scenario.behavior.ventilation_supply_temperature)

        if self._is_hp():
            p_fuel_price = self._da(self._zeros())
        else:
            p_fuel_price = self._da(self.scenario.energy_price.__dict__[self.scenario.boiler.type])

        for name in self._iter_result_var_names():
            if name in self.EXTERNAL_RESULT_VARS:
                continue
            self._add_var(model, name, lower=0)

        cpw = float(self.CPWater)
        space_tank_size = float(self.scenario.space_heating_tank.size or 0)
        hot_tank_size = float(self.scenario.hot_water_tank.size or 0)
        has_space_tank = self._has_space_heating_tank()
        has_hot_tank = self._has_hot_water_tank()
        has_cooling = self._has_cooling()
        has_battery = self._has_battery()
        has_ev = self._has_ev()
        has_pv = self._has_pv()
        is_hp = self._is_hp()

        # (1) Space heating tank energy
        if has_space_tank:
            qh = self._var["Q_HeatingTank"]
            qh_in = self._var["Q_HeatingTank_in"]
            qh_out = self._var["Q_HeatingTank_out"]
            k = float(self.scenario.space_heating_tank.loss * self.A_SurfaceTank_heating / (cpw * space_tank_size))
            rhs_const = float(
                self.scenario.space_heating_tank.loss
                * self.A_SurfaceTank_heating
                * (self.scenario.space_heating_tank.temperature_surrounding + 273.15)
            )

            model.add_constraints(
                self._ati(qh, 0)
                == cpw * space_tank_size * (273.15 + self.scenario.space_heating_tank.temperature_start)
                - self._ati(qh_out, 0)
            )
            for idx in range(1, self.HOURS_PER_YEAR):
                model.add_constraints(
                    self._ati(qh, idx) * (1 + k)
                    == self._ati(qh, idx - 1)
                    - self._ati(qh_out, idx)
                    + self._ati(qh_in, idx)
                    + rhs_const
                )
        else:
            self._fix_zero(model, "Q_HeatingTank")
            self._fix_zero(model, "Q_HeatingTank_in")
            self._fix_zero(model, "Q_HeatingTank_out")

        # (2) Room heating split
        model.add_constraints(
            self._var["Q_RoomHeating"] == self._var["Q_HeatingTank_out"] + self._var["Q_HeatingTank_bypass"]
        )

        # (3) Thermal mass and room temperature (5R1C)
        for idx in range(self.HOURS_PER_YEAR):
            if idx == 0:
                tm_prev = float(self.BuildingMassTemperatureStartValue)
            else:
                tm_prev = self._ati(self._var["T_BuildingMass"], idx - 1)

            q_solar_t = float(a_q_solar[idx])
            t_out = float(a_t_outside[idx])
            t_sup = float(a_t_sup[idx])

            phi_m = self.Am / self.Atot * (0.5 * self.Qi + q_solar_t)
            phi_st = (
                1 - self.Am / self.Atot - self.Htr_w / 9.1 / self.Atot
            ) * (0.5 * self.Qi + q_solar_t)
            qh = self._ati(self._var["Q_RoomHeating"], idx)
            qc = self._ati(self._var["Q_RoomCooling"], idx)

            phi_mtot = (
                phi_m
                + self.Htr_em * t_out
                + self.Htr_3
                * (
                    phi_st
                    + self.Htr_w * t_out
                    + self.Htr_1 * (((self.PHI_ia + qh - qc) / self.Hve) + t_sup)
                )
                / self.Htr_2
            )

            model.add_constraints(
                self._ati(self._var["T_BuildingMass"], idx)
                == (
                    tm_prev * ((self.Cm / 3600) - 0.5 * (self.Htr_3 + self.Htr_em))
                    + phi_mtot
                )
                / ((self.Cm / 3600) + 0.5 * (self.Htr_3 + self.Htr_em))
            )

            t_m = (self._ati(self._var["T_BuildingMass"], idx) + tm_prev) / 2
            t_s = (
                self.Htr_ms * t_m
                + phi_st
                + self.Htr_w * t_out
                + self.Htr_1 * (t_sup + (self.PHI_ia + qh - qc) / self.Hve)
            ) / (self.Htr_ms + self.Htr_w + self.Htr_1)
            t_air = (
                self.Htr_is * t_s + self.Hve * t_sup + self.PHI_ia + qh - qc
            ) / (self.Htr_is + self.Hve)
            model.add_constraints(self._ati(self._var["T_Room"], idx) == t_air)

        # (4) Heating element split
        model.add_constraints(
            self._var["Q_HeatingElement"] == self._var["Q_HeatingElement_DHW"] + self._var["Q_HeatingElement_heat"]
        )

        # (5) DHW tank energy and profile
        if has_hot_tank:
            qd = self._var["Q_DHWTank"]
            qd_in = self._var["Q_DHWTank_in"]
            qd_out = self._var["Q_DHWTank_out"]
            k = float(self.scenario.hot_water_tank.loss * self.A_SurfaceTank_DHW / (cpw * hot_tank_size))
            rhs_const = float(
                self.scenario.hot_water_tank.loss
                * self.A_SurfaceTank_DHW
                * (self.scenario.hot_water_tank.temperature_surrounding + 273.15)
            )
            model.add_constraints(
                self._ati(qd, 0)
                == cpw * hot_tank_size * (273.15 + self.scenario.hot_water_tank.temperature_start)
                - self._ati(qd_out, 0)
            )
            for idx in range(1, self.HOURS_PER_YEAR):
                model.add_constraints(
                    self._ati(qd, idx) * (1 + k)
                    == self._ati(qd, idx - 1)
                    - self._ati(qd_out, idx)
                    + self._ati(qd_in, idx)
                    + rhs_const
                )
        else:
            self._fix_zero(model, "Q_DHWTank")
            self._fix_zero(model, "Q_DHWTank_in")
            self._fix_zero(model, "Q_DHWTank_out")

        model.add_constraints(p_hot_water_profile == self._var["Q_DHWTank_out"] + self._var["Q_DHWTank_bypass"])

        # (6) HP or fuel boiler branch
        if is_hp:
            model.add_constraints(
                self._var["Q_HeatingTank_bypass"] * p_space_heating_cop_tank
                + self._var["Q_HeatingTank_in"] * p_space_heating_cop
                == self._var["E_Heating_HP_out"] * p_space_heating_cop_tank * p_space_heating_cop
                + self._var["Q_HeatingElement_heat"]
            )
            model.add_constraints(
                self._var["Q_DHWTank_bypass"] * p_hot_water_cop_tank
                + self._var["Q_DHWTank_in"] * p_hot_water_cop
                == self._var["E_DHW_HP_out"] * p_hot_water_cop_tank * p_hot_water_cop
                + self._var["Q_HeatingElement_DHW"]
            )
            model.add_constraints(
                self._var["E_DHW_HP_out"] + self._var["E_Heating_HP_out"] <= self.SpaceHeating_MaxBoilerPower
            )

            self._fix_zero(model, "Fuel")
            self._fix_zero(model, "Q_DHW_Boiler_out")
            self._fix_zero(model, "Q_Heating_Boiler_out")
        else:
            model.add_constraints(
                self._var["Q_HeatingTank_bypass"] + self._var["Q_HeatingTank_in"]
                == self._var["Q_Heating_Boiler_out"] + self._var["Q_HeatingElement_heat"]
            )
            model.add_constraints(
                self._var["Q_DHWTank_bypass"] + self._var["Q_DHWTank_in"]
                == self._var["Q_DHW_Boiler_out"] + self._var["Q_HeatingElement_DHW"]
            )
            model.add_constraints(
                self._var["Q_DHW_Boiler_out"] + self._var["Q_Heating_Boiler_out"] <= self.SpaceHeating_MaxBoilerPower
            )
            model.add_constraints(
                self._var["Q_DHW_Boiler_out"] + self._var["Q_Heating_Boiler_out"]
                == self._var["Fuel"] * self.fuel_boiler_efficiency
            )
            self._fix_zero(model, "E_Heating_HP_out")
            self._fix_zero(model, "E_DHW_HP_out")

        # (7) Cooling
        if has_cooling:
            model.add_constraints(self._var["E_RoomCooling"] == self._var["Q_RoomCooling"] / p_cooling_cop)
        else:
            self._fix_zero(model, "Q_RoomCooling")
            self._fix_zero(model, "E_RoomCooling")

        # (8) PV split and feed
        model.add_constraints(
            p_pv == self._var["PV2EV"] + self._var["PV2Load"] + self._var["PV2Bat"] + self._var["PV2Grid"]
        )
        model.add_constraints(self._var["Feed2Grid"] == self._var["PV2Grid"])

        # (9) Battery
        model.add_constraints(self._var["BatCharge"] == self._var["PV2Bat"] + self._var["Grid2Bat"] + self._var["EV2Bat"])
        model.add_constraints(self._var["BatDischarge"] == self._var["Bat2Load"] + self._var["Bat2EV"])
        model.add_constraints(
            self._ati(self._var["BatSoC"], 0)
            == self._ati(self._var["BatCharge"], 0) * self.scenario.battery.charge_efficiency
            - self._ati(self._var["BatDischarge"], 0) * (1 + (1 - self.scenario.battery.discharge_efficiency))
        )
        for idx in range(1, self.HOURS_PER_YEAR):
            model.add_constraints(
                self._ati(self._var["BatSoC"], idx)
                == self._ati(self._var["BatSoC"], idx - 1)
                + self._ati(self._var["BatCharge"], idx) * self.scenario.battery.charge_efficiency
                - self._ati(self._var["BatDischarge"], idx) * (1 + (1 - self.scenario.battery.discharge_efficiency))
            )
        if has_battery:
            self._add_ub(model, "Grid2Bat", float(self.scenario.battery.charge_power_max))
            self._add_ub(model, "Bat2Load", float(self.scenario.battery.discharge_power_max))
            self._add_ub(model, "BatSoC", float(self.scenario.battery.capacity))
            self._add_ub(model, "BatCharge", float(self.scenario.battery.charge_power_max))
            self._add_ub(model, "BatDischarge", float(self.scenario.battery.discharge_power_max))
            if has_pv:
                self._add_ub(model, "PV2Bat", float(self.scenario.battery.charge_power_max))
            else:
                self._fix_zero(model, "PV2Bat")
        else:
            for name in ["Grid2Bat", "Bat2Load", "BatSoC", "BatCharge", "BatDischarge", "PV2Bat"]:
                self._fix_zero(model, name)

        # (10) EV
        model.add_constraints(self._var["EVCharge"] == self._var["PV2EV"] + self._var["Grid2EV"] + self._var["Bat2EV"])
        model.add_constraints(self._var["EVDischarge"] == p_ev_demand + self._var["EV2Load"] + self._var["EV2Bat"])
        model.add_constraints(
            self._ati(self._var["EVSoC"], 0)
            == float(self.scenario.vehicle.capacity)
            + self._ati(self._var["EVCharge"], 0) * float(self.scenario.vehicle.charge_efficiency)
            - self._ati(self._var["EVDischarge"], 0) / float(self.scenario.vehicle.discharge_efficiency)
        )
        for idx in range(1, self.HOURS_PER_YEAR):
            model.add_constraints(
                self._ati(self._var["EVSoC"], idx)
                == self._ati(self._var["EVSoC"], idx - 1)
                + self._ati(self._var["EVCharge"], idx) * float(self.scenario.vehicle.charge_efficiency)
                - self._ati(self._var["EVDischarge"], idx) / float(self.scenario.vehicle.discharge_efficiency)
            )

        if has_ev:
            ev_discharge_ub = self._arr(self.create_upper_bound_ev_discharge())
            self._add_ub(model, "EVSoC", float(self.scenario.vehicle.capacity))
            self._add_ub(model, "EVCharge", float(self.scenario.vehicle.charge_power_max))
            model.add_constraints(self._var["EVDischarge"] <= ev_discharge_ub)
            if not has_pv:
                self._fix_zero(model, "PV2EV")

            for idx, at_home in enumerate(self._arr(self.EVAtHomeProfile), start=1):
                if round(at_home) == 0:
                    for name in ["Grid2EV", "Bat2EV", "PV2EV", "EVCharge", "EV2Load", "EV2Bat"]:
                        model.add_constraints(self._at(self._var[name], idx) == 0)

            if has_battery:
                if float(self.EVOptionV2B or 0) == 0:
                    self._fix_zero(model, "EV2Bat")
                    self._fix_zero(model, "EV2Load")
            else:
                self._fix_zero(model, "EV2Bat")
                self._fix_zero(model, "Bat2EV")
                if float(self.EVOptionV2B or 0) == 0:
                    self._fix_zero(model, "EV2Load")
        else:
            for name in ["Grid2EV", "Bat2EV", "PV2EV", "EVSoC", "EVCharge", "EVDischarge", "EV2Load", "EV2Bat"]:
                self._fix_zero(model, name)

        # (11) Electricity demand and supply
        heating_element_eff = float(self.HeatingElement_efficiency if self.HeatingElement_efficiency > 0 else 1)
        if float(self.HeatingElement_power or 0) == 0:
            self._fix_zero(model, "Q_HeatingElement")
            self._fix_zero(model, "Q_HeatingElement_heat")
            self._fix_zero(model, "Q_HeatingElement_DHW")
        else:
            self._add_ub(model, "Q_HeatingElement", float(self.HeatingElement_power))
            self._add_ub(model, "Q_HeatingElement_heat", float(self.HeatingElement_power))
            self._add_ub(model, "Q_HeatingElement_DHW", float(self.HeatingElement_power))

        model.add_constraints(
            self._var["Load"]
            == p_base_load
            + self._var["E_Heating_HP_out"]
            + self._var["Q_HeatingElement"] / heating_element_eff
            + self._var["E_RoomCooling"]
            + self._var["E_DHW_HP_out"]
        )
        model.add_constraints(self._var["Grid"] == self._var["Grid2Load"] + self._var["Grid2Bat"] + self._var["Grid2EV"])
        model.add_constraints(
            self._var["Load"]
            == self._var["Grid2Load"] + self._var["PV2Load"] + self._var["Bat2Load"] + self._var["EV2Load"]
        )

        # (12) Bounds that OptConfig applies
        max_t_room, min_t_room = self.generate_target_indoor_temperature(temperature_offset=3)
        model.add_constraints(self._var["T_Room"] <= self._arr(max_t_room))
        model.add_constraints(self._var["T_Room"] >= self._arr(min_t_room))
        self._add_ub(model, "T_BuildingMass", 100)

        if is_hp:
            self._add_ub(model, "E_Heating_HP_out", float(self.SpaceHeating_MaxBoilerPower))
        else:
            self._add_ub(model, "Q_Heating_Boiler_out", float(self.SpaceHeating_MaxBoilerPower))
            self._add_ub(model, "Q_DHW_Boiler_out", float(self.SpaceHeating_MaxBoilerPower))

        if has_hot_tank:
            lb = cpw * hot_tank_size * (273.15 + float(self.scenario.hot_water_tank.temperature_min))
            ub = cpw * hot_tank_size * (273.15 + float(self.scenario.hot_water_tank.temperature_max))
            self._add_lb(model, "Q_DHWTank", lb)
            self._add_ub(model, "Q_DHWTank", ub)

        self._add_ub(model, "E_DHW_HP_out", float(self.SpaceHeating_MaxBoilerPower))

        if has_space_tank:
            lb = cpw * space_tank_size * (273.15 + float(self.scenario.space_heating_tank.temperature_min))
            ub = cpw * space_tank_size * (273.15 + float(self.scenario.space_heating_tank.temperature_max))
            self._add_lb(model, "Q_HeatingTank", lb)
            self._add_ub(model, "Q_HeatingTank", ub)

        if not has_pv:
            self._fix_zero(model, "PV2Load")
            self._fix_zero(model, "PV2Bat")
            self._fix_zero(model, "PV2Grid")

        model.add_objective(
            (
                self._var["Grid"] * p_elec_price
                + self._var["Fuel"] * p_fuel_price
                - self._var["Feed2Grid"] * p_fit
            ).sum()
        )

        return model

    def _build_result_from_solution(self):
        result = {}
        for key in self._iter_result_var_names():
            if key == "T_outside":
                result[key] = self._arr(self.T_outside)
            elif key == "Q_Solar":
                result[key] = self._arr(self.Q_Solar)
            elif key == "SpaceHeatingHourlyCOP":
                result[key] = self._arr(self.SpaceHeatingHourlyCOP)
            elif key == "SpaceHeatingHourlyCOP_tank":
                result[key] = self._arr(self.SpaceHeatingHourlyCOP_tank)
            elif key == "HotWaterProfile":
                result[key] = self._arr(self.HotWaterProfile)
            elif key == "HotWaterHourlyCOP":
                result[key] = self._arr(self.HotWaterHourlyCOP)
            elif key == "HotWaterHourlyCOP_tank":
                result[key] = self._arr(self.HotWaterHourlyCOP_tank)
            elif key == "CoolingHourlyCOP":
                result[key] = self._arr(self.CoolingHourlyCOP)
            elif key == "PhotovoltaicProfile":
                result[key] = self._arr(self.PhotovoltaicProfile)
            elif key == "EVDemandProfile":
                result[key] = self._arr(self.EVDemandProfile)
            elif key == "ElectricityPrice":
                result[key] = self._arr(self.ElectricityPrice)
            elif key == "FiT":
                result[key] = self._arr(self.FiT)
            elif key == "FuelPrice":
                if self._is_hp():
                    result[key] = self._zeros()
                else:
                    result[key] = self._arr(self.scenario.energy_price.__dict__[self.scenario.boiler.type])
            elif key == "BaseLoadProfile":
                result[key] = self._arr(self.BaseLoadProfile)
            else:
                result[key] = self._var[key].solution.to_numpy()
        return result

    def solve(self, instance=None):
        self.logger.info("starting solving Linopy backend (full model).")
        try:
            import linopy  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Linopy backend requested but dependency 'linopy' is not installed."
            ) from exc

        model = self._build_model()
        solver_name = get_solver_name(default="gurobi")
        status, termination = model.solve(solver_name=solver_name)

        solved = "optimal" in str(termination).lower()
        if not solved:
            self.logger.warning(
                "Linopy backend did not reach optimal status: "
                f"status={status}, termination={termination}, solver={solver_name}"
            )
            return None, False

        result = self._build_result_from_solution()
        total_cost = float(
            (
                result["Grid"] * result["ElectricityPrice"]
                + result["Fuel"] * result["FuelPrice"]
                - result["Feed2Grid"] * result["FiT"]
            ).sum()
        )

        output = LinopyResultModel(total_cost=total_cost)
        for key, values in result.items():
            setattr(output, key, values)
        return output, True
