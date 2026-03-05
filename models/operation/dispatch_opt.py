import logging

from pyomo.opt import TerminationCondition

from models.operation.physics_model import OperationModel
from models.operation.opt_pyomo_config import OptConfig
from models.operation.solver import get_solver_interface
from models.operation.solver import get_solver_options
from models.operation.solver import get_solver_name
from models.operation.solver import solve_model


class OptOperationModel(OperationModel):

    # @performance_counter
    def solve(self, instance):
        logger = logging.getLogger(f"{self.scenario.config.project_name}")
        logger.info("starting solving Opt model.")
        instance = OptConfig(self).config_instance(instance)
        solver_name = get_solver_name(default="gurobi")
        solver_interface = get_solver_interface(default="shell")
        solver_options = get_solver_options()
        results = solve_model(
            instance,
            solver_name=solver_name,
            solver_options=solver_options,
            solver_interface=solver_interface,
            tee=False,
        )
        if results.solver.termination_condition == TerminationCondition.optimal:
            instance.solutions.load_from(results)
            logger.info(
                f"OptCost: {round(instance.total_operation_cost_rule(), 2)} "
                f"(solver={solver_name}, interface={solver_interface})"
            )
            solved = True
        else:
            logger.warning(f'Infeasible Scenario Warning!!!!!!!!!!!!!!!!!!!!!! --> ID_Scenario = {self.scenario.scenario_id}')
            solved = False
        return instance, solved
