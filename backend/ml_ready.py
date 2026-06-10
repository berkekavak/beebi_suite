"""Preview summaries, ML-ready feature table, and Excel export.

All logic here is lifted verbatim (in behaviour) from the original Streamlit
``app.py`` so the new UI produces identical numbers.
"""

from __future__ import annotations

import io
from datetime import datetime

import pandas as pd

from profiler import infer_task_type


# ---------- preview: dataset health + per-column scan (was app.py preview) ----
def build_health(df: pd.DataFrame) -> dict:
    n = len(df)
    return {
        "rows": int(n),
        "columns": int(df.shape[1]),
        "duplicates": int(df.duplicated().sum()),
        "missing_cells": int(df.isna().sum().sum()),
        "memory_mb": round(df.memory_usage(deep=True).sum() / (1024 ** 2), 2),
    }


def _dtype_label(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "bool"
    if pd.api.types.is_numeric_dtype(s):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    return "categorical"


def build_column_summary(df: pd.DataFrame, target: str | None) -> list[dict]:
    """One row per column with the same flags the Streamlit preview showed."""
    n = len(df)
    rows = []
    for col in df.columns:
        s = df[col]
        nunique = int(s.nunique(dropna=True))
        unique_ratio = nunique / max(n, 1)
        missing = int(s.isna().sum())
        missing_pct = missing / max(n, 1)
        vc = s.value_counts(dropna=True)
        top_val = vc.index[0] if not vc.empty else None
        top_pct = (vc.iloc[0] / n) if not vc.empty else 0.0
        dtype_label = _dtype_label(s)

        flags = []
        if target is not None and col == target:
            flags.append("target")
        if unique_ratio >= 0.95 and nunique > 10:
            flags.append("id-like")
        if nunique <= 1:
            flags.append("constant")
        if missing_pct > 0.5:
            flags.append("mostly-missing")
        elif missing_pct > 0.2:
            flags.append("high-missing")
        if dtype_label == "categorical" and nunique > 50:
            flags.append("high-cardinality")
        if top_pct > 0.95 and nunique > 1:
            flags.append("mode-dominant")

        sample_vals = s.dropna().unique()[:3]
        sample_str = ", ".join(str(v)[:20] for v in sample_vals)

        if dtype_label == "numeric":
            try:
                mean_val = round(float(s.mean()), 2)
                num_range = f"{round(float(s.min()), 2)} → {round(float(s.max()), 2)}"
            except Exception:
                mean_val = None
                num_range = None
        else:
            mean_val = None
            num_range = None

        rows.append(
            {
                "column": col,
                "dtype": dtype_label,
                "missing": missing,
                "missing_pct": round(100 * missing_pct, 1),
                "unique": nunique,
                "unique_pct": round(100 * unique_ratio, 1),
                "top_value": str(top_val)[:30] if top_val is not None else None,
                "top_pct": round(100 * top_pct, 1),
                "mean": mean_val,
                "range": num_range,
                "sample": sample_str,
                "flags": flags,
            }
        )
    return rows


def build_auto_exclude(df: pd.DataFrame, target: str | None) -> list[dict]:
    """Auto-suggested columns to drop before profiling (was the sidebar expander)."""
    n_rows = len(df)
    out = []
    for col in df.columns:
        if target is not None and col == target:
            continue
        s = df[col]
        nunique = s.nunique(dropna=True)
        unique_ratio = nunique / max(n_rows, 1)
        if unique_ratio >= 0.95:
            out.append({"column": col, "reason": f"{unique_ratio:.0%} unique (likely ID/text)"})
        elif nunique <= 1:
            out.append({"column": col, "reason": "constant value"})
        elif s.isna().mean() > 0.95:
            out.append({"column": col, "reason": f"{s.isna().mean():.0%} missing"})
    return out


def inferred_task_map(df: pd.DataFrame) -> dict:
    """Auto-inferred task type per column, for the target picker's default."""
    return {col: infer_task_type(df[col]) for col in df.columns}


# ---------- ML-ready feature summary (was app.py build_ml_ready_summary) ------
def build_ml_ready_summary(
    df: pd.DataFrame, target: str, profile_result, source_fqn: str
) -> pd.DataFrame:
    n = len(df)
    fi = profile_result.feature_importance
    fi_idx = fi.set_index("feature") if not fi.empty else None
    now = datetime.utcnow()
    rows = []
    for col in df.columns:
        s = df[col]
        nunique = int(s.nunique(dropna=True))
        unique_ratio = nunique / max(n, 1)
        missing_pct = float(s.isna().mean())
        vc = s.value_counts(dropna=True)
        top_pct = float(vc.iloc[0] / n) if not vc.empty else 0.0

        if pd.api.types.is_bool_dtype(s):
            dtype = "bool"
        elif pd.api.types.is_numeric_dtype(s):
            dtype = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(s):
            dtype = "datetime"
        else:
            dtype = "categorical"

        is_target = col == target
        kept = True
        drop_reason = ""
        if is_target:
            kept = False
            drop_reason = "is_target"
        elif nunique <= 1:
            kept = False
            drop_reason = "constant"
        elif unique_ratio >= 0.95 and nunique > 10:
            kept = False
            drop_reason = "id_like"
        elif missing_pct > 0.95:
            kept = False
            drop_reason = "mostly_missing"
        elif dtype == "categorical" and nunique > 50:
            kept = False
            drop_reason = "high_cardinality"
        elif top_pct > 0.95 and nunique > 1:
            kept = False
            drop_reason = "mode_dominant"

        if fi_idx is not None and col in fi_idx.index:
            mi = float(fi_idx.loc[col, "mutual_info"])
            t_raw = fi_idx.loc[col, "test"]
            tname = str(t_raw) if pd.notna(t_raw) and t_raw != "-" else None
            stat_raw = fi_idx.loc[col, "statistic"]
            stat = float(stat_raw) if pd.notna(stat_raw) else None
            p_raw = fi_idx.loc[col, "p_value"]
            pv = float(p_raw) if pd.notna(p_raw) else None
        else:
            mi = None
            tname = None
            stat = None
            pv = None

        rows.append(
            {
                "column": col,
                "dtype": dtype,
                "is_target": bool(is_target),
                "kept": bool(kept),
                "drop_reason": drop_reason,
                "missing_pct": round(100 * missing_pct, 3),
                "unique_count": int(nunique),
                "unique_ratio": round(unique_ratio, 4),
                "mutual_info": mi,
                "test_name": tname,
                "statistic": stat,
                "p_value": pv,
                "source_table": source_fqn,
                "profiled_at": now,
            }
        )
    return pd.DataFrame(rows)


# ---------- full Excel report (was app.py build_excel_report) ----------------
def build_excel_report(res) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame([res.overview]).to_excel(writer, sheet_name="overview", index=False)
        if not res.numeric_stats.empty:
            res.numeric_stats.to_excel(writer, sheet_name="numeric_stats", index=False)
        if not res.categorical_stats.empty:
            res.categorical_stats.to_excel(
                writer, sheet_name="categorical_stats", index=False
            )
        res.missing_summary.to_excel(writer, sheet_name="missing", index=False)
        if not res.feature_importance.empty:
            res.feature_importance.to_excel(
                writer, sheet_name="feature_importance", index=False
            )
        tcn = res.target_conditioned.get("numeric")
        if isinstance(tcn, pd.DataFrame) and not tcn.empty:
            tcn.to_excel(writer, sheet_name="target_cond_numeric")
        tcc = res.target_conditioned.get("categorical")
        if isinstance(tcc, pd.DataFrame) and not tcc.empty:
            tcc.to_excel(writer, sheet_name="target_cond_categorical", index=False)
        if res.correlations is not None:
            res.correlations.to_excel(writer, sheet_name="correlations")
    return buf.getvalue()
