import os
import re
from typing import List

import pandas as pd

from src.models.community.main import run_community_model
from src.plotters.community import aggregator_profit
from src.plotters.community import p2p_trading_amount
from src.plotters.community import battery_operation
from src.utils.config import Config
from src.utils.db import prepare_project_run
from src.utils.file_store import read_table_smart
from src.utils.tables import InputTables
from src.utils.tables import OutputTables


def copy_operation_tables(
    operation_output_folder: str = None,
    operation_input_folder: str = None,
    community_input_folder: str = None
):
    project_dir = os.path.dirname(__file__)
    if operation_output_folder is None:
        operation_output_folder = os.path.normpath(os.path.join(project_dir, "../test_operation/output"))
    if operation_input_folder is None:
        operation_input_folder = os.path.normpath(os.path.join(project_dir, "../test_operation/input"))
    if community_input_folder is None:
        community_input_folder = os.path.join(project_dir, "input")

    def read_operation_input_table(table_name: str) -> pd.DataFrame:
        csv_path = os.path.join(operation_input_folder, f"{table_name}.csv")
        xlsx_path = os.path.join(operation_input_folder, f"{table_name}.xlsx")
        if os.path.exists(csv_path):
            return pd.read_csv(csv_path)
        if os.path.exists(xlsx_path):
            return pd.read_excel(xlsx_path)
        raise FileNotFoundError(
            f"Cannot find operation input table {table_name} in {operation_input_folder}"
        )

    direct_copy_tables = {
        InputTables.OperationScenario.name: InputTables.CommunityScenario_OperationScenario.name,
        InputTables.OperationScenario_EnergyPrice.name: InputTables.CommunityScenario_EnergyPrice.name,
        InputTables.OperationScenario_Component_Battery.name: InputTables.CommunityScenario_Component_Battery.name,
    }
    for source, target in direct_copy_tables.items():
        read_operation_input_table(source).to_csv(
            os.path.join(community_input_folder, f'{target}.csv'),
            index=False,
        )

    read_table_smart(
        file_name=OutputTables.OperationResult_RefYear.name,
        folder=operation_output_folder,
    ).to_csv(
        os.path.join(community_input_folder, f'{InputTables.CommunityScenario_Household_RefYear.name}.csv'),
        index=False,
    )


def copy_household_ref_hour(
    operation_scenario_ids: List[int] = None,
    operation_output_folder: str = None,
    community_input_folder: str = None
):
    project_dir = os.path.dirname(__file__)
    if operation_output_folder is None:
        operation_output_folder = os.path.normpath(os.path.join(project_dir, "../test_operation/output"))
    if community_input_folder is None:
        community_input_folder = os.path.join(project_dir, "input")

    if operation_scenario_ids is None:
        operation_scenario_ids = []
        for file_name in os.listdir(operation_output_folder):
            if not file_name.startswith(f"{OutputTables.OperationResult_RefHour.name}_S"):
                continue
            match = re.search(r"_S(\d+)\.", file_name)
            if match is None:
                continue
            operation_scenario_ids.append(int(match.group(1)))
        operation_scenario_ids = sorted(set(operation_scenario_ids))

    operation_ref_hour_profiles: List[pd.DataFrame] = []
    for id_operation_scenario in operation_scenario_ids:
        operation_ref_hour_profiles.append(read_table_smart(
            file_name=f'{OutputTables.OperationResult_RefHour.name}_S{id_operation_scenario}',
            folder=operation_output_folder,
            column_names=[
                'ID_Scenario',
                'PhotovoltaicProfile',
                'Grid',
                'Load',
                'Feed2Grid',
                'BatSoC'
            ]
        ))
    pd.concat(operation_ref_hour_profiles, ignore_index=True).to_csv(
        os.path.join(community_input_folder, f'{InputTables.CommunityScenario_Household_RefHour.name}.csv'),
        index=False
    )


def run_flex_community_model(project_name: str):
    config = Config(project_name=project_name, project_path=os.path.dirname(__file__))
    prepare_project_run(config)
    run_community_model(config)


def run_flex_community_plotter(project_name: str):
    config = Config(project_name=project_name, project_path=os.path.dirname(__file__))
    aggregator_profit(config)
    p2p_trading_amount(config, id_scenario=1)
    battery_operation(config, id_scenario=1)


if __name__ == "__main__":
    copy_operation_tables()
    copy_household_ref_hour()
    run_flex_community_model("test_community")
    run_flex_community_plotter("test_community")
