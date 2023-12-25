from typing import List, Union, Dict, Any
import random
from pathlib import Path
import logging
import sqlalchemy
import numpy as np
import pandas as pd
from functools import wraps
import time


def get_logger(name, level=logging.DEBUG, file_name: Union[str, "Path"] = None):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    formatter = logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    if file_name:
        file_handler = logging.FileHandler(file_name)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(logging.INFO)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger


def performance_counter(func):
    @wraps(func)
    def wrapper(*args):
        t_start = time.perf_counter()
        result = func(*args)
        t_end = time.perf_counter()
        exe_time = round(t_end - t_start, 3)
        logger = get_logger(__name__)
        logger.info(f"Timer: {func.__name__} - {exe_time}s.")
        return result

    return wrapper


def convert_datatype_py2sql(data_types: dict) -> dict:
    type_py2sql_dict: dict = {
        int: sqlalchemy.types.BigInteger,
        Union[int, None]: sqlalchemy.types.BigInteger,
        Union[List[int], None]: sqlalchemy.types.BigInteger,
        Union[np.ndarray, int, None]: sqlalchemy.types.BigInteger,
        str: sqlalchemy.types.Unicode,
        Union[str, None]: sqlalchemy.types.Unicode,
        Union[List[str], None]: sqlalchemy.types.Unicode,
        float: sqlalchemy.types.Float,
        Union[float, None]: sqlalchemy.types.Float,
        Union[List[float], None]: sqlalchemy.types.Float,
        Union[np.ndarray, None]: sqlalchemy.types.Float,
        Union[np.ndarray, float, None]: sqlalchemy.types.Float,
    }
    for key, value in data_types.items():
        data_types[key] = type_py2sql_dict[value]
    return data_types


def filter_df(df: pd.DataFrame, filter_dict: dict) -> pd.DataFrame:
    df_filtered = df.loc[(df[list(filter_dict)] == pd.Series(filter_dict)).all(axis=1)]
    return df_filtered


def filter_dataframe_dynamic(df, od_filter: "OrderedDict"):
    while len(filter_df(df, od_filter)) == 0 and len(od_filter) > 1:
        od_filter.popitem()
    filtered_df = filter_df(df, od_filter)
    return filtered_df


def filter_df2s(df: pd.DataFrame, filter_dict: dict) -> pd.Series:
    df_filtered = filter_df(df, filter_dict)
    s = df_filtered.iloc[0]
    return s


def dict_sample(options: Dict[Any, float]) -> Any:
    value_sum = 0
    for key in options.keys():
        value_sum += options[key]
    for key in options.keys():
        options[key] = options[key] / value_sum
    rand = random.uniform(0, 1)
    prob_accumulated = 0
    option_chosen_key = None
    for key in options.keys():
        prob_accumulated += options[key]
        if prob_accumulated >= rand:
            option_chosen_key = key
            break
    return option_chosen_key


def timeslot2everything(timeslot: int):
    hour, hour_slot = timeslot2hour(timeslot)
    week_day, id_day_type, day_hour = hour2weekday(hour)
    return hour, week_day, id_day_type, day_hour, hour_slot


def timeslot2hour(timeslot: int):
    hour, hour_slot = divmod(timeslot, 6)
    if hour_slot == 0:
        hour_slot = 6
    return hour + 1, hour_slot


def hour2weekday(hour: int):
    day, day_hour = divmod(hour, 24)
    if day_hour == 0:
        day_hour = 24
        day = day - 1
    week_day, id_day_type = day2weekday(day)
    return week_day, id_day_type, day_hour


def day2weekday(day: int, first_week_day: int = 2):  # The first day in 2019 is Tuesday
    week_day = (first_week_day + day) % 7
    if week_day == 0:
        week_day = 7
    if week_day in [6, 7]:
        id_day_type = 2
    else:
        id_day_type = 1
    return week_day, id_day_type


def get_time_cols_10min():
    time_cols = []
    for hour in range(1, 8761):
        week_day, id_day_type, day_hour = hour2weekday(hour)
        for slot in range(1, 7):
            time_cols.append({
                "hour": hour,
                "week_day": week_day,
                "id_day_type": id_day_type,
                "day_hour": day_hour,
                "hour_slot": slot
            })
    return pd.DataFrame(time_cols)


def get_time_cols_hour():
    time_cols = []
    for hour in range(1, 8761):
        week_day, id_day_type, day_hour = hour2weekday(hour)
        time_cols.append({
            "hour": hour,
            "week_day": week_day,
            "id_day_type": id_day_type,
            "day_hour": day_hour,
        })
    return pd.DataFrame(time_cols)

