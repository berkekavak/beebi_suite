"""JSON-safe conversion helpers.

pandas / numpy values (NaN, Inf, np.int64, Timestamps, ...) are not natively
JSON-serializable. Everything leaving the API goes through :func:`clean` so the
frontend always receives plain JSON with ``null`` for missing values.
"""

from __future__ import annotations

import datetime as _dt
import math
from typing import Any

import numpy as np
import pandas as pd


def to_native(v: Any) -> Any:
    """Convert a single scalar to a JSON-safe Python primitive."""
    if v is None:
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (pd.Timestamp, _dt.datetime, _dt.date)):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    if isinstance(v, np.ndarray):
        return [to_native(x) for x in v.tolist()]
    if isinstance(v, (np.str_,)):
        return str(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def clean(obj: Any) -> Any:
    """Recursively convert a nested structure into JSON-safe primitives."""
    if isinstance(obj, dict):
        return {str(k): clean(val) for k, val in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [clean(v) for v in obj.tolist()]
    if isinstance(obj, pd.Series):
        return [clean(v) for v in obj.tolist()]
    return to_native(obj)


def df_records(df: pd.DataFrame) -> list[dict]:
    """Return a DataFrame as a JSON-safe list of row dicts."""
    if df is None or df.empty:
        return []
    return [clean(rec) for rec in df.to_dict(orient="records")]


def matrix_payload(df: pd.DataFrame | None) -> dict | None:
    """Serialize a square/labelled matrix (e.g. a correlation matrix) for a heatmap."""
    if df is None or df.empty:
        return None
    return {
        "labels": [str(c) for c in df.columns],
        "index": [str(i) for i in df.index],
        "z": [[to_native(v) for v in row] for row in df.to_numpy()],
    }
