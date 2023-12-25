import os

import pandas as pd

from utils.tables import InputTables


def calc_starting_activity():
    output_folder = os.path.join(os.path.abspath(os.path.dirname(__file__)), '../output')
    df = pd.read_excel(os.path.join(output_folder, f"{InputTables.BehaviorParam_Activity_TUSProfile.name}.xlsx"))
    starting_activity = {}
    for id_person_type in range(1, 5):
        for id_day_type in range(1, 3):
            d = {}
            for id_activity in range(1, 18):
                d[id_activity] = 0
            activity_ids = df.loc[
                (df["id_person_type"] == id_person_type) &
                (df["id_day_type"] == id_day_type)
            ]["t1"].to_list()
            total_activity = len(activity_ids)
            for id_activity in activity_ids:
                d[id_activity] = d[id_activity] + 1/total_activity
            starting_activity[(id_person_type, id_day_type)] = d
    result = []
    for (id_person_type, id_day_type), d in starting_activity.items():
        for id_activity, probability in d.items():
            result.append({
                "id_person_type": id_person_type,
                "id_day_type": id_day_type,
                "id_activity": id_activity,
                "probability": probability,
            })
    pd.DataFrame(result).to_excel(
        os.path.join(output_folder, f"{InputTables.BehaviorParam_Activity_TUSStart.name}.xlsx"),
        index=False
    )
