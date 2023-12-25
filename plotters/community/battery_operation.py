import numpy as np

from utils.config import Config
from utils.db import create_db_conn
from utils.plotter import Plotter
from utils.tables import OutputTables


def battery_operation(config: "Config", id_scenario: int):
    db = create_db_conn(config)
    result_hour = db.read_dataframe(
        OutputTables.CommunityResult_AggregatorHour.name,
        filter={"ID_Scenario": id_scenario}
    )
    battery_charge = result_hour["battery_charge"].to_numpy()
    battery_discharge = result_hour["battery_discharge"].to_numpy()
    battery_charge_by_month = []
    battery_discharge_by_month = []
    for month in range(0, 12):
        start_hour = month * 730
        end_hour = month * 730 + 730
        battery_charge_by_month.append(np.sum(battery_charge[start_hour:end_hour]) / 10 ** 6)
        battery_discharge_by_month.append(np.sum(battery_discharge[start_hour:end_hour]) / 10 ** 6)
    values_dict = {
        "BatteryCharge": np.array(battery_charge_by_month),
        "BatteryDischarge": - np.array(battery_discharge_by_month)
    }
    Plotter(config).bar_figure(
        values_dict=values_dict,
        fig_name=f"BatteryOperationByMonth_S{id_scenario}",
        x_label="Month of the Year",
        y_label="Battery Charge and Discharge Amount (MWh)",
        y_lim=(-50, 50),
        x_tick_labels=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sept", "Oct", "Nov", "Dec"]
    )

