import os
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

import pandas as pd

from src.utils.tables import InputTables

if TYPE_CHECKING:
    from src.utils.config import Config


def _read_table_file(path: Path) -> pd.DataFrame:
    suffix = "".join(path.suffixes)
    if suffix.endswith(".parquet.gzip") or path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".xlsx":
        return pd.read_excel(path)
    raise ValueError(f"Unsupported table file: {path}")


def _write_table_file(path: Path, data_frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".csv":
        data_frame.to_csv(path, index=False)
        return
    if "".join(path.suffixes).endswith(".parquet.gzip") or path.suffix == ".parquet":
        data_frame.to_parquet(path, index=False, compression="gzip")
        return
    raise ValueError(f"Unsupported write target: {path}")


class DB:
    def __init__(self, output_folder: str, input_folder: Optional[str] = None):
        self.output_folder = Path(output_folder)
        self.input_folder = Path(input_folder) if input_folder is not None else None
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def _candidate_paths(self, table_name: str, include_input: bool = True) -> List[Path]:
        candidates = [
            self.output_folder / f"{table_name}.csv",
            self.output_folder / f"{table_name}.parquet.gzip",
            self.output_folder / f"{table_name}.parquet",
        ]
        if include_input and self.input_folder is not None:
            candidates.extend(
                [
                    self.input_folder / f"{table_name}.csv",
                    self.input_folder / f"{table_name}.xlsx",
                    self.input_folder / f"{table_name}.parquet.gzip",
                    self.input_folder / f"{table_name}.parquet",
                ]
            )
        return candidates

    def _find_existing_path(self, table_name: str, include_input: bool = True) -> Optional[Path]:
        for path in self._candidate_paths(table_name, include_input=include_input):
            if path.exists():
                return path
        return None

    def if_exists(self, table_name: str) -> bool:
        return self._find_existing_path(table_name) is not None

    def close(self):
        return

    def get_table_names(self):
        names = set()
        for folder in [self.output_folder, self.input_folder]:
            if folder is None or not folder.exists():
                continue
            for path in folder.iterdir():
                if path.is_file():
                    suffix = "".join(path.suffixes)
                    if suffix in {".csv", ".xlsx", ".parquet.gzip"} or path.suffix == ".parquet":
                        names.add(path.name.split(".")[0])
        return sorted(names)

    def clear_database(self):
        patterns = [
            "BehaviorResult_*.csv",
            "CommunityResult_*.csv",
            "CommunityResult_*.parquet",
            "CommunityResult_*.parquet.gzip",
            "OperationResult_*.csv",
            "OperationResult_*.parquet",
            "OperationResult_*.parquet.gzip",
            "*.db",
        ]
        for pattern in patterns:
            for path in self.output_folder.glob(pattern):
                if path.is_file():
                    path.unlink()

    def drop_table(self, table_name: str):
        for path in self._candidate_paths(table_name, include_input=False):
            if path.exists():
                path.unlink()

    def write_dataframe(
        self,
        table_name: str,
        data_frame: pd.DataFrame,
        data_types: dict = None,
        if_exists="append",
    ):
        del data_types
        target = self.output_folder / f"{table_name}.csv"
        if if_exists == "replace" or not target.exists():
            _write_table_file(target, data_frame)
            return
        if if_exists == "append":
            old_df = _read_table_file(target)
            _write_table_file(target, pd.concat([old_df, data_frame], ignore_index=True))
            return
        if if_exists == "fail":
            if target.exists():
                raise ValueError(f"Table already exists: {table_name}")
            _write_table_file(target, data_frame)
            return
        raise ValueError(f"Unsupported if_exists mode: {if_exists}")

    def read_dataframe(self, table_name: str, filter: dict = None, column_names: List[str] = None) -> pd.DataFrame:
        path = self._find_existing_path(table_name)
        if path is None:
            raise FileNotFoundError(f"Table not found as file: {table_name}")
        df = _read_table_file(path)
        if column_names:
            df = df.loc[:, column_names]
        if filter:
            for key, value in filter.items():
                df = df.loc[df[key] == value]
        return df.reset_index(drop=True)

    def delete_row_from_table(
        self,
        table_name: str,
        column_name_plus_value: dict
    ) -> None:
        df = self.read_dataframe(table_name)
        mask = pd.Series([True] * len(df))
        for key, value in column_name_plus_value.items():
            mask &= df[key] == value
        df = df.loc[~mask].reset_index(drop=True)
        self.write_dataframe(table_name=table_name, data_frame=df, if_exists="replace")

    def query(self, sql) -> pd.DataFrame:
        raise NotImplementedError("File-backed DB does not support SQL query().")


def create_db_conn(config: "Config") -> DB:
    output_folder = config.task_output if config.task_id is not None else config.output
    return DB(output_folder=output_folder, input_folder=config.input)


def prepare_project_run(
    config: "Config",
    clean_start: bool = True,
    log_input_tables: bool = True,
    table_names: Optional[Iterable[str]] = None,
):
    db = create_db_conn(config)
    if clean_start:
        db.clear_database()

    def file_exists(table_name: str):
        df = None
        extensions = {
            ".xlsx": pd.read_excel,
            ".csv": pd.read_csv,
            ".parquet.gzip": pd.read_parquet,
            ".parquet": pd.read_parquet,
        }
        for ext, pd_read_func in extensions.items():
            file_path = os.path.join(config.input, table_name + ext)
            if os.path.exists(file_path):
                df = pd_read_func(file_path)
                break
        return df

    names = list(table_names) if table_names is not None else [input_table.name for input_table in InputTables]
    if log_input_tables:
        for table_name in names:
            df = file_exists(table_name)
            if df is not None:
                print(f'Loading input table --> {table_name}')



def fetch_input_tables(config: "Config", table_names: Optional[Iterable[str]] = None) -> Dict[str, pd.DataFrame]:
    input_tables = {}
    names = list(table_names) if table_names is not None else [input_table.name for input_table in InputTables]
    for table_name in names:
        csv_path = Path(config.input) / f"{table_name}.csv"
        xlsx_path = Path(config.input) / f"{table_name}.xlsx"
        parquet_path = Path(config.input) / f"{table_name}.parquet.gzip"
        if csv_path.exists():
            input_tables[table_name] = pd.read_csv(csv_path)
        elif xlsx_path.exists():
            input_tables[table_name] = pd.read_excel(xlsx_path)
        elif parquet_path.exists():
            input_tables[table_name] = pd.read_parquet(parquet_path)
    return input_tables
