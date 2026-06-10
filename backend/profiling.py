"""Run the profiler and serialize its result into a single JSON payload.

A small LRU cache keeps the most recent ProfileResult so that /profile, the
Excel export and the save-to-table endpoint don't recompute the (potentially
expensive) profiling pipeline for identical parameters.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np
import pandas as pd

from profiler import ProfileResult, profile

from .ml_ready import build_ml_ready_summary
from .serialize import clean, df_records, matrix_payload


@dataclass(frozen=True)
class ProfileKey:
    catalog: str
    schema: str
    table: str
    limit: int
    target: str
    task: str
    excluded: tuple


_cache: dict = {}
_cache_lock = threading.Lock()
_CACHE_MAX = 2


def run_profile(df: pd.DataFrame, key: ProfileKey) -> tuple[pd.DataFrame, ProfileResult]:
    """Return (df_profile, ProfileResult), memoized on the parameter key."""
    with _cache_lock:
        hit = _cache.get(key)
        if hit is not None:
            return hit

    df_profile = df.drop(columns=list(key.excluded)) if key.excluded else df
    result = profile(df_profile, target=key.target, task=key.task)

    with _cache_lock:
        _cache[key] = (df_profile, result)
        if len(_cache) > _CACHE_MAX:
            _cache.pop(next(iter(_cache)), None)
    return df_profile, result


def _flatten_target_conditioned_numeric(tcn) -> list[dict]:
    """Flatten the classification MultiIndex (feature, stat) columns into records."""
    if not isinstance(tcn, pd.DataFrame) or tcn.empty:
        return []
    flat = tcn.copy()
    if isinstance(flat.columns, pd.MultiIndex):
        flat.columns = ["_".join(str(c) for c in tup) for tup in flat.columns]
    flat = flat.reset_index()
    return df_records(flat)


def _target_histogram(s: pd.Series, bins: int = 40) -> dict | None:
    """Precompute a histogram for a numeric regression target."""
    vals = s.dropna().to_numpy()
    if vals.size == 0 or not np.issubdtype(vals.dtype, np.number):
        return None
    counts, edges = np.histogram(vals, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    return {
        "counts": [int(c) for c in counts],
        "centers": [float(x) for x in centers],
    }


def serialize_profile(
    df_profile: pd.DataFrame,
    result: ProfileResult,
    target: str,
    task: str,
    source_fqn: str,
    excluded: list[str],
) -> dict:
    """Build the full JSON payload consumed by the frontend profiler view."""
    ml_ready = build_ml_ready_summary(df_profile, target, result, source_fqn)
    n_kept = int(ml_ready["kept"].sum())

    # target info: turn the classification distribution DataFrame into records
    tinfo = dict(result.target_info)
    target_block: dict = {
        "task": task,
        "dtype": tinfo.get("dtype"),
        "missing": tinfo.get("missing"),
        "unique": tinfo.get("unique"),
    }
    if task == "classification":
        dist = tinfo.get("distribution")
        if isinstance(dist, pd.DataFrame):
            d = dist.reset_index()
            target_block["distribution"] = df_records(d)
        target_block["imbalance_ratio"] = tinfo.get("imbalance_ratio")
    else:
        target_block["stats"] = clean(tinfo.get("stats", {}))
        target_block["histogram"] = _target_histogram(df_profile[target])

    return {
        "target": target,
        "task": task,
        "source_fqn": source_fqn,
        "excluded": list(excluded),
        "overview": clean(result.overview),
        "target_info": target_block,
        "feature_importance": df_records(result.feature_importance),
        "numeric_stats": df_records(result.numeric_stats),
        "categorical_stats": df_records(result.categorical_stats),
        "missing_summary": df_records(result.missing_summary),
        "correlations": matrix_payload(result.correlations),
        "target_conditioned": {
            "numeric": _flatten_target_conditioned_numeric(
                result.target_conditioned.get("numeric")
            ),
            "categorical": df_records(result.target_conditioned.get("categorical")),
        },
        "ml_ready": {
            "rows": df_records(ml_ready),
            "total": int(len(ml_ready)),
            "kept": n_kept,
            "dropped": int(len(ml_ready) - n_kept),
            "default_output": f"{source_fqn}_ml_ready_profile",
        },
    }


def column_detail(df: pd.DataFrame, column: str, target: str, task: str) -> dict:
    """Sampled column data for the on-demand distribution / category explorer."""
    s = df[column]
    is_numeric = pd.api.types.is_numeric_dtype(s)

    payload: dict = {"column": column, "kind": "numeric" if is_numeric else "categorical"}

    sample = df[[column] + ([target] if target in df.columns else [])]
    if len(sample) > 5000:
        sample = sample.sample(5000, random_state=42)

    if is_numeric:
        pts = []
        for _, row in sample.iterrows():
            x = row[column]
            if pd.isna(x):
                continue
            t = row[target] if target in df.columns else None
            pts.append({"x": float(x), "t": clean(t)})
        payload["points"] = pts
    else:
        vc = s.value_counts(dropna=False).head(30)
        payload["counts"] = [
            {"value": "(missing)" if pd.isna(v) else str(v), "count": int(c)}
            for v, c in vc.items()
        ]
        if task == "classification" and target in df.columns:
            feat = s.fillna("(missing)").astype(str)
            ct = (pd.crosstab(feat, df[target], normalize="index") * 100).round(2)
            top_vals = [c["value"] for c in payload["counts"]]
            ct = ct.loc[[v for v in top_vals if v in ct.index]]
            ct = ct.reset_index()
            ct.columns = ["value"] + [f"P(target={c})" for c in ct.columns[1:]]
            payload["rates"] = df_records(ct)
    return payload
