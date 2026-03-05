#!/usr/bin/env python3
"""Run operation regression in parallel mode.

Workflow per mode:
1) Delete output folder.
2) Re-initialize project output workspace from input files.
3) Run operation model.
4) Compare output against output_benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import Callable

import pandas as pd
from pandas.testing import assert_frame_equal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.operation.main import run_operation_model
from models.operation.main import run_operation_model_parallel
from models.operation.input_tables import OPERATION_INPUT_TABLE_NAMES
from projects.test_operation.main import get_config
from utils.db import prepare_project_run


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _normalize_table(df: pd.DataFrame) -> pd.DataFrame:
    preferred = [c for c in ("ID_Scenario", "Hour", "Month", "DayHour") if c in df.columns]
    if preferred:
        return df.sort_values(preferred).reset_index(drop=True)
    return df


def _frames_match(actual: pd.DataFrame, benchmark: pd.DataFrame) -> bool:
    if list(actual.columns) != list(benchmark.columns):
        return False
    if actual.shape != benchmark.shape:
        return False
    actual = _normalize_table(actual)
    benchmark = _normalize_table(benchmark)
    try:
        assert_frame_equal(actual, benchmark, check_dtype=False, check_like=False, check_exact=True)
        return True
    except AssertionError:
        return False


def compare_outputs(actual_dir: Path, benchmark_dir: Path) -> list[str]:
    messages: list[str] = []

    actual_files = sorted(
        p.name for p in actual_dir.iterdir()
        if p.is_file() and p.name.startswith("OperationResult_") and (
            p.name.endswith(".parquet.gzip") or p.name.endswith(".csv")
        )
    )
    benchmark_files = sorted(
        p.name for p in benchmark_dir.iterdir()
        if p.is_file() and p.name.startswith("OperationResult_") and (
            p.name.endswith(".parquet.gzip") or p.name.endswith(".csv")
        )
    )

    missing_in_actual = sorted(set(benchmark_files) - set(actual_files))
    extra_in_actual = sorted(set(actual_files) - set(benchmark_files))
    if missing_in_actual:
        messages.append(f"missing result files in actual: {missing_in_actual}")
    if extra_in_actual:
        messages.append(f"extra result files in actual: {extra_in_actual}")

    for name in sorted(set(actual_files) & set(benchmark_files)):
        a = actual_dir / name
        b = benchmark_dir / name
        if name.endswith(".parquet.gzip"):
            dfa = pd.read_parquet(a)
            dfb = pd.read_parquet(b)
            if not _frames_match(dfa, dfb):
                messages.append(f"parquet hash mismatch: {name}")
        elif name.endswith(".csv"):
            dfa = pd.read_csv(a)
            dfb = pd.read_csv(b)
            if not _frames_match(dfa, dfb):
                messages.append(f"csv value mismatch: {name}")
    return messages


def run_mode(
    mode_name: str,
    cfg,
    runner: Callable[[], None],
) -> int:
    output_dir = Path(cfg.output)
    benchmark_dir = Path(cfg.project_path) / "output_benchmark"

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prepare_project_run(cfg, table_names=OPERATION_INPUT_TABLE_NAMES)
    runner()

    messages = compare_outputs(output_dir, benchmark_dir)
    if messages:
        print(f"[{mode_name}] FAIL")
        for m in messages:
            print(f"- {m}")
        return 1
    print(f"[{mode_name}] PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run operation regression (parallel only).")
    parser.add_argument("--parallel-tasks", type=int, default=2, help="Task count for parallel mode.")
    args = parser.parse_args()

    cfg = get_config("test_operation")
    return run_mode(
        "parallel",
        cfg,
        lambda: run_operation_model_parallel(
            config=cfg,
            task_num=args.parallel_tasks,
            run_ref=True,
            run_opt=True,
            save_year=True,
            save_month=True,
            save_hour=True,
            reset_task_workspaces=True,
        ),
    )


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", "0")
    os.environ.setdefault("FLEX_OPERATION_SOLVER_OPTIONS", "Threads=1,Seed=0")
    raise SystemExit(main())
