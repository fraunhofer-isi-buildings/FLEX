#!/usr/bin/env python3
"""Compare operation model outputs against a benchmark folder.

Default mode is strict: same files, same table names, same columns/dtypes, and
element-wise exact equality for numeric and non-numeric values.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


def _list_files(folder: Path) -> list[Path]:
    return sorted([p for p in folder.iterdir() if p.is_file()])


def _assert_same_file_set(actual: Path, benchmark: Path) -> list[str]:
    messages: list[str] = []
    actual_files = {p.name for p in _list_files(actual)}
    benchmark_files = {p.name for p in _list_files(benchmark)}
    missing_in_actual = sorted(benchmark_files - actual_files)
    extra_in_actual = sorted(actual_files - benchmark_files)
    if missing_in_actual:
        messages.append(f"actual missing files: {missing_in_actual}")
    if extra_in_actual:
        messages.append(f"actual has extra files: {extra_in_actual}")
    return messages


def _compare_schema(a: pd.DataFrame, b: pd.DataFrame, context: str) -> list[str]:
    messages: list[str] = []
    if list(a.columns) != list(b.columns):
        messages.append(
            f"{context}: column order/content mismatch\n"
            f"actual={list(a.columns)}\nbenchmark={list(b.columns)}"
        )
        return messages
    dtype_a = [str(x) for x in a.dtypes]
    dtype_b = [str(x) for x in b.dtypes]
    if dtype_a != dtype_b:
        messages.append(
            f"{context}: dtype mismatch\nactual={dtype_a}\nbenchmark={dtype_b}"
        )
    if len(a) != len(b):
        messages.append(f"{context}: row count mismatch actual={len(a)} benchmark={len(b)}")
    return messages


def _iter_mismatch_indices(mask: np.ndarray, max_report: int = 5) -> Iterable[int]:
    idx = np.flatnonzero(mask)
    return idx[:max_report]


def _compare_frame_values(
    a: pd.DataFrame,
    b: pd.DataFrame,
    context: str,
    strict: bool,
    atol: float,
    rtol: float,
) -> list[str]:
    messages: list[str] = []
    if len(a) != len(b) or list(a.columns) != list(b.columns):
        return messages

    for col in a.columns:
        s1 = a[col]
        s2 = b[col]
        if pd.api.types.is_numeric_dtype(s1) and pd.api.types.is_numeric_dtype(s2):
            arr1 = s1.to_numpy()
            arr2 = s2.to_numpy()
            if strict:
                equal = arr1 == arr2
            else:
                equal = np.isclose(arr1, arr2, atol=atol, rtol=rtol, equal_nan=True)
            if not bool(np.all(equal)):
                bad = list(_iter_mismatch_indices(~equal))
                preview = [(int(i), arr1[i], arr2[i]) for i in bad]
                messages.append(
                    f"{context}:{col} numeric mismatch count={int((~equal).sum())}, "
                    f"first={preview}"
                )
        else:
            # Handle object/string columns
            arr1 = s1.astype("string").fillna("<NA>").to_numpy()
            arr2 = s2.astype("string").fillna("<NA>").to_numpy()
            equal = arr1 == arr2
            if not bool(np.all(equal)):
                bad = list(_iter_mismatch_indices(~equal))
                preview = [(int(i), arr1[i], arr2[i]) for i in bad]
                messages.append(
                    f"{context}:{col} value mismatch count={int((~equal).sum())}, "
                    f"first={preview}"
                )
    return messages


def _compare_parquet_file(
    actual_file: Path,
    benchmark_file: Path,
    strict: bool,
    atol: float,
    rtol: float,
) -> list[str]:
    context = f"parquet:{actual_file.name}"
    a = pd.read_parquet(actual_file)
    b = pd.read_parquet(benchmark_file)
    messages = _compare_schema(a, b, context)
    messages.extend(_compare_frame_values(a, b, context, strict, atol, rtol))
    return messages


def _sqlite_tables(db_path: Path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows]


def _read_sql_table(db_path: Path, table: str) -> pd.DataFrame:
    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(f"SELECT * FROM {table}", conn)


def _compare_sqlite_file(
    actual_file: Path,
    benchmark_file: Path,
    strict: bool,
    atol: float,
    rtol: float,
) -> list[str]:
    messages: list[str] = []
    context = f"sqlite:{actual_file.name}"
    t1 = _sqlite_tables(actual_file)
    t2 = _sqlite_tables(benchmark_file)
    if t1 != t2:
        messages.append(f"{context}: table mismatch actual={t1}, benchmark={t2}")
        return messages

    for table in t1:
        a = _read_sql_table(actual_file, table)
        b = _read_sql_table(benchmark_file, table)
        tctx = f"{context}:{table}"
        messages.extend(_compare_schema(a, b, tctx))
        messages.extend(_compare_frame_values(a, b, tctx, strict, atol, rtol))
    return messages


def compare_outputs(
    actual: Path,
    benchmark: Path,
    strict: bool = True,
    atol: float = 0.0,
    rtol: float = 0.0,
) -> list[str]:
    messages = _assert_same_file_set(actual, benchmark)
    if messages:
        return messages

    for file in sorted(p.name for p in _list_files(benchmark)):
        af = actual / file
        bf = benchmark / file
        if file.endswith(".parquet.gzip"):
            messages.extend(_compare_parquet_file(af, bf, strict, atol, rtol))
        elif file.endswith(".sqlite"):
            messages.extend(_compare_sqlite_file(af, bf, strict, atol, rtol))
        else:
            messages.append(f"unsupported file type: {file}")
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare operation outputs to benchmark")
    parser.add_argument("--actual", type=Path, required=True, help="Actual output folder")
    parser.add_argument("--benchmark", type=Path, required=True, help="Benchmark output folder")
    parser.add_argument(
        "--mode",
        choices=["strict", "tolerant"],
        default="strict",
        help="strict: exact numeric equality, tolerant: use np.isclose",
    )
    parser.add_argument("--atol", type=float, default=1e-9, help="abs tolerance for tolerant mode")
    parser.add_argument("--rtol", type=float, default=1e-9, help="rel tolerance for tolerant mode")
    args = parser.parse_args()

    strict = args.mode == "strict"
    if not args.actual.exists():
        print(f"FAIL: actual folder not found: {args.actual}")
        return 2
    if not args.benchmark.exists():
        print(f"FAIL: benchmark folder not found: {args.benchmark}")
        return 2

    messages = compare_outputs(
        actual=args.actual,
        benchmark=args.benchmark,
        strict=strict,
        atol=args.atol,
        rtol=args.rtol,
    )
    if messages:
        print("FAIL")
        for m in messages:
            print(f"- {m}")
        return 1

    print("PASS: outputs are identical under selected comparison mode")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
