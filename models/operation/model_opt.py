import logging

from pyomo.opt import TerminationCondition

from models.operation.model_base import OperationModel
from models.operation.opt_config import OptConfig
from models.operation.opt_structure import OptInstance
from models.operation.solver import get_solver_name
from models.operation.solver import solve_model


class OptOperationModel(OperationModel):

    # @performance_counter
    def solve(self, instance):
        logger = logging.getLogger(f"{self.scenario.config.project_name}")
        logger.info("starting solving Opt model.")
        instance = OptConfig(self).config_instance(instance)
        solver_name = get_solver_name(default="gurobi")
        results = solve_model(instance, solver_name=solver_name, tee=False)
        if results.solver.termination_condition == TerminationCondition.optimal:
            instance.solutions.load_from(results)
            logger.info(
                f"OptCost: {round(instance.total_operation_cost_rule(), 2)} "
                f"(solver={solver_name})"
            )
            solved = True
        else:
            print(f'Infeasible Scenario Warning!!!!!!!!!!!!!!!!!!!!!! --> ID_Scenario = {self.scenario.scenario_id}')
            logger.warning(f'Infeasible Scenario Warning!!!!!!!!!!!!!!!!!!!!!! --> ID_Scenario = {self.scenario.scenario_id}')
            solved = False
        return instance, solved
