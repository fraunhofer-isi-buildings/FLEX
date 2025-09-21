import os

from models.operation.main import run_operation_model
from plotters.operation import household_load_balance
from utils.config import Config
from utils.db import init_project_db


def get_config(project_name: str):
    return Config(
        project_name=project_name,
        project_path=os.path.join(os.path.dirname(__file__), f"{project_name}")
    )


def run_flex_operation_model(config: "Config"):
    init_project_db(config)
    # scenario_ids = list(range(1, 25)) + list(range(37, 45)) + list(range(49, 53))  # group 1
    # scenario_ids = list(range(25, 31)) + list(range(45, 49))  # group 2
    scenario_ids = list(range(31, 37))  # group 3
    print(scenario_ids)
    run_operation_model(config=config, save_hour=True, scenario_ids=scenario_ids)
    # run_operation_model(config=config, save_hour=True)


def run_flex_operation_plotter(config: "Config"):
    household_load_balance(config, scenario_ids=[1])


if __name__ == "__main__":

    cfg = get_config("zvei")
    run_flex_operation_model(cfg)
    # run_flex_operation_plotter(cfg)
