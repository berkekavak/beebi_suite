"""
Data Profiler - Streamlit UI.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import io

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from profiler import infer_task_type, profile

st.set_page_config(page_title="Data Profiler", layout="wide", page_icon="📊")

st.title("📊 Data Profiler")
st.caption("Upload a dataset, pick a target, and inspect its statistics.")


# ---------- sidebar: upload + target config ----------
with st.sidebar:
    st.header("1. Upload data")
    uploaded = st.file_uploader(
        "CSV, Excel, or Parquet file",
        type=["csv", "xlsx", "xls", "parquet"],
    )
    sep = st.text_input("CSV separator (if CSV)", value=",")
    sample_size = st.number_input(
        "Sample size (0 = use all rows)",
        min_value=0,
        value=0,
        step=1000,
        help="Useful for very large datasets.",
    )


@st.cache_data(show_spinner=False)
def load_data(file_bytes: bytes, name: str, sep: str) -> pd.DataFrame:
    buf = io.BytesIO(file_bytes)
    lower = name.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(buf, sep=sep)
    if lower.endswith((".xlsx", ".xls")):
        return pd.read_excel(buf)
    if lower.endswith(".parquet"):
        return pd.read_parquet(buf)
    raise ValueError(f"Unsupported file type: {name}")


if uploaded is None:
    st.info("👈 Upload a file in the sidebar to begin.")
    st.stop()

try:
    df = load_data(uploaded.getvalue(), uploaded.name, sep)
except Exception as e:
    st.error(f"Could not read file: {e}")
    st.stop()

if sample_size and sample_size < len(df):
    df = df.sample(sample_size, random_state=42).reset_index(drop=True)

with st.sidebar:
    st.header("2. Target & task")
    target = st.selectbox("Target column", options=list(df.columns))
    inferred = infer_task_type(df[target])
    task = st.radio(
        "Task type",
        options=["classification", "regression"],
        index=0 if inferred == "classification" else 1,
        help=f"Auto-inferred: {inferred}",
    )

    st.header("3. Exclude columns")
    st.caption(
        "Columns to drop before profiling. Useful for IDs, free-text fields, "
        "timestamps, or any feature you don't want in the analysis."
    )

    # Auto-suggest columns to exclude based on heuristics
    n_rows = len(df)
    auto_exclude = []
    exclude_reasons = {}
    for col in df.columns:
        if col == target:
            continue
        s = df[col]
        nunique = s.nunique(dropna=True)
        unique_ratio = nunique / max(n_rows, 1)

        # Heuristic 1: near-unique values (IDs, names, free text)
        if unique_ratio >= 0.95:
            auto_exclude.append(col)
            exclude_reasons[col] = f"{unique_ratio:.0%} unique (likely ID/text)"
        # Heuristic 2: constant columns (zero variance)
        elif nunique <= 1:
            auto_exclude.append(col)
            exclude_reasons[col] = "constant value"
        # Heuristic 3: nearly all missing
        elif s.isna().mean() > 0.95:
            auto_exclude.append(col)
            exclude_reasons[col] = f"{s.isna().mean():.0%} missing"

    if auto_exclude:
        with st.expander(f"🔍 Auto-suggestions ({len(auto_exclude)} found)", expanded=False):
            for col in auto_exclude:
                st.caption(f"• **{col}** — {exclude_reasons[col]}")

    available_cols = [c for c in df.columns if c != target]
    excluded = st.multiselect(
        "Columns to exclude",
        options=available_cols,
        default=auto_exclude,
        help="Pre-filled with auto-suggestions. Edit freely.",
    )

    st.caption(f"**{len(available_cols) - len(excluded)}** features will be profiled.")

    if st.button("Run profile", type="primary", use_container_width=True):
        st.session_state.profile_ran = True

    if st.session_state.get("profile_ran") and st.button(
        "Reset", use_container_width=True
    ):
        st.session_state.profile_ran = False
        st.rerun()

if not st.session_state.get("profile_ran"):
    n = len(df)

    # Top-level dataset health metrics
    st.subheader("Dataset health")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rows", f"{n:,}")
    c2.metric("Columns", df.shape[1])
    c3.metric("Duplicate rows", f"{int(df.duplicated().sum()):,}")
    c4.metric("Missing cells", f"{df.isna().sum().sum():,}")
    c5.metric("Memory", f"{df.memory_usage(deep=True).sum() / (1024**2):.2f} MB")

    # Per-column summary
    st.subheader("Column summary")
    st.caption(
        "Quick scan to help you decide what to exclude. "
        "**Flags** highlight likely problems: 🔑 ID-like · ⚠️ constant · 🕳️ mostly missing · "
        "📝 high-cardinality categorical · 💀 single-value dominance."
    )

    rows = []
    for col in df.columns:
        s = df[col]
        nunique = int(s.nunique(dropna=True))
        unique_ratio = nunique / max(n, 1)
        missing = int(s.isna().sum())
        missing_pct = missing / max(n, 1)

        # Most-frequent value and its share
        vc = s.value_counts(dropna=True)
        top_val = vc.index[0] if not vc.empty else None
        top_pct = (vc.iloc[0] / n) if not vc.empty else 0.0

        # Decide dtype bucket
        if pd.api.types.is_numeric_dtype(s):
            dtype_label = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(s):
            dtype_label = "datetime"
        elif pd.api.types.is_bool_dtype(s):
            dtype_label = "bool"
        else:
            dtype_label = "categorical"

        # Flags
        flags = []
        if col == target:
            flags.append("🎯 target")
        if unique_ratio >= 0.95 and nunique > 10:
            flags.append("🔑 id-like")
        if nunique <= 1:
            flags.append("⚠️ constant")
        if missing_pct > 0.5:
            flags.append("🕳️ mostly missing")
        elif missing_pct > 0.2:
            flags.append("🕳️ high missing")
        if dtype_label == "categorical" and nunique > 50:
            flags.append("📝 high-cardinality")
        if top_pct > 0.95 and nunique > 1:
            flags.append("💀 mode dominant")

        # Sample values (first 3 non-null unique)
        sample_vals = s.dropna().unique()[:3]
        sample_str = ", ".join(str(v)[:20] for v in sample_vals)

        # Numeric-specific stats
        if dtype_label == "numeric":
            try:
                mean_val = round(float(s.mean()), 2)
                min_val = round(float(s.min()), 2)
                max_val = round(float(s.max()), 2)
                num_range = f"{min_val} → {max_val}"
            except Exception:
                mean_val = None
                num_range = "—"
        else:
            mean_val = None
            num_range = "—"

        rows.append(
            {
                "column": col,
                "dtype": dtype_label,
                "missing": missing,
                "missing %": round(100 * missing_pct, 1),
                "unique": nunique,
                "unique %": round(100 * unique_ratio, 1),
                "top value": str(top_val)[:30] if top_val is not None else "—",
                "top %": round(100 * top_pct, 1),
                "mean": mean_val if mean_val is not None else "—",
                "range": num_range,
                "sample": sample_str,
                "flags": " ".join(flags) if flags else "",
            }
        )

    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True, height=400)

    # Quick visual: missing values bar
    miss_plot = summary_df[summary_df["missing"] > 0].sort_values("missing %", ascending=True)
    if not miss_plot.empty:
        st.subheader("Missing values")
        fig = px.bar(
            miss_plot,
            x="missing %",
            y="column",
            orientation="h",
            color="missing %",
            color_continuous_scale="Reds",
            title="Columns with missing values",
        )
        fig.update_layout(height=max(250, 25 * len(miss_plot)), showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Raw data preview (collapsed by default)
    with st.expander("Raw data preview (first 50 rows)", expanded=False):
        st.dataframe(df.head(50), use_container_width=True)

    st.stop()


# ---------- run profile ----------
# Drop excluded columns before profiling
df_profile = df.drop(columns=excluded) if excluded else df
if excluded:
    st.info(f"Excluded {len(excluded)} column(s) from profiling: {', '.join(excluded)}")


@st.cache_data(show_spinner="Profiling dataset...")
def _cached_profile(df_in: pd.DataFrame, target: str, task: str):
    return profile(df_in, target=target, task=task)


result = _cached_profile(df_profile, target, task)


# ---------- overview ----------
st.header("Overview")
ov = result.overview
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rows", f"{ov['rows']:,}")
c2.metric("Columns", ov["columns"])
c3.metric("Memory (MB)", ov["memory_mb"])
c4.metric("Duplicates", f"{ov['duplicates']:,}")
c5.metric("Missing %", f"{ov['missing_pct']}%")

with st.expander("Column dtypes"):
    st.json(ov["dtypes"])


# ---------- target analysis ----------
st.header(f"Target: `{target}` ({task})")
tinfo = result.target_info

if task == "classification":
    dist = tinfo["distribution"]
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("Class distribution")
        st.dataframe(dist, use_container_width=True)
        if "imbalance_ratio" in tinfo:
            st.metric("Imbalance ratio (max/min)", tinfo["imbalance_ratio"])
    with col_b:
        fig = px.bar(
            dist.reset_index(),
            x="class",
            y="count",
            text="count",
            title="Class frequencies",
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
else:
    st.subheader("Target statistics")
    st.json(tinfo["stats"])
    fig = px.histogram(df_profile, x=target, nbins=50, title=f"Distribution of {target}")
    st.plotly_chart(fig, use_container_width=True)


# ---------- feature importance ----------
st.header("Feature importance vs target")
st.caption(
    "Mutual information measures non-linear dependence. "
    "Statistical tests: Pearson r (num→num), ANOVA F (num→cat target or cat→num target), "
    "chi-square (cat→cat). `unique_ratio` = unique values / rows. "
    "`id_like` flags columns with ≥95% unique values — these inflate mutual info "
    "and chi-square artificially and usually should NOT be used as features."
)
fi = result.feature_importance
if not fi.empty:
    n_id_like = int(fi["id_like"].sum())
    if n_id_like > 0:
        flagged = fi.loc[fi["id_like"], "feature"].tolist()
        st.warning(
            f"⚠️ {n_id_like} identifier-like column(s) detected: **{', '.join(flagged)}**. "
            f"Their high mutual information is an artifact of near-unique values, not real predictive power."
        )

    hide_ids = st.checkbox("Hide id-like columns from ranking", value=n_id_like > 0)
    fi_display = fi[~fi["id_like"]] if hide_ids else fi
    fi_display = fi_display.reset_index(drop=True)

    st.dataframe(fi_display, use_container_width=True)

    top = fi_display.head(20)
    if not top.empty:
        fig = px.bar(
            top.iloc[::-1],
            x="mutual_info",
            y="feature",
            color="type",
            orientation="h",
            title="Top features by mutual information",
            hover_data=["unique", "unique_ratio", "p_value"],
        )
        fig.update_layout(height=max(300, 25 * len(top)))
        st.plotly_chart(fig, use_container_width=True)


# ---------- numeric features ----------
st.header("Numeric features")
ns = result.numeric_stats
if not ns.empty:
    st.dataframe(ns, use_container_width=True)

    st.subheader("Distribution explorer")
    numeric_cols = ns["feature"].tolist()
    chosen = st.selectbox("Feature to visualize", numeric_cols, key="num_explorer")

    col_l, col_r = st.columns(2)
    with col_l:
        fig = px.histogram(
            df_profile,
            x=chosen,
            color=target if task == "classification" else None,
            nbins=50,
            marginal="box",
            title=f"Distribution of {chosen}",
        )
        st.plotly_chart(fig, use_container_width=True)
    with col_r:
        if task == "classification":
            fig = px.box(df_profile, x=target, y=chosen, color=target, title=f"{chosen} by class")
        else:
            fig = px.scatter(
                df_profile, x=chosen, y=target, trendline="ols", title=f"{chosen} vs {target}"
            )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Target-conditioned stats")
    tcn = result.target_conditioned["numeric"]
    if isinstance(tcn, pd.DataFrame) and not tcn.empty:
        st.dataframe(tcn, use_container_width=True)
else:
    st.info("No numeric features detected.")


# ---------- categorical features ----------
st.header("Categorical features")
cs = result.categorical_stats
if not cs.empty:
    st.dataframe(cs, use_container_width=True)

    st.subheader("Category explorer")
    cat_cols = cs["feature"].tolist()
    chosen_cat = st.selectbox("Feature to visualize", cat_cols, key="cat_explorer")

    top_n = st.slider("Top N categories", 5, 30, 10)
    vc = df_profile[chosen_cat].value_counts(dropna=False).head(top_n).reset_index()
    vc.columns = [chosen_cat, "count"]
    # Replace NaN with a display-friendly string for plotting
    vc[chosen_cat] = vc[chosen_cat].astype(object).where(vc[chosen_cat].notna(), "(missing)")
    fig = px.bar(vc, x=chosen_cat, y="count", title=f"Top {top_n} values of {chosen_cat}")
    st.plotly_chart(fig, use_container_width=True)

    if task == "classification":
        # Fill NaN in both axes so crosstab keeps missing values as a visible row
        feat_series = df_profile[chosen_cat].fillna("(missing)")
        ct = pd.crosstab(feat_series, df_profile[target], normalize="index") * 100
        # Only reindex with rows that actually exist
        available_rows = [v for v in vc[chosen_cat] if v in ct.index]
        if available_rows:
            ct = ct.loc[available_rows]
        st.dataframe(ct.round(2), use_container_width=True)
    else:
        agg = (
            df_profile.groupby(chosen_cat, dropna=False)[target]
            .agg(["count", "mean", "std"])
            .sort_values("mean", ascending=False)
            .head(top_n)
            .round(4)
        )
        st.dataframe(agg, use_container_width=True)
else:
    st.info("No categorical features detected.")


# ---------- missing values ----------
st.header("Missing values")
ms = result.missing_summary
st.dataframe(ms, use_container_width=True)
miss_nonzero = ms[ms["missing"] > 0]
if not miss_nonzero.empty:
    fig = px.bar(
        miss_nonzero,
        x="feature",
        y="missing_pct",
        title="Missing percentage by feature",
    )
    st.plotly_chart(fig, use_container_width=True)


# ---------- correlations ----------
if result.correlations is not None:
    st.header("Numeric correlation matrix")
    fig = px.imshow(
        result.correlations,
        color_continuous_scale="RdBu_r",
        zmin=-1,
        zmax=1,
        aspect="auto",
        title="Pearson correlations",
    )
    fig.update_layout(height=max(400, 25 * len(result.correlations)))
    st.plotly_chart(fig, use_container_width=True)


# ---------- download report ----------
st.header("Export")


def build_excel_report(res) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame([res.overview]).to_excel(writer, sheet_name="overview", index=False)
        if not res.numeric_stats.empty:
            res.numeric_stats.to_excel(writer, sheet_name="numeric_stats", index=False)
        if not res.categorical_stats.empty:
            res.categorical_stats.to_excel(writer, sheet_name="categorical_stats", index=False)
        res.missing_summary.to_excel(writer, sheet_name="missing", index=False)
        if not res.feature_importance.empty:
            res.feature_importance.to_excel(writer, sheet_name="feature_importance", index=False)
        tcn = res.target_conditioned.get("numeric")
        if isinstance(tcn, pd.DataFrame) and not tcn.empty:
            tcn.to_excel(writer, sheet_name="target_cond_numeric")
        tcc = res.target_conditioned.get("categorical")
        if isinstance(tcc, pd.DataFrame) and not tcc.empty:
            tcc.to_excel(writer, sheet_name="target_cond_categorical", index=False)
        if res.correlations is not None:
            res.correlations.to_excel(writer, sheet_name="correlations")
    return buf.getvalue()


st.download_button(
    "📥 Download full report (Excel)",
    data=build_excel_report(result),
    file_name="data_profile_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)