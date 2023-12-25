import os
from typing import TYPE_CHECKING, List, Dict

import pandas as pd
import sqlalchemy

from utils.tables import InputTables

if TYPE_CHECKING:
    from utils.config import Config


class DB:

    def __init__(self, path):
        self.connection = sqlalchemy.create_engine(f'sqlite:///{path}')

    def if_exists(self, table_name: str) -> bool:
        return table_name in self.get_table_names()

    def get_engine(self):
        return self.connection

    def close(self):
        self.connection.dispose()

    def get_table_names(self):
        return sqlalchemy.inspect(self.connection).get_table_names()

    def clear_database(self):
        for table_name in self.get_table_names():
            with self.connection.connect() as conn:
                result = conn.execute(sqlalchemy.text(f"drop table {table_name}"))

    def drop_table(self, table_name: str):
        with self.connection.connect() as conn:
            result = conn.execute(sqlalchemy.text(f"drop table if exists {table_name}"))

    def write_dataframe(
            self,
            table_name: str,
            data_frame: pd.DataFrame,
            data_types: dict = None,
            if_exists="append",
    ):  # if_exists: {'replace', 'fail', 'append'}
        data_frame.to_sql(
            table_name,
            self.connection,
            index=False,
            dtype=data_types,
            if_exists=if_exists,
            chunksize=10_000,
        )

    def read_dataframe(self, table_name: str, filter: dict = None, column_names: List[str] = None) -> pd.DataFrame:
        """column_names will only extract certain columns (list)
        filter have to be dict with: column_name: value. The table where the column has that value is returned

        Returns:
            object: pandas Dataframe"""
        if filter is None:
            filter = {}
        if column_names is None:
            column_names = []
        if len(column_names) > 0:
            columns2extract = ""
            for name in column_names:
                columns2extract += name + ','
            columns2extract = columns2extract[:-1]  # delete last ","
        else:
            columns2extract = "*"  # select all columns
        if len(filter) > 0:
            condition_temp = ""
            for key, value in filter.items():
                condition_temp += key + " == '" + str(value) + "' and "
            condition = " where " + condition_temp
            condition = condition[0:-5]  # deleting last "and"
        else:
            condition = ''

        dataframe = pd.read_sql('select ' + columns2extract + ' from ' + table_name + condition, con=self.connection)
        return dataframe

    def delete_row_from_table(
            self,
            table_name: str,
            column_name_plus_value: dict
    ) -> None:
        condition_temp = ""
        for key, value in column_name_plus_value.items():
            condition_temp += key + " == '" + str(value) + "' and "
        condition = " where " + condition_temp
        condition = condition[0:-5]  # deleting last "and"

        query = f"DELETE FROM {table_name}" + condition
        self.connection.execute(query)

    def query(self, sql) -> pd.DataFrame:
        return pd.read_sql(sql, self.connection)


def create_db_conn(config: "Config") -> DB:
    if config.task_id is None:
        conn = DB(os.path.join(config.output, config.project_name + ".sqlite"))
    else:
        conn = DB(os.path.join(config.task_output, f'{config.project_name}.sqlite'))
    return conn


def init_project_db(config: "Config"):
    db = create_db_conn(config)
    db.clear_database()

    def file_exists(table_name: str):
        df = None
        extensions = {".xlsx": pd.read_excel,
                      ".csv": pd.read_csv}
        for ext, pd_read_func in extensions.items():
            file_path = os.path.join(config.input, table_name + ext)
            if os.path.exists(file_path):
                df = pd_read_func(file_path)
                break
        return df

    for input_table in InputTables:
        df = file_exists(input_table.name)
        if df is not None:
            print(f'Loading input table --> {input_table.name}')
            db.write_dataframe(
                table_name=input_table.name,
                data_frame=df.dropna(axis=1, how="all").dropna(axis=0, how="all"),
                if_exists="replace"
            )


def fetch_input_tables(config: "Config") -> Dict[str, pd.DataFrame]:
    input_tables = {}
    db = create_db_conn(config)
    for table_name in db.get_table_names():
        input_tables[table_name] = db.read_dataframe(table_name)
    return input_tables
