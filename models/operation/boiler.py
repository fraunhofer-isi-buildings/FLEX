from __future__ import annotations

from enum import Enum
from typing import Literal


class BoilerType(str, Enum):
    AIR_HP = "air_hp"
    GROUND_HP = "ground_hp"
    ELECTRIC = "electric"
    GASES = "gases"
    SOLIDS = "solids"
    LIQUIDS = "liquids"
    DISTRICT_HEATING = "district_heating"


HP_BOILER_TYPES = {
    BoilerType.AIR_HP.value,
    BoilerType.GROUND_HP.value,
    BoilerType.ELECTRIC.value,
}
FUEL_BOILER_TYPES = {
    BoilerType.GASES.value,
    BoilerType.SOLIDS.value,
    BoilerType.LIQUIDS.value,
    BoilerType.DISTRICT_HEATING.value,
}
ALLOWED_BOILER_TYPES = HP_BOILER_TYPES | FUEL_BOILER_TYPES

BoilerClass = Literal["hp", "fuel"]


def normalize_boiler_type(value: str) -> str:
    if value is None:
        raise ValueError("boiler.type is None")
    return str(value).strip().lower()


def parse_boiler_type(value: str) -> BoilerType:
    normalized = normalize_boiler_type(value)
    try:
        return BoilerType(normalized)
    except ValueError as err:
        raise ValueError(
            f"Unsupported boiler.type '{value}'. Allowed: {sorted(ALLOWED_BOILER_TYPES)}"
        ) from err


def classify_boiler_type(value: str) -> BoilerClass:
    boiler_type = parse_boiler_type(value).value
    if boiler_type in HP_BOILER_TYPES:
        return "hp"
    return "fuel"


def is_hp_boiler(value: str) -> bool:
    return classify_boiler_type(value) == "hp"


def is_fuel_boiler(value: str) -> bool:
    return classify_boiler_type(value) == "fuel"
