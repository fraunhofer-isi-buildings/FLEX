import os
from typing import List

import pandas as pd


def if_parquet_exists(file_name: str, folder: str) -> bool:
    return os.path.exists(os.path.join(folder, f"{file_name}.parquet.gzip"))


def write_parquet(data_frame: pd.DataFrame, file_name: str, folder: str) -> None:
    data_frame.to_parquet(path=os.path.join(folder, f"{file_name}.parquet.gzip"),
                          engine="auto", compression='gzip', index=False)


def read_parquet(file_name: str, folder: str, column_names: List[str] = None) -> pd.DataFrame:
    path_to_file = os.path.join(folder, f"{file_name}.parquet.gzip")
    if column_names:
        df = pd.read_parquet(path=path_to_file, engine="auto", columns=column_names)
    else:
        df = pd.read_parquet(path=path_to_file, engine="auto")
    return df
