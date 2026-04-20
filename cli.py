"""
Data Profiler - command-line interface.

Usage:
    python cli.py data.csv --target churn
    python cli.py data.csv --target price --task regression --output report.xlsx
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from profiler import profile


def load_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    if suffix == ".parquet":
        return pd.read_parquet(path)
    raise ValueError(f"Unsupported file type: {suffix}")


def save_report(result, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([result.overview]).to_excel(writer, sheet_name="overview", index=False)
        if not result.numeric_stats.empty:
            result.numeric_stats.to_excel(writer, sheet_name="numeric_stats", index=False)
        if not result.categorical_stats.empty:
            result.categorical_stats.to_excel(writer, sheet_name="categorical_stats", index=False)
        result.missing_summary.to_excel(writer, sheet_name="missing", index=False)
        if not result.feature_importance.empty:
            result.feature_importance.to_excel(writer, sheet_name="feature_importance", index=False)
        tcn = result.target_conditioned.get("numeric")
        if isinstance(tcn, pd.DataFrame) and not tcn.empty:
            tcn.to_excel(writer, sheet_name="target_cond_numeric")
        tcc = result.target_conditioned.get("categorical")
        if isinstance(tcc, pd.DataFrame) and not tcc.empty:
            tcc.to_excel(writer, sheet_name="target_cond_categorical", index=False)
        if result.correlations is not None:
            result.correlations.to_excel(writer, sheet_name="correlations")


def main() -> int:
    ap = argparse.ArgumentParser(description="Profile a dataset against a target column.")
    ap.add_argument("file", type=Path, help="Input file (csv, xlsx, parquet).")
    ap.add_argument("--target", required=True, help="Name of the target column.")
    ap.add_argument(
        "--task",
        choices=["classification", "regression"],
        default=None,
        help="Override auto-inferred task type.",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=Path("profile_report.xlsx"),
        help="Output Excel report path.",
    )
    args = ap.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        return 1

    df = load_file(args.file)
    result = profile(df, target=args.target, task=args.task)

    # Console summary
    ov = result.overview
    print(f"Rows: {ov['rows']:,} | Columns: {ov['columns']} | Missing: {ov['missing_pct']}%")
    print(f"Target: {args.target} | Task: {result.target_info['task']}")
    print("\nTop 10 features by mutual information:")
    if not result.feature_importance.empty:
        print(result.feature_importance.head(10).to_string(index=False))

    save_report(result, args.output)
    print(f"\n✅ Report written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
