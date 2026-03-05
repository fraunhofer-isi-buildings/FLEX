import numpy as np
import pyomo.environ as pyo

from models.community.scenario import CommunityScenario
from models.operation.solver import solve_model
from utils.func import get_logger
logger = get_logger(__file__)


class CommunityModel:

    def __init__(self, scenario: "CommunityScenario"):
        self.scenario = scenario
        self.hours = scenario.hours

    def solve_aggregator_p2p_trading(self):
        self.p2p_trading = self.scenario.community_p2p_trading
        sell_price = self.scenario.electricity_price * self.scenario.aggregator_sell_price_factor
        buy_price = self.scenario.feed_in_price * self.scenario.aggregator_buy_price_factor
        self.p2p_trading_profit = np.sum(self.p2p_trading * (sell_price - buy_price))
        logger.info(f"p2p_profit: {self.p2p_trading_profit:.2f}")

    def solve_aggregator_optimization(self, instance):
        instance = self.config_instance(instance)
        result = solve_model(instance, tee=False)
        tc = result.solver.termination_condition
        if tc != pyo.TerminationCondition.optimal:
            raise RuntimeError(
                f"Solver terminated non-optimally: {tc} (scenario {self.scenario.scenario_id})"
            )
        logger.info(f"opt_profit: {instance.opt_profit_rule():.2f} | termination: {tc}")
        return instance

    def config_instance(self, instance):
        self.config_params(instance)
        self.config_boundaries(instance)
        return instance

    def config_params(self, instance):
        instance.battery_charge_efficiency = self.scenario.aggregator_battery_charge_efficiency
        instance.battery_discharge_efficiency = self.scenario.aggregator_battery_discharge_efficiency
        buy_price = self.scenario.feed_in_price * self.scenario.aggregator_buy_price_factor
        sell_price = self.scenario.electricity_price * self.scenario.aggregator_sell_price_factor
        instance.buy_price.store_values({t: float(v) for t, v in enumerate(buy_price, start=1)})
        instance.sell_price.store_values({t: float(v) for t, v in enumerate(sell_price, start=1)})

    def config_boundaries(self, instance):
        ctrl = self.scenario.aggregator_household_battery_control
        if ctrl == 0:
            battery_soc_ub = np.full(self.hours, self.scenario.aggregator_battery_size)
        elif ctrl == 1:
            battery_soc_ub = self.scenario.aggregator_battery_size + self.scenario.community_battery_size
        else:
            raise ValueError(
                f"CommunityScenario.aggregator_household_battery_control={ctrl}, expected 0 or 1."
            )
        for t in range(1, self.hours + 1):
            instance.battery_charge[t].setub(self.scenario.community_grid_feed[t - 1])
            instance.battery_discharge[t].setub(self.scenario.community_grid_consumption[t - 1])
            instance.battery_soc[t].setub(float(battery_soc_ub[t - 1]))
