import os
from pathlib import Path
from typing import Iterable
from typing import List
from typing import Optional

import pandas as pd


def _normalize_format(file_format: str) -> str:
    fmt = file_format.lower().strip()
    if fmt not in {"parquet", "csv"}:
        raise ValueError(f"Unsupported file format: {file_format}")
    return fmt


def _suffix_for_format(file_format: str) -> str:
    fmt = _normalize_format(file_format)
    return ".parquet.gzip" if fmt == "parquet" else ".csv"


def file_path(file_name: str, folder: str, file_format: str) -> Path:
    suffix = _suffix_for_format(file_format)
    return Path(folder) / f"{file_name}{suffix}"


def write_table(data_frame: pd.DataFrame, file_name: str, folder: str, file_format: str) -> None:
    path = file_path(file_name, folder, file_format)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = _normalize_format(file_format)
    if fmt == "parquet":
        data_frame.to_parquet(path=path, engine="auto", compression="gzip", index=False)
    else:
        data_frame.to_csv(path, index=False)


def read_table(file_name: str, folder: str, file_format: str, column_names: Optional[List[str]] = None) -> pd.DataFrame:
    path = file_path(file_name, folder, file_format)
    fmt = _normalize_format(file_format)
    if fmt == "parquet":
        if column_names:
            return pd.read_parquet(path=path, engine="auto", columns=column_names)
        return pd.read_parquet(path=path, engine="auto")
    if column_names:
        return pd.read_csv(path, usecols=column_names)
    return pd.read_csv(path)


def read_table_smart(
    file_name: str,
    folder: str,
    column_names: Optional[List[str]] = None,
    prefer: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    order = list(prefer) if prefer is not None else ["parquet", "csv"]
    for file_format in order:
        path = file_path(file_name, folder, file_format)
        if path.exists():
            return read_table(file_name=file_name, folder=folder, file_format=file_format, column_names=column_names)
    raise FileNotFoundError(
        f"Cannot find table '{file_name}' in {folder} as parquet/csv."
    )


def if_table_exists(file_name: str, folder: str, file_format: str) -> bool:
    return os.path.exists(file_path(file_name=file_name, folder=folder, file_format=file_format))
