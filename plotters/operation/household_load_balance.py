from typing import List, Optional

import numpy as np

from utils.config import Config
from utils.parquet import read_parquet
from utils.plotter import Plotter


def household_load_balance(config: "Config", scenario_ids: List[int], models: Optional[List[str]] = None):
    _models = ["Opt", "Ref"]
    weeks = {"Winter": (145, 312), "Summer": (4177, 4344)}
    for id_scenario in scenario_ids:
        if models is not None:
            _models = models
        for model in _models:
            file_name = f'OperationResult_{model}Hour_S{id_scenario}'
            df = read_parquet(file_name, config.output)
            for season, hour_range in weeks.items():
                df_week = df[df["Hour"].between(hour_range[0], hour_range[1])]
                values_dict = {
                    "Appliance": np.array(df_week["BaseLoadProfile"]) / 1000,
                    "HP_SpaceHeating": np.array(df_week["E_Heating_HP_out"]) / 1000,
                    "HP_HotWater": np.array(df_week["E_DHW_HP_out"]) / 1000,
                    "HE_SpaceHeating": np.array(df_week["Q_HeatingElement_heat"]) / 1000,
                    "HE_HotWater": np.array(df_week["Q_HeatingElement_DHW"]) / 1000,
                    "SpaceCooling": np.array(df_week["E_RoomCooling"]) / 1000,
                    "EVCharge": np.array(df_week["EVCharge"]) / 1000,
                    "BatteryCharge": np.array(df_week["BatCharge"]) / 1000,
                    "BatteryDischarge": np.array(-df_week["BatDischarge"]) / 1000,
                    "PVSupply": np.array(-(df_week["PV2Load"] + df_week["PV2Bat"] + df_week["PV2EV"])) / 1000,
                    "PV2Grid": np.array(-df_week["PV2Grid"]) / 1000,
                    "GridSupply": np.array(-df_week["Grid"]) / 1000,
                    # If EV can supply to the building, then two bars can be added: EV2Load & EV2Battery
                }
                Plotter(config).bar_figure(
                    values_dict=values_dict,
                    fig_name=f"HouseholdLoadBalance_{season}_S{id_scenario}_{model}",
                    x_label="Hour",
                    y_label="Electricity Demand and Supply (kW)",
                    # x_lim=None,
                    y_lim=(-50, 50),
                )
