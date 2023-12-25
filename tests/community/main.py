import os
from typing import List

import pandas as pd

from models.community.main import run_community_model
from plotters.community import aggregator_profit
from plotters.community import p2p_trading_amount
from plotters.community import battery_operation
from utils.config import Config
from utils.db import DB
from utils.db import init_project_db
from utils.parquet import read_parquet
from utils.tables import InputTables
from utils.tables import OutputTables


def copy_operation_tables(
    operation_output_folder: str = f"../operation/output",
    operation_project_name: str = "test_operation",
    community_input_folder: str = "input"
):
    def copy_table(
            operation_table_name: str,
            community_table_name: str,
    ):
        db = DB(path=os.path.join(operation_output_folder, f"{operation_project_name}.sqlite"))
        db.read_dataframe(operation_table_name).to_csv(
            os.path.join(community_input_folder, f'{community_table_name}.csv'),
            index=False
        )

    tables = {
        InputTables.OperationScenario.name: InputTables.CommunityScenario_OperationScenario.name,
        InputTables.OperationScenario_EnergyPrice.name: InputTables.CommunityScenario_EnergyPrice.name,
        InputTables.OperationScenario_Component_Battery.name: InputTables.CommunityScenario_Component_Battery.name,
        OutputTables.OperationResult_RefYear.name: InputTables.CommunityScenario_Household_RefYear.name,
    }
    for source, target in tables.items():
        copy_table(operation_table_name=source, community_table_name=target)


def copy_household_ref_hour(
    operation_scenario_ids: List[int] = range(1, 161),
    operation_output_folder: str = f"../operation/output",
    community_input_folder: str = "input"
):
    operation_ref_hour_profiles: List[pd.DataFrame] = []
    for id_operation_scenario in operation_scenario_ids:
        operation_ref_hour_profiles.append(read_parquet(
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
    config = Config(project_name=project_name)
    init_project_db(config)
    run_community_model(config)


def run_flex_community_plotter(project_name: str):
    config = Config(project_name=project_name)
    aggregator_profit(config)
    p2p_trading_amount(config, id_scenario=1)
    battery_operation(config, id_scenario=1)


if __name__ == "__main__":
    copy_operation_tables()
    copy_household_ref_hour()
    run_flex_community_model("test_community")
    run_flex_community_plotter("test_community")
