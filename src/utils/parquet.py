from typing import List

import pandas as pd

from src.utils.file_store import if_table_exists
from src.utils.file_store import read_table
from src.utils.file_store import write_table


def if_parquet_exists(file_name: str, folder: str) -> bool:
    return if_table_exists(file_name=file_name, folder=folder, file_format="parquet")


def write_parquet(data_frame: pd.DataFrame, file_name: str, folder: str) -> None:
    write_table(data_frame=data_frame, file_name=file_name, folder=folder, file_format="parquet")


def read_parquet(file_name: str, folder: str, column_names: List[str] = None) -> pd.DataFrame:
    return read_table(file_name=file_name, folder=folder, file_format="parquet", column_names=column_names)
