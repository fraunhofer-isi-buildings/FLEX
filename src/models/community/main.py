import os
from typing import Optional, List

import pyomo.common.errors as pyo_errors
from src.models.community.aggregator import Aggregator
from src.models.community.data_collector import CommunityDataCollector
from src.models.community.model import CommunityModel
from src.models.community.scenario import CommunityScenario
from src.models.community.validation import validate_community_inputs
from src.utils.config import Config
from src.utils.db import create_db_conn
from src.utils.func import get_logger
from src.utils.tables import InputTables

logger = get_logger(__file__)


def run_community_model(
    config: "Config",
    community_scenario_ids: Optional[List[int]] = None,
    operation_scenario_ids: Optional[List[int]] = None,
    plot_grid: bool = False,
):
    db = create_db_conn(config)
    logger.info(f"Importing the FLEX-Operation results...")
    community_scenario = db.read_dataframe(InputTables.CommunityScenario.name)
    operation_scenario = db.read_dataframe(InputTables.CommunityScenario_OperationScenario.name)
    community_energy_price = db.read_dataframe(InputTables.CommunityScenario_EnergyPrice.name)
    community_battery_component = db.read_dataframe(InputTables.CommunityScenario_Component_Battery.name)
    ref_operation_result_hour = db.read_dataframe(InputTables.CommunityScenario_Household_RefHour.name)
    ref_operation_result_year = db.read_dataframe(InputTables.CommunityScenario_Household_RefYear.name)
    validate_community_inputs(
        community_scenario=community_scenario,
        operation_scenario=operation_scenario,
        ref_operation_result_hour=ref_operation_result_hour,
        ref_operation_result_year=ref_operation_result_year,
        community_energy_price=community_energy_price,
        community_battery_component=community_battery_component,
    )
    if community_scenario_ids is None:
        community_scenario_ids = community_scenario["ID_Scenario"].unique()
    community_scenario_ids = [int(v) for v in community_scenario_ids]
    if operation_scenario_ids is None:
        operation_scenario_ids = operation_scenario["ID_Scenario"].unique()
    operation_scenario_ids = [int(v) for v in operation_scenario_ids]

    solver_failures = 0
    max_solver_failures = int(os.getenv("FLEX_COMMUNITY_MAX_SOLVER_FAILURES", "3"))
    fail_ratio_limit = float(os.getenv("FLEX_COMMUNITY_MAX_SOLVER_FAIL_RATIO", "0.5"))
    total_scenarios = len(community_scenario_ids)
    for id_community_scenario in community_scenario_ids:
        logger.info(f"FLEX-Community Model --> ID_Scenario = {id_community_scenario}.")
        scenario = CommunityScenario(id_community_scenario, config)
        scenario.operation_scenario_ids = operation_scenario_ids
        scenario.operation_scenario = operation_scenario
        scenario.ref_operation_result_hour = ref_operation_result_hour
        scenario.ref_operation_result_year = ref_operation_result_year
        scenario.setup(battery_table=community_battery_component)
        if plot_grid:
            scenario.plot_community_grid()
        opt_instance = Aggregator().create_opt_instance()
        try:
            community_model = CommunityModel(scenario)
            community_model.solve_aggregator_p2p_trading()
            opt_instance = community_model.solve_aggregator_optimization(opt_instance)
            CommunityDataCollector(
                model=community_model,
                opt_instance=opt_instance,
                scenario_id=scenario.scenario_id,
                config=config
            ).run()
        except ValueError as exc:
            logger.error(f"Configuration error for scenario {scenario.scenario_id}: {exc}")
            raise
        except (RuntimeError, pyo_errors.ApplicationError) as exc:
            solver_failures += 1
            logger.warning(f"Solver failed for scenario {scenario.scenario_id}: {exc}")
            if solver_failures > max_solver_failures:
                raise RuntimeError(
                    f"Too many community solver failures: {solver_failures}>{max_solver_failures}"
                ) from exc
            if total_scenarios > 0 and solver_failures / total_scenarios > fail_ratio_limit:
                raise RuntimeError(
                    f"Community solver failure ratio exceeded: {solver_failures}/{total_scenarios}"
                    f" > {fail_ratio_limit:.2%}"
                ) from exc
