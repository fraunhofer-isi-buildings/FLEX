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

    def setup(self):
        self.setup_scenario_params()
        self.setup_energy_price()
        self.setup_households()
        self.setup_community_results()

    def setup_scenario_params(self):
        community_scenarios = self.db.read_dataframe(InputTables.CommunityScenario.name)
        params_dict = community_scenarios.loc[community_scenarios["ID_Scenario"] == self.scenario_id].iloc[0].to_dict()
        for key, value in params_dict.items():
            if key in self.__dict__.keys():
                self.__setattr__(key, value)

    def setup_energy_price(self):
        self.energy_prices = self.db.read_dataframe(InputTables.CommunityScenario_EnergyPrice.name)
        self.electricity_price = self.energy_prices[f"electricity_{self.id_electricity}"].to_numpy()
        self.feed_in_price = self.energy_prices[f"electricity_feed_in_{self.id_electricity_feed_in}"].to_numpy()

    def setup_households(self):
        for id_scenario in self.operation_scenario_ids:
            household = Household(id_scenario)
            household.setup_component_ids(self.operation_scenario)
            household.setup_operation_result_hour(self.ref_operation_result_hour)
            household.setup_operation_result_year(self.ref_operation_result_year)
            self.households.append(household)

    def setup_community_results(self):
        self.hours = 8760
        self.setup_community_pv_generation()
        self.setup_community_load()
        self.setup_community_grid_balance()
        self.setup_community_pv_self_consumption()
        self.setup_community_p2p_trading()
        self.setup_community_battery_size()

    def setup_community_pv_generation(self):
        self.community_pv_generation = np.zeros(self.hours, )
        for household in self.households:
            self.community_pv_generation += household.PhotovoltaicProfile_hour

    def setup_community_load(self):
        self.community_load = np.zeros(self.hours, )
        for household in self.households:
            self.community_load += household.Load_hour

    def setup_community_grid_balance(self):
        self.community_pv_consumption = np.zeros(self.hours, )
        self.community_grid_consumption = np.zeros(self.hours, )
        self.community_grid_feed = np.zeros(self.hours, )
        for h in range(0, self.hours):
            if self.community_pv_generation[h] <= self.community_load[h]:
                self.community_pv_consumption[h] = self.community_pv_generation[h]
                self.community_grid_consumption[h] = self.community_load[h] - self.community_pv_generation[h]
                self.community_grid_feed[h] = 0
            else:
                self.community_pv_consumption[h] = self.community_load[h]
                self.community_grid_consumption[h] = 0
                self.community_grid_feed[h] = self.community_pv_generation[h] - self.community_load[h]

    def setup_community_pv_self_consumption(self):
        self.community_pv_self_consumption = np.zeros(self.hours, )
        for household in self.households:
            household_pv_self_consumption = np.zeros(self.hours, )
            for h in range(0, self.hours):
                if household.PhotovoltaicProfile_hour[h] <= household.Load_hour[h]:
                    household_pv_self_consumption[h] = household.PhotovoltaicProfile_hour[h]
                else:
                    household_pv_self_consumption[h] = household.Load_hour[h]
            self.community_pv_self_consumption += household_pv_self_consumption

    def setup_community_p2p_trading(self):
        self.community_p2p_trading = self.community_pv_consumption - self.community_pv_self_consumption

    def setup_community_battery_size(self):
        self.community_battery_size = np.zeros(self.hours, )
        df = self.db.read_dataframe(InputTables.CommunityScenario_Component_Battery.name)
        for household in self.households:
            household_battery_size = df.loc[df["ID_Battery"] == household.id_battery].iloc[0]["capacity"]
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
                y_lim=(-2000, 2000)
            )


