from utils.config import Config
from utils.db import create_db_conn
from utils.plotter import Plotter
from utils.tables import InputTables
from utils.tables import OutputTables


def aggregator_profit(config: "Config"):
    db = create_db_conn(config)
    scenarios = db.read_dataframe(InputTables.CommunityScenario.name)
    result_year = db.read_dataframe(OutputTables.CommunityResult_AggregatorYear.name)
    values_dict = {
        "P2P_Profit": result_year["p2p_profit"].to_numpy() / 10**5,
        "Opt_Profit": result_year["opt_profit"].to_numpy() / 10**5
    }
    battery_sizes = scenarios["aggregator_battery_size"].to_numpy() / 10**6
    Plotter(config).bar_figure(
        values_dict=values_dict,
        fig_name=f"AggregatorProfit-Battery",
        x_label="Battery Size (MWh)",
        y_label="Aggregator Profit (k€)",
        y_lim=(0, 200),
        x_tick_labels=battery_sizes
    )
