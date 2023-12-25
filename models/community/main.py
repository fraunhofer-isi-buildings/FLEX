from typing import Optional, List
from models.community.aggregator import Aggregator
from models.community.data_collector import CommunityDataCollector
from models.community.model import CommunityModel
from models.community.scenario import CommunityScenario
from utils.config import Config
from utils.db import create_db_conn
from utils.func import get_logger
from utils.tables import InputTables

logger = get_logger(__file__)


def run_community_model(
    config: "Config",
    community_scenario_ids: Optional[List[int]] = None,
    operation_scenario_ids: Optional[List[int]] = None,
):
    db = create_db_conn(config)
    logger.info(f"Importing the FLEX-Operation results...")
    community_scenario = db.read_dataframe(InputTables.CommunityScenario.name)
    operation_scenario = db.read_dataframe(InputTables.CommunityScenario_OperationScenario.name)
    ref_operation_result_hour = db.read_dataframe(InputTables.CommunityScenario_Household_RefHour.name)
    ref_operation_result_year = db.read_dataframe(InputTables.CommunityScenario_Household_RefYear.name)
    if community_scenario_ids is None:
        community_scenario_ids = community_scenario["ID_Scenario"].unique()
    if operation_scenario_ids is None:
        operation_scenario_ids = operation_scenario["ID_Scenario"].unique()

    for id_community_scenario in community_scenario_ids:
        logger.info(f"FLEX-Community Model --> ID_Scenario = {id_community_scenario}.")
        scenario = CommunityScenario(id_community_scenario, config)
        scenario.operation_scenario_ids = operation_scenario_ids
        scenario.operation_scenario = operation_scenario
        scenario.ref_operation_result_hour = ref_operation_result_hour
        scenario.ref_operation_result_year = ref_operation_result_year
        scenario.setup()
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
        except ValueError:
            print(f'FLEX-Community Infeasible --> ID_Scenario = {scenario.scenario_id}')

