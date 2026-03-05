from dataclasses import dataclass
from typing import Dict
from typing import Iterable


@dataclass(frozen=True)
class ResultVarSpec:
    name: str
    save_hour: bool = True
    save_month: bool = False
    save_year: bool = False
    agg_month: str = "none"
    agg_year: str = "none"
    kind: str = "flow"


def _spec_hour(name: str, kind: str = "state") -> ResultVarSpec:
    return ResultVarSpec(name=name, save_hour=True, save_month=False, save_year=False, kind=kind)


def _spec_sum(name: str, kind: str = "flow") -> ResultVarSpec:
    return ResultVarSpec(
        name=name,
        save_hour=True,
        save_month=True,
        save_year=True,
        agg_month="sum",
        agg_year="sum",
        kind=kind,
    )


OPERATION_RESULT_SPECS: Dict[str, ResultVarSpec] = {
    "T_outside": _spec_hour("T_outside", kind="temperature"),
    "Q_Solar": _spec_sum("Q_Solar"),
    "SpaceHeatingHourlyCOP": _spec_hour("SpaceHeatingHourlyCOP", kind="cop"),
    "SpaceHeatingHourlyCOP_tank": _spec_hour("SpaceHeatingHourlyCOP_tank", kind="cop"),
    "Q_HeatingTank_in": _spec_sum("Q_HeatingTank_in"),
    "Q_HeatingTank_out": _spec_sum("Q_HeatingTank_out"),
    "Q_HeatingTank": _spec_hour("Q_HeatingTank", kind="state"),
    "Q_HeatingTank_bypass": _spec_sum("Q_HeatingTank_bypass"),
    "E_Heating_HP_out": _spec_sum("E_Heating_HP_out"),
    "Q_RoomHeating": _spec_sum("Q_RoomHeating"),
    "T_Room": _spec_hour("T_Room", kind="temperature"),
    "T_BuildingMass": _spec_hour("T_BuildingMass", kind="temperature"),
    "Q_HeatingElement": _spec_sum("Q_HeatingElement"),
    "Q_HeatingElement_DHW": _spec_sum("Q_HeatingElement_DHW"),
    "Q_HeatingElement_heat": _spec_sum("Q_HeatingElement_heat"),
    "HotWaterProfile": _spec_sum("HotWaterProfile"),
    "HotWaterHourlyCOP": _spec_hour("HotWaterHourlyCOP", kind="cop"),
    "HotWaterHourlyCOP_tank": _spec_hour("HotWaterHourlyCOP_tank", kind="cop"),
    "Q_DHWTank": _spec_hour("Q_DHWTank", kind="state"),
    "Q_DHWTank_out": _spec_sum("Q_DHWTank_out"),
    "Q_DHWTank_in": _spec_sum("Q_DHWTank_in"),
    "Q_DHWTank_bypass": _spec_sum("Q_DHWTank_bypass"),
    "E_DHW_HP_out": _spec_sum("E_DHW_HP_out"),
    "Q_RoomCooling": _spec_sum("Q_RoomCooling"),
    "E_RoomCooling": _spec_sum("E_RoomCooling"),
    "CoolingHourlyCOP": _spec_hour("CoolingHourlyCOP", kind="cop"),
    "PhotovoltaicProfile": _spec_sum("PhotovoltaicProfile"),
    "PV2Load": _spec_sum("PV2Load"),
    "PV2Bat": _spec_sum("PV2Bat"),
    "PV2Grid": _spec_sum("PV2Grid"),
    "PV2EV": _spec_sum("PV2EV"),
    "BatSoC": _spec_hour("BatSoC", kind="state"),
    "BatCharge": _spec_sum("BatCharge"),
    "BatDischarge": _spec_sum("BatDischarge"),
    "Bat2Load": _spec_sum("Bat2Load"),
    "Bat2EV": _spec_sum("Bat2EV"),
    "EVDemandProfile": _spec_sum("EVDemandProfile"),
    "EVSoC": _spec_hour("EVSoC", kind="state"),
    "EVCharge": _spec_sum("EVCharge"),
    "EVDischarge": _spec_sum("EVDischarge"),
    "EV2Bat": _spec_sum("EV2Bat"),
    "EV2Load": _spec_sum("EV2Load"),
    "ElectricityPrice": _spec_hour("ElectricityPrice", kind="price"),
    "FiT": _spec_hour("FiT", kind="price"),
    "FuelPrice": _spec_hour("FuelPrice", kind="price"),
    "Fuel": _spec_sum("Fuel"),
    "BaseLoadProfile": _spec_sum("BaseLoadProfile"),
    "Grid": _spec_sum("Grid"),
    "Grid2Load": _spec_sum("Grid2Load"),
    "Grid2Bat": _spec_sum("Grid2Bat"),
    "Grid2EV": _spec_sum("Grid2EV"),
    "Load": _spec_sum("Load"),
    "Feed2Grid": _spec_sum("Feed2Grid"),
}


def iter_operation_result_specs() -> Iterable[ResultVarSpec]:
    for key, spec in OPERATION_RESULT_SPECS.items():
        if key != spec.name:
            raise ValueError(f"Result registry key/spec mismatch: key='{key}', spec.name='{spec.name}'")
    return OPERATION_RESULT_SPECS.values()
