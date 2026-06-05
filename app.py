"""
Data Profiler — reads tables from Unity Catalog and writes an ML-ready
feature summary back as a Delta table.

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import io
import os
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from databricks import sql as dbsql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config, oauth_service_principal

from profiler import infer_task_type, profile

st.set_page_config(page_title="Data Profiler", layout="wide", page_icon="📊")
st.title("📊 Data Profiler")
st.caption(
    "Pick a Unity Catalog table, profile it against a target column, "
    "and save the ML-ready feature summary back as a Delta table."
)


WAREHOUSE_ID = os.environ.get("DATABRICKS_WAREHOUSE_ID")
if not WAREHOUSE_ID:
    st.error(
        "`DATABRICKS_WAREHOUSE_ID` is not set. Bind a SQL Warehouse to this app "
        "via the **Resources** tab and redeploy."
    )
    st.stop()


# ---------- connection helpers ----------
@st.cache_resource
def get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient()


@st.cache_resource
def get_sql_connection():
    cfg = Config()
    host = cfg.host.replace("https://", "").rstrip("/")

    def cred_provider():
        return oauth_service_principal(cfg)

    return dbsql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{WAREHOUSE_ID}",
        credentials_provider=cred_provider,
        # Databricks Apps run in a sandbox with restricted network egress and
        # cannot reach the external cloud-storage host that Cloud Fetch returns
        # pre-signed URLs for (*.storage.cloud.databricks.com -> Connection
        # refused). Force results to stream inline through the SQL endpoint.
        use_cloud_fetch=False,
    )


@st.cache_data(ttl=300, show_spinner=False)
def list_catalogs() -> list[str]:
    w = get_workspace_client()
    return sorted({c.name for c in w.catalogs.list() if c.name})


@st.cache_data(ttl=300, show_spinner=False)
def list_schemas(catalog: str) -> list[str]:
    w = get_workspace_client()
    return sorted({s.name for s in w.schemas.list(catalog_name=catalog) if s.name})


@st.cache_data(ttl=300, show_spinner=False)
def list_tables(catalog: str, schema: str) -> list[str]:
    w = get_workspace_client()
    return sorted(
        {t.name for t in w.tables.list(catalog_name=catalog, schema_name=schema) if t.name}
    )


@st.cache_data(ttl=600, show_spinner="Loading table from Databricks...")
def read_table(catalog: str, schema: str, table: str, limit: int) -> pd.DataFrame:
    fqn = f"`{catalog}`.`{schema}`.`{table}`"
    q = f"SELECT * FROM {fqn}"
    if limit and limit > 0:
        q += f" LIMIT {int(limit)}"
    conn = get_sql_connection()
    with conn.cursor() as cur:
        cur.execute(q)
        return cur.fetchall_arrow().to_pandas()


# ---------- writing ML-ready summary back to a Delta table ----------
def _spark_type(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(s):
        return "BIGINT"
    if pd.api.types.is_float_dtype(s):
        return "DOUBLE"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "TIMESTAMP"
    return "STRING"


def _to_native(v):
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return None if np.isnan(v) else float(v)
    if isinstance(v, np.bool_):
        return bool(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def write_summary_table(df: pd.DataFrame, fqn: str) -> int:
    conn = get_sql_connection()
    col_defs = ", ".join(f"`{c}` {_spark_type(df[c])}" for c in df.columns)
    with conn.cursor() as cur:
        cur.execute(f"CREATE OR REPLACE TABLE {fqn} ({col_defs}) USING DELTA")
        if df.empty:
            return 0
        placeholders = ", ".join(["?"] * len(df.columns))
        rows = [
            tuple(_to_native(v) for v in tup)
            for tup in df.itertuples(index=False, name=None)
        ]
        cur.executemany(f"INSERT INTO {fqn} VALUES ({placeholders})", rows)
    return len(rows)


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


# ---------- sidebar: pick table ----------
with st.sidebar:
    st.header("1. Pick table")
    try:
        catalogs = list_catalogs()
    except Exception as e:
        st.error(f"Could not list catalogs: {e}")
        st.stop()
    if not catalogs:
        st.error("No catalogs visible. Grant USE CATALOG to this app's service principal.")
        st.stop()
    default_cat_idx = catalogs.index("workspace") if "workspace" in catalogs else 0
    catalog = st.selectbox("Catalog", catalogs, index=default_cat_idx)

    try:
        schemas = list_schemas(catalog)
    except Exception as e:
        st.error(f"Could not list schemas in `{catalog}`: {e}")
        st.stop()
    if not schemas:
        st.warning("No schemas visible in this catalog.")
        st.stop()
    default_sch_idx = schemas.index("default") if "default" in schemas else 0
    schema = st.selectbox("Schema", schemas, index=default_sch_idx)

    try:
        tables = list_tables(catalog, schema)
    except Exception as e:
        st.error(f"Could not list tables in `{catalog}.{schema}`: {e}")
        st.stop()
    if not tables:
        st.warning("No tables visible in this schema.")
        st.stop()
    default_tbl_idx = (
        tables.index("mdo_retail_sellout_vw") if "mdo_retail_sellout_vw" in tables else 0
    )
    table = st.selectbox("Table", tables, index=default_tbl_idx)

    limit = st.number_input(
        "Row limit (0 = all rows)",
        min_value=0,
        value=100_000,
        step=10_000,
        help="Reading too many rows can exhaust the app's memory. Sample large tables.",
    )


# ---------- load data ----------
try:
    df = read_table(catalog, schema, table, limit)
except Exception as e:
    st.error(f"Failed to read table: {e}")
    st.stop()

source_fqn = f"{catalog}.{schema}.{table}"
st.success(f"Loaded `{source_fqn}` — {len(df):,} rows × {df.shape[1]} cols")


# ---------- sidebar: target & exclusions ----------
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
    st.caption("Columns to drop before profiling.")
    n_rows = len(df)
    auto_exclude = []
    exclude_reasons = {}
    for col in df.columns:
        if col == target:
            continue
        s = df[col]
        nunique = s.nunique(dropna=True)
        unique_ratio = nunique / max(n_rows, 1)
        if unique_ratio >= 0.95:
            auto_exclude.append(col)
            exclude_reasons[col] = f"{unique_ratio:.0%} unique (likely ID/text)"
        elif nunique <= 1:
            auto_exclude.append(col)
            exclude_reasons[col] = "constant value"
        elif s.isna().mean() > 0.95:
            auto_exclude.append(col)
            exclude_reasons[col] = f"{s.isna().mean():.0%} missing"

    if auto_exclude:
        with st.expander(f"🔍 Auto-suggestions ({len(auto_exclude)})", expanded=False):
            for col in auto_exclude:
                st.caption(f"• **{col}** — {exclude_reasons[col]}")

    available_cols = [c for c in df.columns if c != target]
    excluded = st.multiselect(
        "Columns to exclude",
        options=available_cols,
        default=auto_exclude,
        help="Pre-filled with auto-suggestions.",
    )
    st.caption(f"**{len(available_cols) - len(excluded)}** features will be profiled.")

    if st.button("Run profile", type="primary", use_container_width=True):
        st.session_state.profile_ran = True

    if st.session_state.get("profile_ran") and st.button(
        "Reset", use_container_width=True
    ):
        st.session_state.profile_ran = False
        st.rerun()


# ---------- preview mode ----------
if not st.session_state.get("profile_ran"):
    n = len(df)

    st.subheader("Dataset health")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Rows", f"{n:,}")
    c2.metric("Columns", df.shape[1])
    c3.metric("Duplicate rows", f"{int(df.duplicated().sum()):,}")
    c4.metric("Missing cells", f"{df.isna().sum().sum():,}")
    c5.metric("Memory", f"{df.memory_usage(deep=True).sum() / (1024**2):.2f} MB")

    st.subheader("Column summary")
    st.caption(
        "Quick scan to help you decide what to exclude. "
        "**Flags**: 🔑 ID-like · ⚠️ constant · 🕳️ mostly missing · "
        "📝 high-cardinality categorical · 💀 single-value dominance."
    )

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

        if pd.api.types.is_numeric_dtype(s):
            dtype_label = "numeric"
        elif pd.api.types.is_datetime64_any_dtype(s):
            dtype_label = "datetime"
        elif pd.api.types.is_bool_dtype(s):
            dtype_label = "bool"
        else:
            dtype_label = "categorical"

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

        sample_vals = s.dropna().unique()[:3]
        sample_str = ", ".join(str(v)[:20] for v in sample_vals)

        if dtype_label == "numeric":
            try:
                mean_val = round(float(s.mean()), 2)
                num_range = f"{round(float(s.min()), 2)} → {round(float(s.max()), 2)}"
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

    miss_plot = summary_df[summary_df["missing"] > 0].sort_values(
        "missing %", ascending=True
    )
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

    with st.expander("Raw data preview (first 50 rows)", expanded=False):
        st.dataframe(df.head(50), use_container_width=True)

    st.stop()


# ---------- run profile ----------
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
    "chi-square (cat→cat). `id_like` flags columns with ≥95% unique values — those usually "
    "should NOT be used as features."
)
fi = result.feature_importance
if not fi.empty:
    n_id_like = int(fi["id_like"].sum())
    if n_id_like > 0:
        flagged = fi.loc[fi["id_like"], "feature"].tolist()
        st.warning(
            f"⚠️ {n_id_like} identifier-like column(s) detected: **{', '.join(flagged)}**."
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
            fig = px.box(
                df_profile, x=target, y=chosen, color=target, title=f"{chosen} by class"
            )
        else:
            fig = px.scatter(
                df_profile,
                x=chosen,
                y=target,
                trendline="ols",
                title=f"{chosen} vs {target}",
            )
        st.plotly_chart(fig, use_container_width=True)

    tcn = result.target_conditioned["numeric"]
    if isinstance(tcn, pd.DataFrame) and not tcn.empty:
        st.subheader("Target-conditioned stats")
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
    vc[chosen_cat] = vc[chosen_cat].astype(object).where(
        vc[chosen_cat].notna(), "(missing)"
    )
    fig = px.bar(vc, x=chosen_cat, y="count", title=f"Top {top_n} values of {chosen_cat}")
    st.plotly_chart(fig, use_container_width=True)

    if task == "classification":
        feat_series = df_profile[chosen_cat].fillna("(missing)")
        ct = pd.crosstab(feat_series, df_profile[target], normalize="index") * 100
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


# ---------- ML-ready output ----------
st.header("💾 Save ML-ready profile")
ml_ready = build_ml_ready_summary(df_profile, target, result, source_fqn)
st.caption(
    "One row per source column. **kept** = passes auto-exclusion filters "
    "(constant / id_like / mostly_missing / high_cardinality / mode_dominant). "
    "**mutual_info** scores predictive value vs target."
)

n_kept = int(ml_ready["kept"].sum())
n_dropped = len(ml_ready) - n_kept
c_k1, c_k2, c_k3 = st.columns(3)
c_k1.metric("Total columns", len(ml_ready))
c_k2.metric("Kept as features", n_kept)
c_k3.metric("Dropped / target", n_dropped)

st.dataframe(ml_ready, use_container_width=True, hide_index=True)

default_out = f"{catalog}.{schema}.{table}_ml_ready_profile"
out_fqn = st.text_input("Output table (fully qualified)", value=default_out)

c_save, c_dl = st.columns([1, 3])
with c_save:
    if st.button("💾 Save to table", type="primary"):
        try:
            n_written = write_summary_table(ml_ready, out_fqn)
            st.success(f"✅ Wrote {n_written} rows to `{out_fqn}`")
        except Exception as e:
            st.error(f"Write failed: {e}")
with c_dl:
    csv_bytes = ml_ready.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download ML-ready CSV",
        data=csv_bytes,
        file_name=f"{table}_ml_ready_profile.csv",
        mime="text/csv",
    )


# ---------- full Excel export (unchanged) ----------
st.header("Full profile export")


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


st.download_button(
    "📥 Download full report (Excel)",
    data=build_excel_report(result),
    file_name=f"{table}_profile.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
