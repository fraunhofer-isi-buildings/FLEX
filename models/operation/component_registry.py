from dataclasses import dataclass

from models.operation import components


class OperationComponentInfo:

    def __init__(
        self,
        name: str,
        table_name_override: str | None = None,
        profile_table_name: str | None = None,
    ):
        self.name = name
        self.camel_name = self.to_camel(name)
        self.id_name = f"ID_{self.camel_name}"
        self.class_var = getattr(components, self.camel_name)
        self._table_name_override = table_name_override
        self.profile_table_name = profile_table_name

    @staticmethod
    def to_camel(name: str) -> str:
        if name == "pv":
            return "PV"
        items = [item[0].upper() + item[1:] for item in name.split("_")]
        return "".join(items)

    @property
    def table_name(self) -> str:
        if self._table_name_override is not None:
            return self._table_name_override
        return f"OperationScenario_Component_{self.camel_name}"


@dataclass
class OperationScenarioComponent:
    Building = OperationComponentInfo("building")
    Boiler = OperationComponentInfo("boiler")
    HeatingElement = OperationComponentInfo("heating_element")
    SpaceHeatingTank = OperationComponentInfo("space_heating_tank")
    HotWaterTank = OperationComponentInfo("hot_water_tank")
    SpaceCoolingTechnology = OperationComponentInfo("space_cooling_technology")
    PV = OperationComponentInfo("pv")
    Battery = OperationComponentInfo("battery")
    Vehicle = OperationComponentInfo("vehicle")
    EnergyPrice = OperationComponentInfo(
        "energy_price",
        table_name_override="OperationScenario_Component_EnergyPrice",
        profile_table_name="OperationScenario_EnergyPrice",
    )
    Behavior = OperationComponentInfo("behavior")
