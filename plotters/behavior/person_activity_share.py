import os.path

from utils.db import create_db_conn
from utils.config import Config
from utils.tables import InputTables, OutputTables
import numpy as np
from typing import List, Optional
import matplotlib.pyplot as plt
import seaborn as sns


def plot_activity_share_comparison(tus_matrix: np.ndarray, sim_matrix: np.ndarray, labels: dict, fig_path: str):

    def count_activity_percentages(activity_matrix):
        row_num = np.shape(activity_matrix)[0]
        activity_percentages = []
        for id_activity, activity_name in labels.items():
            activity_percentages.append(np.count_nonzero(activity_matrix == id_activity, axis=0)/row_num)
        return activity_percentages

    fig = plt.figure(figsize=(25, 10), dpi=200, frameon=False)
    ax1 = fig.add_axes((0.05, 0.07, 0.43, 0.7))
    ax2 = fig.add_axes((0.52, 0.07, 0.43, 0.7))
    tick_fontsize = 15
    label_fontsize = 20

    timeslots = [timeslot for timeslot in range(0, 144)]
    ax1.stackplot(
        timeslots,
        count_activity_percentages(tus_matrix),
        labels=labels.values(),
        colors=sns.color_palette("Spectral", len(labels)).as_hex())
    ax1.set_xlabel('timeslots', fontsize=label_fontsize)
    ax1.set_ylabel('activity percentage', fontsize=label_fontsize)

    ax2.stackplot(
        timeslots,
        count_activity_percentages(sim_matrix),
        labels=labels.values(),
        colors=sns.color_palette("Spectral", len(labels)).as_hex()
    )
    ax2.set_xlabel('timeslots', fontsize=label_fontsize)

    # Add a shared legend
    handles, labels = ax1.get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        fontsize=15,
        bbox_to_anchor=(0.05, 1, 0.9, -0.02),
        loc="upper left",
        ncol=3,
        borderaxespad=0,
        mode="expand",
        frameon=True,
    )

    for ax in [ax1, ax2]:
        for tick in ax.xaxis.get_major_ticks():
            tick.label1.set_fontsize(tick_fontsize)
        for tick in ax.yaxis.get_major_ticks():
            tick.label1.set_fontsize(tick_fontsize)

    plt.savefig(fig_path)


def person_activity_share(config: "Config", person_types: List[int], day_types: List[int]):
    db = create_db_conn(config)
    df_activities = db.read_dataframe(InputTables.BehaviorID_Activity.name)
    df_tus = db.read_dataframe(InputTables.BehaviorParam_Activity_TUSProfile.name)
    df_sim = db.read_dataframe(OutputTables.BehaviorResult_PersonProfiles.name)

    def get_activities():
        activities = {}
        for index, row in df_activities.iterrows():
            activities[row["id_activity"]] = row["name"]
        return activities

    def get_tus_matrix(id_person_type: Optional[int] = None, id_day_type: Optional[int] = None):
        if id_person_type is not None and id_day_type is not None:
            df = df_tus.loc[(df_tus["id_person_type"] == id_person_type) &
                            (df_tus["id_day_type"] == id_day_type)]
        else:
            df = df_tus
        return df.loc[:, "t1":"t144"].to_numpy()

    def get_sim_matrix(id_person_type: Optional[int] = None, id_day_type: Optional[int] = None):
        if id_person_type is not None and id_day_type is not None:
            df = df_sim[["hour", "week_day", "id_day_type", "day_hour", "hour_slot"] +
                        [col for col in df_sim.columns if col.startswith(f"activity_p{id_person_type}")]]
            df = df.loc[df["id_day_type"] == id_day_type].reset_index(drop=True)
        else:
            df = df_sim[["hour", "week_day", "id_day_type", "day_hour", "hour_slot"] +
                        [col for col in df_sim.columns if col.startswith(f"activity_p")]]
        day_num, remaining = divmod(len(df), 144)
        assert remaining == 0
        df.drop(columns=["hour", "week_day", "id_day_type", "day_hour", "hour_slot"], inplace=True)
        profile_matrix_list = []
        for day in range(0, day_num):
            profile_matrix_list.append(df.iloc[144 * day:144 * (day + 1)].to_numpy().transpose())
        return np.vstack(profile_matrix_list)

    for id_person_type in person_types:
        for id_day_type in day_types:
            plot_activity_share_comparison(
                tus_matrix=get_tus_matrix(id_person_type, id_day_type),
                sim_matrix=get_sim_matrix(id_person_type, id_day_type),
                labels=get_activities(),
                fig_path=os.path.join(config.figure, f"activity_share_p{id_person_type}d{id_day_type}")
            )

    plot_activity_share_comparison(
        tus_matrix=get_tus_matrix(),
        sim_matrix=get_sim_matrix(),
        labels=get_activities(),
        fig_path=os.path.join(config.figure, f"activity_share")
    )



