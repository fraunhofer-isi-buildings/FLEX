import os
import re
import shutil
import time
import logging
from typing import List
from typing import Optional
from typing import Iterable

import pandas as pd
from joblib import Parallel
from joblib import delayed
from tqdm import tqdm

from models.operation.data_collector import OptDataCollector
from models.operation.data_collector import RefDataCollector
from models.operation.dispatch_opt import OptOperationModel
from models.operation.input_tables import OPERATION_INPUT_TABLE_NAMES
from models.operation.dispatch_ref import RefOperationModel
from models.operation.opt_pyomo_structure import OptInstance
from models.operation.scenario import OperationScenario
from models.operation.validation import validate_operation_inputs
from utils.config import Config
from utils.db import create_db_conn
from utils.db import fetch_input_tables
from utils.file_store import read_table
from utils.file_store import write_table
from utils.tables import InputTables
from utils.tables import OutputTables


def _scenario_file_exists(folder: str, table_name: str, scenario_id: int, file_format: str) -> bool:
    suffix = ".parquet.gzip" if file_format == "parquet" else ".csv"
    return os.path.exists(os.path.join(folder, f"{table_name}_S{scenario_id}{suffix}"))


def _is_scenario_done_in_folder(
    folder: str,
    scenario_id: int,
    run_ref: bool,
    run_opt: bool,
    save_year: bool,
    save_month: bool,
    save_hour: bool,
    hour_file_format: str,
) -> bool:
    checks: List[bool] = []
    if run_ref:
        if save_hour:
            checks.append(_scenario_file_exists(folder, OutputTables.OperationResult_RefHour.name, scenario_id, hour_file_format))
        if save_month:
            checks.append(_scenario_file_exists(folder, OutputTables.OperationResult_RefMonth.name, scenario_id, "csv"))
        if save_year:
            checks.append(_scenario_file_exists(folder, OutputTables.OperationResult_RefYear.name, scenario_id, "csv"))
    if run_opt:
        if save_hour:
            checks.append(_scenario_file_exists(folder, OutputTables.OperationResult_OptHour.name, scenario_id, hour_file_format))
        if save_month:
            checks.append(_scenario_file_exists(folder, OutputTables.OperationResult_OptMonth.name, scenario_id, "csv"))
        if save_year:
            checks.append(_scenario_file_exists(folder, OutputTables.OperationResult_OptYear.name, scenario_id, "csv"))
    return bool(checks) and all(checks)


def _filter_pending_scenarios(
    scenario_ids: List[int],
    folders: Iterable[str],
    run_ref: bool,
    run_opt: bool,
    save_year: bool,
    save_month: bool,
    save_hour: bool,
    hour_file_format: str,
) -> List[int]:
    pending: List[int] = []
    check_folders = [f for f in folders if f and os.path.exists(f)]
    for scenario_id in scenario_ids:
        done_somewhere = any(
            _is_scenario_done_in_folder(
                folder=folder,
                scenario_id=scenario_id,
                run_ref=run_ref,
                run_opt=run_opt,
                save_year=save_year,
                save_month=save_month,
                save_hour=save_hour,
                hour_file_format=hour_file_format,
            )
            for folder in check_folders
        )
        if not done_somewhere:
            pending.append(scenario_id)
    return pending


def run_ref_model(
    scenario: "OperationScenario",
    config: "Config",
    save_year: bool = True,
    save_month: bool = False,
    save_hour: bool = False,
    hour_vars: Optional[List[str]] = None,
    hour_file_format: str = "parquet",
    aggregate_file_format: str = "csv",
):
    ref_model = RefOperationModel(scenario).solve()
    RefDataCollector(model=ref_model,
                     scenario_id=scenario.scenario_id,
                     config=config,
                     save_year=save_year,
                     save_month=save_month,
                     save_hour=save_hour,
                     hour_vars=hour_vars,
                     hour_file_format=hour_file_format,
                     aggregate_file_format=aggregate_file_format).run()


def run_opt_model(
    opt_instance,
    scenario: "OperationScenario",
    config: "Config",
    save_year: bool = True,
    save_month: bool = False,
    save_hour: bool = False,
    hour_vars: Optional[List[str]] = None,
    hour_file_format: str = "parquet",
    aggregate_file_format: str = "csv",
):
    opt_model, solve_status = OptOperationModel(scenario).solve(opt_instance)
    if solve_status:
        OptDataCollector(
            model=opt_model,
            scenario_id=scenario.scenario_id,
            config=config,
            save_year=save_year,
            save_month=save_month,
            save_hour=save_hour,
            hour_vars=hour_vars,
            hour_file_format=hour_file_format,
            aggregate_file_format=aggregate_file_format,
        ).run()


def run_operation_model(config: "Config",
                        scenario_ids: Optional[List[int]] = None,
                        run_ref: bool = True,
                        run_opt: bool = True,
                        save_year: bool = True,
                        save_month: bool = False,
                        save_hour: bool = False,
                        hour_vars: List[str] = None,
                        hour_file_format: str = "parquet",
                        aggregate_file_format: str = "csv",
                        clean_start: bool = False,
                        merge_aggregate_outputs: bool = True):

    logger = logging.getLogger(config.project_name)
    input_tables = fetch_input_tables(config, table_names=OPERATION_INPUT_TABLE_NAMES)
    if scenario_ids is None:
        scenario_ids = input_tables[InputTables.OperationScenario.name]["ID_Scenario"].to_list()
    if clean_start:
        create_db_conn(config).clear_database()
    scenario_ids = _filter_pending_scenarios(
        scenario_ids=scenario_ids,
        folders=[config.output],
        run_ref=run_ref,
        run_opt=run_opt,
        save_year=save_year,
        save_month=save_month,
        save_hour=save_hour,
        hour_file_format=hour_file_format,
    )
    if not scenario_ids:
        if merge_aggregate_outputs:
            _merge_operation_aggregate_outputs(
                config=config,
                save_year=save_year,
                save_month=save_month,
                aggregate_file_format=aggregate_file_format,
            )
        return
    validate_operation_inputs(input_tables=input_tables, scenario_ids=scenario_ids)
    input_indexes = OperationScenario.build_input_indexes(input_tables)
    opt_instance = None
    if run_opt:
        t0 = time.perf_counter()
        opt_instance = OptInstance().create_instance()
        logger.info(
            "Initialized OptInstance in %.3fs (task_id=%s).",
            time.perf_counter() - t0,
            config.task_id,
        )
    for scenario_id in tqdm(scenario_ids, desc=f"{config.project_name}"):
        scenario = OperationScenario(
            config=config,
            scenario_id=scenario_id,
            input_tables=input_tables,
            input_indexes=input_indexes,
        )
        if run_ref:
            run_ref_model(scenario=scenario, config=config, save_year=save_year, save_month=save_month,
                          save_hour=save_hour, hour_vars=hour_vars,
                          hour_file_format=hour_file_format, aggregate_file_format=aggregate_file_format)
        if run_opt:
            run_opt_model(opt_instance=opt_instance, scenario=scenario, config=config, save_year=save_year,
                          save_month=save_month, save_hour=save_hour, hour_vars=hour_vars,
                          hour_file_format=hour_file_format, aggregate_file_format=aggregate_file_format)

    if merge_aggregate_outputs:
        _merge_operation_aggregate_outputs(
            config=config,
            save_year=save_year,
            save_month=save_month,
            aggregate_file_format=aggregate_file_format,
        )


def _merge_one_table(
    folder: str,
    table_name: str,
    file_format: str,
) -> None:
    import glob

    suffix = ".parquet.gzip" if file_format == "parquet" else ".csv"
    merged_target = os.path.join(folder, f"{table_name}{suffix}")
    pattern = os.path.join(folder, f"{table_name}_S*{suffix}")
    files = sorted(glob.glob(pattern))
    if not files and not os.path.exists(merged_target):
        return

    scenario_frames = []
    for file in files:
        filename = os.path.basename(file)
        match = re.search(r"_S(\d+)\.", filename)
        if match is None:
            raise ValueError(f"Cannot parse scenario id from file name '{filename}'.")
        scenario_id = int(match.group(1))
        frame = read_table(
            file_name=f"{table_name}_S{scenario_id}",
            folder=folder,
            file_format=file_format,
        )
        scenario_frames.append(frame)
    if os.path.exists(merged_target):
        scenario_frames.insert(0, read_table(file_name=table_name, folder=folder, file_format=file_format))
    if not scenario_frames:
        return
    merged = pd.concat(scenario_frames, ignore_index=True)
    if "ID_Scenario" in merged.columns:
        dedup_cols = ["ID_Scenario"]
        if "Month" in merged.columns:
            dedup_cols.append("Month")
        merged = merged.drop_duplicates(subset=dedup_cols, keep="last")
    sort_cols = [c for c in ["ID_Scenario", "Month"] if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols).reset_index(drop=True)

    write_table(
        data_frame=merged,
        file_name=table_name,
        folder=folder,
        file_format=file_format,
    )
    for file in files:
        os.remove(file)

def _merge_operation_aggregate_outputs(
    config: "Config",
    save_year: bool,
    save_month: bool,
    aggregate_file_format: str,
) -> None:
    del aggregate_file_format
    aggregate_file_format = "csv"
    folder = config.output if config.task_output is None else config.task_output
    if save_year:
        for table_name in [
            OutputTables.OperationResult_RefYear.name,
            OutputTables.OperationResult_OptYear.name,
        ]:
            _merge_one_table(folder=folder, table_name=table_name, file_format=aggregate_file_format)
    if save_month:
        for table_name in [
            OutputTables.OperationResult_RefMonth.name,
            OutputTables.OperationResult_OptMonth.name,
        ]:
            _merge_one_table(folder=folder, table_name=table_name, file_format=aggregate_file_format)


def run_operation_model_parallel(
    config: "Config",
    task_num: int,
    run_ref: bool = True,
    run_opt: bool = True,
    save_year: bool = True,
    save_month: bool = False,
    save_hour: bool = False,
    hour_vars: List[str] = None,
    reset_task_workspaces: bool = True,
    hour_file_format: str = "parquet",
    aggregate_file_format: str = "csv",
    clean_start: bool = False,
):

    def create_task_workspaces():
        for task_id in range(1, task_num + 1):
            task_config = config.make_copy().set_task_id(task_id=task_id)
            if os.path.exists(task_config.task_output):
                shutil.rmtree(task_config.task_output)
            os.makedirs(task_config.task_output, exist_ok=True)

    def split_scenario_ids():
        all_scenario_ids = create_db_conn(config).read_dataframe(
            InputTables.OperationScenario.name, column_names=["ID_Scenario"]
        )["ID_Scenario"].tolist()
        folders_to_scan = [config.output]
        for task_id in range(1, task_num + 1):
            task_output = config.make_copy().set_task_id(task_id=task_id).task_output
            folders_to_scan.append(task_output)
        scenario_ids = _filter_pending_scenarios(
            scenario_ids=[int(v) for v in all_scenario_ids],
            folders=folders_to_scan,
            run_ref=run_ref,
            run_opt=run_opt,
            save_year=save_year,
            save_month=save_month,
            save_hour=save_hour,
            hour_file_format=hour_file_format,
        )
        chunk_size = max(1, (len(scenario_ids) + task_num - 1) // task_num) if scenario_ids else 1
        chunks = [
            [int(v) for v in scenario_ids[i * chunk_size:(i + 1) * chunk_size]]
            for i in range(task_num)
        ]
        return chunks

    def run_tasks():
        chunks = split_scenario_ids()
        tasks = [
            {
                "config": config.make_copy().set_task_id(task_id=task_id),
                "scenario_ids": chunks[task_id - 1],
                "run_ref": run_ref,
                "run_opt": run_opt,
                "save_year": save_year,
                "save_month": save_month,
                "save_hour": save_hour,
                "hour_vars": hour_vars,
                "hour_file_format": hour_file_format,
                "aggregate_file_format": aggregate_file_format,
                "merge_aggregate_outputs": False,
            }
            for task_id in range(1, task_num + 1)
        ]
        runnable_tasks = [task for task in tasks if task["scenario_ids"]]
        if not runnable_tasks:
            return
        Parallel(n_jobs=task_num)(delayed(run_operation_model)(**task) for task in runnable_tasks)

    def merge_task_results():

        def move_task_outputs():
            for task_id in range(1, task_num + 1):
                task_config = config.make_copy().set_task_id(task_id=task_id)
                for file_name in os.listdir(task_config.task_output):
                    if file_name.endswith(".parquet.gzip") or file_name.endswith(".csv"):
                        src = os.path.join(task_config.task_output, file_name)
                        dst = os.path.join(task_config.output, file_name)
                        if os.path.exists(dst):
                            os.remove(dst)
                        shutil.move(src, dst)

        move_task_outputs()

    def remove_task_folders():
        for task_id in range(1, task_num + 1):
            task_config = config.make_copy().set_task_id(task_id=task_id)
            if os.path.exists(task_config.task_output):
                shutil.rmtree(task_config.task_output)

    if clean_start:
        create_db_conn(config).clear_database()
    if reset_task_workspaces:
        create_task_workspaces()
    run_tasks()
    merge_task_results()
    _merge_operation_aggregate_outputs(
        config=config,
        save_year=save_year,
        save_month=save_month,
        aggregate_file_format=aggregate_file_format,
    )
    remove_task_folders()
