from __future__ import annotations

import os
from typing import Optional

import pyomo.environ as pyo


def get_solver_name(default: str = "gurobi") -> str:
    """Return solver name from env override or default."""
    return os.getenv("FLEX_OPERATION_SOLVER", default).strip()


def solve_model(
    model,
    solver_name: Optional[str] = None,
    tee: bool = False,
):
    """Solve a Pyomo model with the configured solver."""
    resolved_solver = solver_name or get_solver_name()
    solver = pyo.SolverFactory(resolved_solver)
    if solver is None or not solver.available(False):
        raise RuntimeError(
            f"Requested solver '{resolved_solver}' is not available. "
            "Set FLEX_OPERATION_SOLVER to an installed solver."
        )
    return solver.solve(model, tee=tee)
