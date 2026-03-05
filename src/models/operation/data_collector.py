import os.path
from typing import TYPE_CHECKING, Union, Optional, List
from abc import ABC, abstractmethod
import pyomo.environ as pyo
import pandas as pd
import numpy as np
import logging

from src.models.operation.result_registry import ResultVarSpec
from src.models.operation.result_registry import iter_operation_result_specs
from src.models.operation.time_defs import HOURS_PER_YEAR as OP_HOURS_PER_YEAR
from src.models.operation.time_defs import MONTH_HOUR_RANGES
from src.utils.tables import OutputTables
from src.utils.file_store import write_table

if TYPE_CHECKING:
    from src.utils.config import Config
    from src.models.operation.physics_model import OperationModel


class OperationDataCollector(ABC):
    HOURS_PER_YEAR = OP_HOURS_PER_YEAR

    def __init__(
        self,
        model: Union["OperationModel", "pyo.ConcreteModel"],
        scenario_id: int,
        config: "Config",
        save_year: Optional[bool] = True,
        save_month: Optional[bool] = False,
        save_hour: Optional[bool] = False,
        hour_vars: Optional[List[str]] = None,
        hour_file_format: str = "parquet",
        aggregate_file_format: str = "csv",
    ):
        """
        :param model: either the ref model or the opt model
        :param scenario_id: id of the scenario that is being saved
        :param config: configuration
        :param save_hour: if True hourly results are saved (default = True)
        :param save_month: if True monthly results are saved (default = False)
        :param save_year: if True yearly results are saved (default = True)
        :param hour_vars: if a list of variables is provided only these variables are being saved as hourly
                results. save_hourly_results has to be True. This is to save disc space if only eg. the Load is needed.
        """
        self.model = model
        self.scenario_id = scenario_id
        self.config = config
        self.hour_result = {}
        self.month_result = {}
        self.year_result = {}
        self.save_hour = save_hour
        self.save_month = save_month
        self.save_year = save_year
        self.logger = logging.getLogger(f"{config.project_name}")
        self.hour_vars = hour_vars
        self.output_folder = self.set_output_folder(config)
        self.hour_file_format = hour_file_format
        del aggregate_file_format
        # Month/Year outputs are always CSV; only hourly output is format-configurable.
        self.aggregate_file_format = "csv"

    @staticmethod
    def set_output_folder(config: "Config"):
        if config.task_output is not None:
            folder = config.task_output
        else:
            folder = config.output
        return folder

    @abstractmethod
    def get_var_values(self, variable_name: str) -> np.array:
        ...

    @abstractmethod
    def get_total_cost(self) -> float:
        ...

    @abstractmethod
    def get_hour_result_table_name(self) -> str:
        ...

    @abstractmethod
    def get_month_result_table_name(self) -> str:
        ...

    @abstractmethod
    def get_year_result_table_name(self) -> str:
        ...

    def convert_hour_to_month(self, values: np.array):
        month_results = []
        for month, hour_range in MONTH_HOUR_RANGES.items():
            month_slice = values[hour_range[0] - 1:hour_range[1]]
            month_results.append(month_slice)
        return month_results

    def _aggregate(self, values: np.array, agg: str):
        if agg == "sum":
            return float(values.sum())
        if agg == "mean":
            return float(values.mean())
        if agg == "min":
            return float(values.min())
        if agg == "max":
            return float(values.max())
        if agg == "last":
            return float(values[-1])
        if agg == "none":
            return None
        raise ValueError(f"Unsupported aggregation '{agg}'")

    def _collect_one_variable(self, spec: "ResultVarSpec") -> None:
        variable_name = spec.name
        var_values = self.get_var_values(variable_name)
        if len(var_values) != self.HOURS_PER_YEAR:
            raise ValueError(
                f"Unexpected length for result variable '{variable_name}': "
                f"{len(var_values)} != {self.HOURS_PER_YEAR}"
            )
        self.hour_result[variable_name] = var_values
        if spec.save_month and spec.agg_month != "none":
            month_slices = self.convert_hour_to_month(var_values)
            self.month_result[variable_name] = [self._aggregate(values=s, agg=spec.agg_month) for s in month_slices]
        if spec.save_year and spec.agg_year != "none":
            self.year_result[variable_name] = self._aggregate(values=var_values, agg=spec.agg_year)

    def collect_result(self):
        for spec in iter_operation_result_specs():
            # check if the load in the reference model has outliers which would indicate a problem:
            # if spec.name == "Load" and self.get_hour_result_table_name() == OutputTables.OperationResult_RefHour.name:
            #     self.check_hourly_results_for_outliers(self.hour_result["Load"], "Load")
            self._collect_one_variable(spec)

    def check_hourly_results_for_outliers(self, profile: np.array, var_name: str):
        """
        check the result for extreme outliers which indicates that something went wrong in the calculation
        using the IQR method
        """
        from matplotlib import pyplot as plt

        Q1 = np.percentile(profile, 25)
        Q3 = np.percentile(profile, 75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 5 * IQR
        upper_bound = Q3 + 5 * IQR
        outlier_indices = np.where((profile < lower_bound) | (profile > upper_bound))[0]
        if len(outlier_indices) > 0:
            print(f"Outlier detected in {var_name} for scenario {self.scenario_id} "
                  f"in table {self.get_hour_result_table_name()}")
            self.logger.warning(f"Outlier detected in profile: {var_name} for scenario {self.scenario_id} "
                                f"in table {self.get_hour_result_table_name()}")
            plt.plot(np.arange(self.HOURS_PER_YEAR), profile)
            ax = plt.gca()
            plt.vlines(x=outlier_indices,
                       ymin=ax.get_ylim()[0], ymax=ax.get_ylim()[1],
                       colors="red", linestyles="dotted")
            plt.title(f"{var_name} in scenario {self.scenario_id}, \n "
                      f"table: {self.get_hour_result_table_name()}")
            plt.savefig(os.path.join(self.config.figure,
                                     f'Outlier_{self.get_hour_result_table_name()}_S{self.scenario_id}.png'))

    def reduce_df_size(self, frame: pd.DataFrame) -> pd.DataFrame:
        """
        reduce the size of a pd Dataframe by down casting the integer type (automatically) and float type (to float32).
        :param frame: df that should be saved
        :return: DataFrame with reduced size
        """
        float_cols = frame.select_dtypes(include=["float64", "float32"]).columns
        if len(float_cols) > 0:
            frame[float_cols] = frame[float_cols].astype("float32")
        int_cols = frame.select_dtypes(include=["int64", "int32"]).columns
        if len(int_cols) > 0:
            frame[int_cols] = frame[int_cols].apply(pd.to_numeric, downcast="integer")
        return frame

    def save_hour_result(self):
        result_hour_df = pd.DataFrame(self.hour_result)
        result_hour_df.insert(loc=0, column="ID_Scenario", value=self.scenario_id)
        result_hour_df.insert(loc=1, column="Hour", value=list(range(1, self.HOURS_PER_YEAR + 1)))
        result_hour_df.insert(loc=2, column="DayHour", value=np.tile(np.arange(1, 25), self.HOURS_PER_YEAR // 24))
        if self.hour_vars:
            base_columns = ["ID_Scenario", "Hour", "DayHour"]
            requested_columns = [
                col for col in self.hour_vars
                if col in result_hour_df.columns and col not in base_columns
            ]
            result_hour_df = result_hour_df.loc[:, base_columns + requested_columns]
        df_to_save = self.reduce_df_size(result_hour_df)
        write_table(
            data_frame=df_to_save,
            file_name=self.get_hour_result_table_name() + f"_S{self.scenario_id}",
            folder=self.output_folder,
            file_format=self.hour_file_format,
        )

    def save_month_result(self):
        result_month_df = pd.DataFrame(self.month_result)
        result_month_df.insert(loc=0, column="ID_Scenario", value=self.scenario_id)
        result_month_df.insert(loc=1, column="Month", value=list(range(1, 13)))
        df_to_save = self.reduce_df_size(result_month_df)
        write_table(
            data_frame=df_to_save,
            file_name=self.get_month_result_table_name() + f"_S{self.scenario_id}",
            folder=self.output_folder,
            file_format=self.aggregate_file_format,
        )

    def save_year_result(self):
        result_year_df = pd.DataFrame(self.year_result, index=[0])
        result_year_df.insert(loc=0, column="ID_Scenario", value=self.scenario_id)
        result_year_df.insert(loc=1, column="TotalCost", value=self.get_total_cost())
        df_to_save = self.reduce_df_size(result_year_df)

        write_table(
            data_frame=df_to_save,
            file_name=self.get_year_result_table_name() + f"_S{self.scenario_id}",
            folder=self.output_folder,
            file_format=self.aggregate_file_format,
        )

    def run(self):
        self.collect_result()
        if self.save_hour:
            self.save_hour_result()
        if self.save_month:
            self.save_month_result()
        if self.save_year:
            self.save_year_result()


class OptDataCollector(OperationDataCollector):
    def get_var_values(self, variable_name: str) -> np.array:
        var_values = np.array(
            list(getattr(self.model, variable_name).extract_values().values())
        )
        return var_values

    def get_total_cost(self) -> float:
        total_cost = self.model.total_operation_cost_rule()
        return total_cost

    def get_hour_result_table_name(self) -> str:
        return OutputTables.OperationResult_OptHour.name

    def get_month_result_table_name(self) -> str:
        return OutputTables.OperationResult_OptMonth.name

    def get_year_result_table_name(self) -> str:
        return OutputTables.OperationResult_OptYear.name


class RefDataCollector(OperationDataCollector):
    def get_var_values(self, variable_name: str) -> np.array:
        var_values = np.array(getattr(self.model, variable_name))
        return var_values

    def get_total_cost(self) -> float:
        total_cost = getattr(self.model, "TotalCost").sum()
        return total_cost

    def get_hour_result_table_name(self) -> str:
        return OutputTables.OperationResult_RefHour.name

    def get_month_result_table_name(self) -> str:
        return OutputTables.OperationResult_RefMonth.name

    def get_year_result_table_name(self) -> str:
        return OutputTables.OperationResult_RefYear.name
