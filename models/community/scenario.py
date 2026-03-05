from typing import List, Optional

import numpy as np
import pandas as pd

from utils.config import Config
from utils.db import create_db_conn
from utils.plotter import Plotter
from utils.tables import InputTables
from models.community.household import Household


class CommunityScenario:

    def __init__(self, scenario_id: int, config: "Config"):
        self.scenario_id = scenario_id
        self.config = config
        self.db = create_db_conn(self.config)
        self.plotter = Plotter(config)
        self.operation_scenario: Optional[pd.DataFrame] = None
        self.ref_operation_result_hour: Optional[pd.DataFrame] = None
        self.ref_operation_result_year: Optional[pd.DataFrame] = None
        self.operation_scenario_ids: Optional[List[int]] = None
        self.hours: int = 8760
        self.region_code: Optional[str] = None
        self.year: Optional[int] = None
        self.aggregator_battery_size: Optional[float] = None
        self.aggregator_battery_charge_efficiency: Optional[float] = None
        self.aggregator_battery_discharge_efficiency: Optional[float] = None
        self.aggregator_household_battery_control: Optional[int] = None
        self.aggregator_buy_price_factor: Optional[float] = None
        self.aggregator_sell_price_factor: Optional[float] = None
        self.id_electricity: Optional[int] = None
        self.id_electricity_feed_in: Optional[int] = None
        self.households: Optional[List["Household"]] = []

    def _validate_injected_dependencies(self):
        required = {
            "operation_scenario": self.operation_scenario,
            "operation_scenario_ids": self.operation_scenario_ids,
            "ref_operation_result_hour": self.ref_operation_result_hour,
            "ref_operation_result_year": self.ref_operation_result_year,
        }
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise ValueError(
                f"CommunityScenario {self.scenario_id} missing injected dependencies: {missing}"
            )

    def setup(self, battery_table: Optional[pd.DataFrame] = None):
        self._validate_injected_dependencies()
        self.setup_scenario_params()
        self.setup_energy_price()
        self.setup_households()
        self.setup_community_results(battery_table=battery_table)

    def setup_scenario_params(self):
        community_scenarios = self.db.read_dataframe(InputTables.CommunityScenario.name)
        row = community_scenarios.loc[community_scenarios["ID_Scenario"] == self.scenario_id].iloc[0]
        self.region_code = row["region_code"]
        self.year = row["year"]
        self.aggregator_battery_size = row["aggregator_battery_size"]
        self.aggregator_battery_charge_efficiency = row["aggregator_battery_charge_efficiency"]
        self.aggregator_battery_discharge_efficiency = row["aggregator_battery_discharge_efficiency"]
        self.aggregator_household_battery_control = row["aggregator_household_battery_control"]
        self.aggregator_buy_price_factor = row["aggregator_buy_price_factor"]
        self.aggregator_sell_price_factor = row["aggregator_sell_price_factor"]
        self.id_electricity = row["id_electricity"]
        self.id_electricity_feed_in = row["id_electricity_feed_in"]

    def setup_energy_price(self):
        self.energy_prices = self.db.read_dataframe(InputTables.CommunityScenario_EnergyPrice.name)
        self.electricity_price = self.energy_prices[f"electricity_{self.id_electricity}"].to_numpy()
        self.feed_in_price = self.energy_prices[f"electricity_feed_in_{self.id_electricity_feed_in}"].to_numpy()

    def setup_households(self):
        self.households = []
        for id_scenario in self.operation_scenario_ids:
            household = Household(id_scenario)
            household.setup_component_ids(self.operation_scenario)
            household.setup_operation_result_hour(self.ref_operation_result_hour)
            household.setup_operation_result_year(self.ref_operation_result_year)
            self.households.append(household)

    def setup_community_results(self, battery_table: Optional[pd.DataFrame] = None):
        self.setup_community_pv_generation()
        self.setup_community_load()
        self.setup_community_grid_balance()
        self.setup_community_pv_self_consumption()
        self.setup_community_p2p_trading()
        self.setup_community_battery_size(battery_table=battery_table)

    def setup_community_pv_generation(self):
        self.community_pv_generation = np.zeros(self.hours, )
        for household in self.households:
            self.community_pv_generation += household.PhotovoltaicProfile_hour

    def setup_community_load(self):
        self.community_load = np.zeros(self.hours, )
        for household in self.households:
            self.community_load += household.Load_hour

    def setup_community_grid_balance(self):
        pv = self.community_pv_generation
        load = self.community_load
        self.community_pv_consumption = np.minimum(pv, load)
        self.community_grid_consumption = np.maximum(load - pv, 0)
        self.community_grid_feed = np.maximum(pv - load, 0)

    def setup_community_pv_self_consumption(self):
        self.community_pv_self_consumption = np.zeros(self.hours,)
        for household in self.households:
            self.community_pv_self_consumption += np.minimum(
                household.PhotovoltaicProfile_hour, household.Load_hour
            )

    def setup_community_p2p_trading(self):
        self.community_p2p_trading = self.community_pv_consumption - self.community_pv_self_consumption

    def setup_community_battery_size(self, battery_table: Optional[pd.DataFrame] = None):
        self.community_battery_size = np.zeros(self.hours,)
        df = (
            battery_table
            if battery_table is not None
            else self.db.read_dataframe(InputTables.CommunityScenario_Component_Battery.name)
        )
        battery_capacity = df.set_index("ID_Battery")["capacity"].to_dict()
        for household in self.households:
            household_battery_size = battery_capacity[household.id_battery]
            self.community_battery_size += (household_battery_size - household.BatSoC_hour)

    def plot_community_grid(self):
        winter_hours = (25, 192)
        # winter_hours = (49, 217)
        summer_hours = (4153, 4321)
        hour_ranges = [winter_hours, summer_hours]
        for hour_range in hour_ranges:
            h1 = hour_range[0]
            h2 = hour_range[1]
            values_dict = {
                "GridConsumption": self.community_grid_consumption[h1:h2] / 1000,
                "PVConsumption": self.community_pv_consumption[h1:h2] / 1000,
                "GridFeed": - self.community_grid_feed[h1:h2] / 1000
            }
            self.plotter.bar_figure(
                values_dict=values_dict,
                fig_name=f"EnergyCommunityElectricityBalance_H{h1}To{h2}",
                x_label="Hour",
                y_label="Electricity Consumption (+) and Feed-in (-) (kWh)",
            )

