from __future__ import annotations

import os
from typing import Dict
from typing import Optional

import pyomo.environ as pyo


def get_solver_name(default: str = "gurobi") -> str:
    """Return solver name from env override or default."""
    return os.getenv("FLEX_OPERATION_SOLVER", default).strip()


def get_solver_interface(default: str = "shell") -> str:
    """Return solver interface type ('shell' or 'persistent')."""
    return os.getenv("FLEX_OPERATION_SOLVER_INTERFACE", default).strip().lower()


def get_solver_options() -> Dict[str, object]:
    """Return solver options from env in 'key=value,key2=value2' format."""
    raw = os.getenv("FLEX_OPERATION_SOLVER_OPTIONS", "").strip()
    if not raw:
        return {}
    options: Dict[str, object] = {}
    for item in raw.split(","):
        pair = item.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(
                f"Invalid FLEX_OPERATION_SOLVER_OPTIONS item '{pair}'. "
                "Expected key=value."
            )
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        try:
            parsed: object = int(value)
        except ValueError:
            try:
                parsed = float(value)
            except ValueError:
                parsed = value
        options[key] = parsed
    return options


def solve_model(
    model,
    solver_name: Optional[str] = None,
    solver_options: Optional[Dict[str, object]] = None,
    solver_interface: Optional[str] = None,
    tee: bool = False,
):
    """Solve a Pyomo model with the configured solver."""
    resolved_solver = solver_name or get_solver_name()
    resolved_interface = solver_interface or get_solver_interface()
    persistent_backend = {
        "gurobi": "gurobi_persistent",
        "cplex": "cplex_persistent",
    }
    if resolved_interface == "persistent":
        factory_name = persistent_backend.get(resolved_solver, resolved_solver)
    else:
        factory_name = resolved_solver
    solver = pyo.SolverFactory(factory_name)
    if solver is None or not solver.available(False):
        raise RuntimeError(
            f"Requested solver '{resolved_solver}' (interface={resolved_interface}) is not available. "
            "Set FLEX_OPERATION_SOLVER to an installed solver."
        )
    for key, value in (solver_options or {}).items():
        solver.options[key] = value
    try:
        if resolved_interface == "persistent" and hasattr(solver, "set_instance"):
            solver.set_instance(model)
        return solver.solve(model, tee=tee)
    except Exception as exc:
        raise RuntimeError(
            f"Solver '{resolved_solver}' failed while solving operation model: {exc}"
        ) from exc
