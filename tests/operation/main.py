import itertools
import os
from typing import Dict, List

import numpy as np
import pandas as pd

from models.operation.main import run_operation_model
from models.operation.main import run_operation_model_parallel
from utils.config import Config
from utils.db import init_project_db
from plotters.operation import household_load_balance


def generate_operation_scenario_table() -> None:

    input_folder = "input"

    def get_component_scenario_ids() -> Dict[str, List[int]]:
        ext_read = {"xlsx": pd.read_excel,
                    "csv": pd.read_csv}
        component_scenario_ids = {}
        files = [file for file in os.listdir(input_folder) if file.startswith("OperationScenario_Component_")]
        for file in files:
            table_name, ext = file.split(".")
            id_component = f'ID_{table_name.split("_")[-1]}'
            df = ext_read[ext](os.path.join(input_folder, file))
            component_scenario_ids[id_component] = df[id_component].to_list()
            print(f'{id_component}: {df[id_component].to_list()}')
        return component_scenario_ids

    def generate_params_combination_df(params_values: Dict[str, List[int]]) -> pd.DataFrame:
        keys, values = zip(*params_values.items())
        df = pd.DataFrame([dict(zip(keys, v)) for v in itertools.product(*values)])
        return df

    scenario_df = generate_params_combination_df(params_values=get_component_scenario_ids())
    scenario_ids = np.array(range(1, 1 + len(scenario_df)))
    scenario_df.insert(loc=0, column="ID_Scenario", value=scenario_ids)
    scenario_df.to_excel(os.path.join(input_folder, "OperationScenario.xlsx"), index=False)


def run_flex_operation_model(project_name: str):
    config = Config(project_name=project_name, project_path=os.path.dirname(__file__))
    init_project_db(config)
    # run_operation_model(config=config, save_hour=True, scenario_ids=[1])
    run_operation_model_parallel(config=config, task_num=8, save_hour=True)


def run_flex_operation_plotter(project_name: str):
    config = Config(project_name=project_name, project_path=os.path.dirname(__file__))
    household_load_balance(config, scenario_ids=[3])


if __name__ == "__main__":
    generate_operation_scenario_table()
    # run_flex_operation_model("test_operation")
    run_flex_operation_plotter("test_operation")
