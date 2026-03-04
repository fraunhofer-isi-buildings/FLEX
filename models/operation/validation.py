from __future__ import annotations

from typing import Dict, Iterable

import pandas as pd

from models.operation.constants import OperationScenarioComponent
from utils.tables import InputTables


def _require_tables(input_tables: Dict[str, pd.DataFrame], table_names: Iterable[str]) -> None:
    missing = [name for name in table_names if name not in input_tables]
    if missing:
        raise ValueError(f"Missing required input tables: {missing}")


def _require_columns(df: pd.DataFrame, table_name: str, columns: Iterable[str]) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in {table_name}: {missing}")


def _assert_hourly_rows(df: pd.DataFrame, table_name: str, expected_rows: int = 8760) -> None:
    if len(df) != expected_rows:
        raise ValueError(
            f"{table_name} must have {expected_rows} rows, got {len(df)}."
        )


def _as_int(value) -> int:
    # Handles numpy/pandas numeric scalars safely.
    return int(float(value))


def validate_operation_inputs(
    input_tables: Dict[str, pd.DataFrame],
    scenario_ids: Iterable[int],
) -> None:
    """Validate operation inputs before model execution.

    This function only validates schema and references; it does not alter inputs.
    """
    required_tables = [
        InputTables.OperationScenario.name,
        InputTables.OperationScenario_Component_Building.name,
        InputTables.OperationScenario_Component_Boiler.name,
        InputTables.OperationScenario_Component_SpaceHeatingTank.name,
        InputTables.OperationScenario_Component_HotWaterTank.name,
        InputTables.OperationScenario_Component_PV.name,
        InputTables.OperationScenario_Component_Battery.name,
        InputTables.OperationScenario_Component_Vehicle.name,
        InputTables.OperationScenario_Component_Behavior.name,
        InputTables.OperationScenario_Component_EnergyPrice.name,
        InputTables.OperationScenario_Component_HeatingElement.name,
        InputTables.OperationScenario_Component_SpaceCoolingTechnology.name,
        InputTables.OperationScenario_Component_Region.name,
        InputTables.OperationScenario_BehaviorProfile.name,
        InputTables.OperationScenario_DrivingProfile_ParkingHome.name,
        InputTables.OperationScenario_DrivingProfile_Distance.name,
        InputTables.OperationScenario_EnergyPrice.name,
        InputTables.OperationScenario_RegionWeather.name,
    ]
    _require_tables(input_tables, required_tables)

    scenario_table = input_tables[InputTables.OperationScenario.name]
    _require_columns(scenario_table, InputTables.OperationScenario.name, ["ID_Scenario"])
    if scenario_table["ID_Scenario"].duplicated().any():
        dup = sorted(scenario_table.loc[scenario_table["ID_Scenario"].duplicated(), "ID_Scenario"].unique())
        raise ValueError(f"Duplicate ID_Scenario in OperationScenario: {dup}")

    available_scenario_ids = set(_as_int(v) for v in scenario_table["ID_Scenario"].tolist())
    requested_scenario_ids = [_as_int(v) for v in scenario_ids]
    unknown = sorted(set(requested_scenario_ids) - available_scenario_ids)
    if unknown:
        raise ValueError(f"Requested scenario_ids not found in OperationScenario: {unknown}")

    # Check that component IDs in OperationScenario are resolvable in their tables.
    component_id_columns = [c for c in scenario_table.columns if c.startswith("ID_") and c != "ID_Scenario"]
    for id_col in component_id_columns:
        component_key = id_col.replace("ID_", "")
        if component_key not in OperationScenarioComponent.__dict__:
            continue
        component_info = OperationScenarioComponent.__dict__[component_key]
        component_table = input_tables[component_info.table_name]
        _require_columns(component_table, component_info.table_name, [component_info.id_name])
        valid_ids = set(_as_int(v) for v in component_table[component_info.id_name].dropna().tolist())
        for scenario_id in requested_scenario_ids:
            row = scenario_table.loc[scenario_table["ID_Scenario"] == scenario_id]
            if row.empty:
                continue
            component_id = row.iloc[0][id_col]
            if pd.isna(component_id):
                raise ValueError(
                    f"OperationScenario[{scenario_id}] has NaN in required column {id_col}."
                )
            if _as_int(component_id) not in valid_ids:
                raise ValueError(
                    f"OperationScenario[{scenario_id}] has {id_col}={component_id}, "
                    f"not found in {component_info.table_name}.{component_info.id_name}."
                )

    # Hourly tables should be complete.
    _assert_hourly_rows(input_tables[InputTables.OperationScenario_BehaviorProfile.name], InputTables.OperationScenario_BehaviorProfile.name)
    _assert_hourly_rows(input_tables[InputTables.OperationScenario_RegionWeather.name], InputTables.OperationScenario_RegionWeather.name)
    _assert_hourly_rows(input_tables[InputTables.OperationScenario_EnergyPrice.name], InputTables.OperationScenario_EnergyPrice.name)
    _assert_hourly_rows(input_tables[InputTables.OperationScenario_DrivingProfile_ParkingHome.name], InputTables.OperationScenario_DrivingProfile_ParkingHome.name)
    _assert_hourly_rows(input_tables[InputTables.OperationScenario_DrivingProfile_Distance.name], InputTables.OperationScenario_DrivingProfile_Distance.name)

    behavior_df = input_tables[InputTables.OperationScenario_BehaviorProfile.name]
    building_df = input_tables[InputTables.OperationScenario_Component_Building.name]
    _require_columns(
        building_df,
        InputTables.OperationScenario_Component_Building.name,
        ["ID_Building", "id_demand_profile_type"],
    )

    building_ids_in_use = set(
        _as_int(v)
        for v in scenario_table.loc[scenario_table["ID_Scenario"].isin(requested_scenario_ids), "ID_Building"].tolist()
    )
    dpt_in_use = set(
        _as_int(v)
        for v in building_df.loc[building_df["ID_Building"].isin(building_ids_in_use), "id_demand_profile_type"].tolist()
    )
    for dpt in sorted(dpt_in_use):
        required_behavior_cols = [
            f"appliance_electricity_dpt{dpt}",
            f"hot_water_dpt{dpt}",
            f"occupancy_dpt{dpt}",
            f"ventilation_supply_temperature_dpt{dpt}",
        ]
        _require_columns(behavior_df, InputTables.OperationScenario_BehaviorProfile.name, required_behavior_cols)

    # Check driving profile columns exist for each used vehicle profile id.
    vehicle_df = input_tables[InputTables.OperationScenario_Component_Vehicle.name]
    _require_columns(
        vehicle_df,
        InputTables.OperationScenario_Component_Vehicle.name,
        ["ID_Vehicle", "id_parking_at_home_profile", "id_distance_profile", "capacity"],
    )
    parking_df = input_tables[InputTables.OperationScenario_DrivingProfile_ParkingHome.name]
    distance_df = input_tables[InputTables.OperationScenario_DrivingProfile_Distance.name]
    vehicle_ids_in_use = set(
        _as_int(v)
        for v in scenario_table.loc[scenario_table["ID_Scenario"].isin(requested_scenario_ids), "ID_Vehicle"].tolist()
    )
    used_vehicles = vehicle_df.loc[vehicle_df["ID_Vehicle"].isin(vehicle_ids_in_use)]
    for _, row in used_vehicles.iterrows():
        if float(row["capacity"]) == 0:
            continue
        p_col = str(_as_int(row["id_parking_at_home_profile"]))
        d_col = str(_as_int(row["id_distance_profile"]))
        if p_col not in parking_df.columns:
            raise ValueError(f"Missing parking profile column {p_col} in {InputTables.OperationScenario_DrivingProfile_ParkingHome.name}.")
        if d_col not in distance_df.columns:
            raise ValueError(f"Missing distance profile column {d_col} in {InputTables.OperationScenario_DrivingProfile_Distance.name}.")

    # Check PV orientation columns exist in weather table.
    pv_df = input_tables[InputTables.OperationScenario_Component_PV.name]
    weather_df = input_tables[InputTables.OperationScenario_RegionWeather.name]
    _require_columns(pv_df, InputTables.OperationScenario_Component_PV.name, ["ID_PV", "orientation"])
    pv_ids_in_use = set(
        _as_int(v)
        for v in scenario_table.loc[scenario_table["ID_Scenario"].isin(requested_scenario_ids), "ID_PV"].tolist()
    )
    orientations = set(
        str(v)
        for v in pv_df.loc[pv_df["ID_PV"].isin(pv_ids_in_use), "orientation"].dropna().tolist()
    )
    for orientation in sorted(orientations):
        col = f"pv_generation_{orientation}"
        if col not in weather_df.columns:
            raise ValueError(f"Missing weather generation column {col} in {InputTables.OperationScenario_RegionWeather.name}.")

    # Check price mapping columns exist.
    energy_price_component_df = input_tables[InputTables.OperationScenario_Component_EnergyPrice.name]
    energy_price_hourly_df = input_tables[InputTables.OperationScenario_EnergyPrice.name]
    _require_columns(
        energy_price_component_df,
        InputTables.OperationScenario_Component_EnergyPrice.name,
        ["ID_EnergyPrice"],
    )
    ep_ids_in_use = set(
        _as_int(v)
        for v in scenario_table.loc[scenario_table["ID_Scenario"].isin(requested_scenario_ids), "ID_EnergyPrice"].tolist()
    )
    ep_rows = energy_price_component_df.loc[energy_price_component_df["ID_EnergyPrice"].isin(ep_ids_in_use)]
    for _, row in ep_rows.iterrows():
        for col in row.index:
            if not col.startswith("id_"):
                continue
            value = row[col]
            if pd.isna(value):
                continue
            carrier = col.replace("id_", "")
            price_col = f"{carrier}_{_as_int(value)}"
            if price_col not in energy_price_hourly_df.columns:
                raise ValueError(
                    f"Missing price column {price_col} in {InputTables.OperationScenario_EnergyPrice.name}."
                )
