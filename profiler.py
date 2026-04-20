"""
Data Profiler - core analysis module.

Analyzes a dataset against a target label, computing:
- Dataset overview (shape, memory, missing values, dtypes)
- Per-feature statistics (numeric + categorical)
- Target-conditioned analysis (distributions, group stats, correlations)
- Feature-target relationships (mutual info, correlation, ANOVA/chi-square)
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.feature_selection import (
    mutual_info_classif,
    mutual_info_regression,
)

warnings.filterwarnings("ignore")


TaskType = str  # "classification" | "regression"


@dataclass
class ProfileResult:
    """Container for all profiling results."""

    overview: Dict[str, Any] = field(default_factory=dict)
    target_info: Dict[str, Any] = field(default_factory=dict)
    numeric_stats: pd.DataFrame = field(default_factory=pd.DataFrame)
    categorical_stats: pd.DataFrame = field(default_factory=pd.DataFrame)
    missing_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    target_conditioned: Dict[str, pd.DataFrame] = field(default_factory=dict)
    feature_importance: pd.DataFrame = field(default_factory=pd.DataFrame)
    correlations: Optional[pd.DataFrame] = None


def infer_task_type(series: pd.Series, threshold: int = 20) -> TaskType:
    """Infer whether the target implies classification or regression."""
    s = series.dropna()
    if s.dtype == "object" or s.dtype.name == "category" or s.dtype == "bool":
        return "classification"
    unique_ratio = s.nunique() / max(len(s), 1)
    if s.nunique() <= threshold and unique_ratio < 0.05:
        return "classification"
    if pd.api.types.is_integer_dtype(s) and s.nunique() <= threshold:
        return "classification"
    return "regression"


def _split_columns(df: pd.DataFrame, target: str) -> tuple[List[str], List[str]]:
    """Split columns into numeric and categorical, excluding the target."""
    features = [c for c in df.columns if c != target]
    numeric = [c for c in features if pd.api.types.is_numeric_dtype(df[c])]
    categorical = [c for c in features if c not in numeric]
    return numeric, categorical


def build_overview(df: pd.DataFrame, target: str) -> Dict[str, Any]:
    """Top-level dataset summary."""
    mem_mb = df.memory_usage(deep=True).sum() / (1024 ** 2)
    duplicates = int(df.duplicated().sum())
    missing_cells = int(df.isna().sum().sum())
    total_cells = df.size
    return {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "target": target,
        "memory_mb": round(mem_mb, 3),
        "duplicates": duplicates,
        "missing_cells": missing_cells,
        "missing_pct": round(100 * missing_cells / max(total_cells, 1), 3),
        "dtypes": df.dtypes.astype(str).to_dict(),
    }


def build_target_info(df: pd.DataFrame, target: str, task: TaskType) -> Dict[str, Any]:
    """Describe the target column itself."""
    s = df[target]
    info: Dict[str, Any] = {
        "task": task,
        "dtype": str(s.dtype),
        "missing": int(s.isna().sum()),
        "unique": int(s.nunique(dropna=True)),
    }
    if task == "classification":
        counts = s.value_counts(dropna=False)
        pct = (counts / counts.sum() * 100).round(3)
        dist = pd.DataFrame({"count": counts, "percent": pct})
        dist.index.name = "class"
        info["distribution"] = dist
        # Imbalance ratio: largest class / smallest class
        if len(counts) > 1:
            info["imbalance_ratio"] = round(counts.max() / counts.min(), 3)
    else:
        info["stats"] = {
            "mean": float(s.mean()),
            "std": float(s.std()),
            "min": float(s.min()),
            "q25": float(s.quantile(0.25)),
            "median": float(s.median()),
            "q75": float(s.quantile(0.75)),
            "max": float(s.max()),
            "skew": float(s.skew()),
            "kurtosis": float(s.kurtosis()),
        }
    return info


def numeric_stats(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Rich descriptive stats for numeric columns."""
    if not columns:
        return pd.DataFrame()
    rows = []
    for c in columns:
        s = df[c].dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        outliers = int(((s < lower) | (s > upper)).sum())
        rows.append(
            {
                "feature": c,
                "count": int(s.count()),
                "missing": int(df[c].isna().sum()),
                "missing_pct": round(100 * df[c].isna().mean(), 3),
                "unique": int(s.nunique()),
                "mean": round(float(s.mean()), 4),
                "std": round(float(s.std()), 4),
                "min": round(float(s.min()), 4),
                "q25": round(float(q1), 4),
                "median": round(float(s.median()), 4),
                "q75": round(float(q3), 4),
                "max": round(float(s.max()), 4),
                "skew": round(float(s.skew()), 4),
                "kurtosis": round(float(s.kurtosis()), 4),
                "outliers_iqr": outliers,
                "zeros": int((s == 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def categorical_stats(df: pd.DataFrame, columns: List[str]) -> pd.DataFrame:
    """Descriptive stats for categorical / object columns."""
    if not columns:
        return pd.DataFrame()
    rows = []
    for c in columns:
        s = df[c]
        vc = s.value_counts(dropna=True)
        top = vc.index[0] if not vc.empty else None
        top_freq = int(vc.iloc[0]) if not vc.empty else 0
        rows.append(
            {
                "feature": c,
                "count": int(s.count()),
                "missing": int(s.isna().sum()),
                "missing_pct": round(100 * s.isna().mean(), 3),
                "unique": int(s.nunique(dropna=True)),
                "top_value": str(top) if top is not None else None,
                "top_freq": top_freq,
                "top_pct": round(100 * top_freq / max(len(s), 1), 3),
                "mode_dominance": round(top_freq / max(s.count(), 1), 4),
            }
        )
    return pd.DataFrame(rows)


def missing_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column missing-value report."""
    miss = df.isna().sum()
    out = pd.DataFrame(
        {
            "feature": miss.index,
            "missing": miss.values,
            "missing_pct": (miss / len(df) * 100).round(3).values,
            "dtype": df.dtypes.astype(str).values,
        }
    )
    return out.sort_values("missing", ascending=False).reset_index(drop=True)


def target_conditioned_numeric(
    df: pd.DataFrame, numeric_cols: List[str], target: str, task: TaskType
) -> pd.DataFrame:
    """
    For classification: group-wise mean/std of each numeric feature per class.
    For regression: correlation between each numeric feature and the target.
    """
    if not numeric_cols:
        return pd.DataFrame()

    if task == "classification":
        grouped = df.groupby(target)[numeric_cols].agg(["mean", "std"])
        grouped = grouped.round(4)
        return grouped

    # regression: pearson + spearman correlations with target
    rows = []
    tgt = df[target]
    for c in numeric_cols:
        s = df[c]
        mask = s.notna() & tgt.notna()
        if mask.sum() < 3:
            continue
        pear = stats.pearsonr(s[mask], tgt[mask])[0]
        spear = stats.spearmanr(s[mask], tgt[mask])[0]
        rows.append(
            {
                "feature": c,
                "pearson": round(float(pear), 4),
                "spearman": round(float(spear), 4),
                "abs_pearson": round(abs(float(pear)), 4),
            }
        )
    return pd.DataFrame(rows).sort_values("abs_pearson", ascending=False).reset_index(drop=True)


def target_conditioned_categorical(
    df: pd.DataFrame, cat_cols: List[str], target: str, task: TaskType
) -> pd.DataFrame:
    """
    For classification: cross-tab row percentages (P(target | feature value)).
    For regression: group-mean of target per category, sorted by mean.
    """
    if not cat_cols:
        return pd.DataFrame()

    frames = []
    for c in cat_cols:
        if task == "classification":
            ct = pd.crosstab(df[c], df[target], normalize="index") * 100
            ct = ct.round(2)
            ct.columns = [f"P(target={col})" for col in ct.columns]
        else:
            agg = df.groupby(c)[target].agg(["count", "mean", "std"]).round(4)
            ct = agg
        ct.insert(0, "feature", c)
        ct = ct.reset_index().rename(columns={c: "value"})
        frames.append(ct)
    if not frames:
        return pd.DataFrame()
    # keep only top 20 rows per feature to avoid explosions
    trimmed = [f.head(20) for f in frames]
    return pd.concat(trimmed, ignore_index=True)


def feature_importance(
    df: pd.DataFrame, target: str, task: TaskType
) -> pd.DataFrame:
    """Mutual information + simple statistical test per feature vs target."""
    numeric_cols, cat_cols = _split_columns(df, target)

    # Build feature matrix (encode categoricals, impute)
    X_parts = []
    feat_names = []
    is_discrete = []

    for c in numeric_cols:
        X_parts.append(df[c].fillna(df[c].median()).to_numpy().reshape(-1, 1))
        feat_names.append(c)
        is_discrete.append(False)

    for c in cat_cols:
        codes = df[c].astype("category").cat.codes.replace(-1, 0).to_numpy().reshape(-1, 1)
        X_parts.append(codes)
        feat_names.append(c)
        is_discrete.append(True)

    if not X_parts:
        return pd.DataFrame()

    X = np.hstack(X_parts)
    y_raw = df[target]

    if task == "classification":
        y = y_raw.astype("category").cat.codes.to_numpy()
        mask = y >= 0
        mi = mutual_info_classif(
            X[mask], y[mask], discrete_features=is_discrete, random_state=42
        )
    else:
        y = y_raw.to_numpy()
        mask = ~pd.isna(y)
        mi = mutual_info_regression(
            X[mask], y[mask], discrete_features=is_discrete, random_state=42
        )

    # Statistical test per feature
    test_stats = []
    p_values = []
    test_names = []
    for i, name in enumerate(feat_names):
        col = X[:, i]
        try:
            if task == "classification":
                if is_discrete[i]:
                    # chi-square on contingency
                    ct = pd.crosstab(df[name].fillna("__NA__"), y_raw.astype(str))
                    chi2, p, _, _ = stats.chi2_contingency(ct)
                    test_stats.append(round(float(chi2), 4))
                    p_values.append(round(float(p), 6))
                    test_names.append("chi2")
                else:
                    # one-way ANOVA F-test across classes
                    groups = [
                        df[name].dropna()[y_raw == cls]
                        for cls in y_raw.dropna().unique()
                    ]
                    groups = [g for g in groups if len(g) > 1]
                    if len(groups) >= 2:
                        f, p = stats.f_oneway(*groups)
                        test_stats.append(round(float(f), 4))
                        p_values.append(round(float(p), 6))
                        test_names.append("anova_f")
                    else:
                        test_stats.append(np.nan)
                        p_values.append(np.nan)
                        test_names.append("-")
            else:
                if is_discrete[i]:
                    # ANOVA: does target mean differ across categories?
                    groups = [
                        df[target].dropna()[df[name] == v]
                        for v in df[name].dropna().unique()
                    ]
                    groups = [g for g in groups if len(g) > 1]
                    if len(groups) >= 2:
                        f, p = stats.f_oneway(*groups)
                        test_stats.append(round(float(f), 4))
                        p_values.append(round(float(p), 6))
                        test_names.append("anova_f")
                    else:
                        test_stats.append(np.nan)
                        p_values.append(np.nan)
                        test_names.append("-")
                else:
                    mask_i = df[name].notna() & df[target].notna()
                    if mask_i.sum() >= 3:
                        r, p = stats.pearsonr(df[name][mask_i], df[target][mask_i])
                        test_stats.append(round(float(r), 4))
                        p_values.append(round(float(p), 6))
                        test_names.append("pearson_r")
                    else:
                        test_stats.append(np.nan)
                        p_values.append(np.nan)
                        test_names.append("-")
        except Exception:
            test_stats.append(np.nan)
            p_values.append(np.nan)
            test_names.append("-")

    n_rows = len(df)
    unique_counts = [int(df[f].nunique(dropna=True)) for f in feat_names]
    unique_ratios = [round(u / max(n_rows, 1), 4) for u in unique_counts]
    # Flag columns that look like row identifiers: very high cardinality
    # relative to row count (>= 95% unique). These inflate MI / chi2 spuriously.
    id_like_flags = [r >= 0.95 for r in unique_ratios]

    out = pd.DataFrame(
        {
            "feature": feat_names,
            "type": ["categorical" if d else "numeric" for d in is_discrete],
            "unique": unique_counts,
            "unique_ratio": unique_ratios,
            "id_like": id_like_flags,
            "mutual_info": np.round(mi, 4),
            "test": test_names,
            "statistic": test_stats,
            "p_value": p_values,
        }
    )
    return out.sort_values("mutual_info", ascending=False).reset_index(drop=True)


def numeric_correlations(df: pd.DataFrame, target: str) -> Optional[pd.DataFrame]:
    """Correlation matrix among numeric features (including target if numeric)."""
    numeric = df.select_dtypes(include=np.number)
    if numeric.shape[1] < 2:
        return None
    return numeric.corr(method="pearson").round(4)


def profile(df: pd.DataFrame, target: str, task: Optional[TaskType] = None) -> ProfileResult:
    """Run the full profiling pipeline."""
    if target not in df.columns:
        raise ValueError(f"Target '{target}' not in dataframe columns.")

    task = task or infer_task_type(df[target])
    numeric_cols, cat_cols = _split_columns(df, target)

    result = ProfileResult()
    result.overview = build_overview(df, target)
    result.target_info = build_target_info(df, target, task)
    result.numeric_stats = numeric_stats(df, numeric_cols)
    result.categorical_stats = categorical_stats(df, cat_cols)
    result.missing_summary = missing_summary(df)
    result.target_conditioned = {
        "numeric": target_conditioned_numeric(df, numeric_cols, target, task),
        "categorical": target_conditioned_categorical(df, cat_cols, target, task),
    }
    result.feature_importance = feature_importance(df, target, task)
    result.correlations = numeric_correlations(df, target)
    return result