from __future__ import annotations

from typing import Iterable

import pandas as pd


def _require_columns(df: pd.DataFrame, required: Iterable[str], table_name: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{table_name} missing required columns: {missing}")


def validate_community_inputs(
    community_scenario: pd.DataFrame,
    operation_scenario: pd.DataFrame,
    ref_operation_result_hour: pd.DataFrame,
    ref_operation_result_year: pd.DataFrame,
    community_energy_price: pd.DataFrame,
    community_battery_component: pd.DataFrame,
) -> None:
    _require_columns(
        community_scenario,
        [
            "ID_Scenario",
            "id_electricity",
            "id_electricity_feed_in",
            "aggregator_household_battery_control",
            "aggregator_battery_size",
        ],
        "CommunityScenario",
    )
    _require_columns(operation_scenario, ["ID_Scenario", "ID_Battery"], "CommunityScenario_OperationScenario")
    _require_columns(ref_operation_result_hour, ["ID_Scenario"], "CommunityScenario_Household_RefHour")
    _require_columns(ref_operation_result_year, ["ID_Scenario"], "CommunityScenario_Household_RefYear")
    _require_columns(community_battery_component, ["ID_Battery", "capacity"], "CommunityScenario_Component_Battery")

    for sid, size in ref_operation_result_hour.groupby("ID_Scenario").size().items():
        if int(size) != 8760:
            raise ValueError(f"RefHour rows for ID_Scenario={sid} must be 8760, got {size}.")

    op_ids = set(int(v) for v in operation_scenario["ID_Scenario"].unique())
    hour_ids = set(int(v) for v in ref_operation_result_hour["ID_Scenario"].unique())
    year_ids = set(int(v) for v in ref_operation_result_year["ID_Scenario"].unique())
    missing_hour = sorted(op_ids - hour_ids)
    missing_year = sorted(op_ids - year_ids)
    if missing_hour:
        raise ValueError(f"Missing RefHour results for operation scenarios: {missing_hour}")
    if missing_year:
        raise ValueError(f"Missing RefYear results for operation scenarios: {missing_year}")

    price_cols = set(community_energy_price.columns)
    for _, row in community_scenario.iterrows():
        e_col = f"electricity_{int(row['id_electricity'])}"
        f_col = f"electricity_feed_in_{int(row['id_electricity_feed_in'])}"
        if e_col not in price_cols:
            raise ValueError(f"Community energy price column missing: {e_col}")
        if f_col not in price_cols:
            raise ValueError(f"Community energy price column missing: {f_col}")

    battery_ids = set(int(v) for v in community_battery_component["ID_Battery"].unique())
    referenced_batteries = set(int(v) for v in operation_scenario["ID_Battery"].unique())
    missing_battery_ids = sorted(referenced_batteries - battery_ids)
    if missing_battery_ids:
        raise ValueError(f"Missing battery component IDs: {missing_battery_ids}")
