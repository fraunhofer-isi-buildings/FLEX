import numpy as np

from utils.config import Config
from utils.db import create_db_conn
from utils.plotter import Plotter
from utils.tables import OutputTables


def p2p_trading_amount(config: "Config", id_scenario: int):
    db = create_db_conn(config)
    result_hour = db.read_dataframe(
        OutputTables.CommunityResult_AggregatorHour.name,
        filter={"ID_Scenario": id_scenario}
    )
    p2p_trading = result_hour["p2p_trading"].to_numpy()
    trading_amount = []
    for month in range(0, 12):
        start_hour = month * 730
        end_hour = month * 730 + 730
        trading_amount.append(np.sum(p2p_trading[start_hour:end_hour]) / 1000)
    values_dict = {"P2P_trading": np.array(trading_amount)}
    Plotter(config).bar_figure(
        values_dict=values_dict,
        fig_name=f"P2P_TradingAmount",
        x_label="Month of the Year",
        y_label="P2P Trading Amount (kWh)",
        add_legend=False,
        y_lim=(0, 16000),
    )

