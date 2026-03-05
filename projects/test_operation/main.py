import os

from models.operation.main import run_operation_model
from models.operation.input_tables import OPERATION_INPUT_TABLE_NAMES
from plotters.operation import household_load_balance
from utils.config import Config
from utils.db import prepare_project_run


def get_config(project_name: str):
    return Config(
        project_name=project_name,
        project_path=os.path.dirname(__file__)
    )


def run_flex_operation_model(config: "Config"):
    hour_file_format = os.getenv("FLEX_OPERATION_HOUR_FILE_FORMAT", "parquet")
    clean_start = os.getenv("FLEX_OPERATION_CLEAN_START", "1") != "0"
    prepare_project_run(config, clean_start=clean_start, table_names=OPERATION_INPUT_TABLE_NAMES)
    run_operation_model(
        config=config,
        save_hour=True,
        hour_file_format=hour_file_format,
        clean_start=False,
    )


def run_flex_operation_plotter(config: "Config"):
    household_load_balance(config, scenario_ids=[1])


if __name__ == "__main__":

    cfg = get_config("test_operation")
    run_flex_operation_model(cfg)
    # run_flex_operation_plotter(cfg)
