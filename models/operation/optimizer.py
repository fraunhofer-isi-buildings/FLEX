import os

from models.operation.linopy_model import LinopyOperationModel
from models.operation.model_opt import OptOperationModel


def get_optimization_backend(default: str = "pyomo") -> str:
    return os.getenv("FLEX_OPERATION_OPT_BACKEND", default).strip().lower()


def create_optimizer(scenario):
    backend = get_optimization_backend()
    if backend == "pyomo":
        return OptOperationModel(scenario)
    if backend == "linopy":
        return LinopyOperationModel(scenario)
    raise ValueError(
        f"Unknown optimization backend '{backend}'. "
        "Supported backends: pyomo, linopy."
    )
