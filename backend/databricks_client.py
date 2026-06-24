"""Databricks data-access layer.

Lifted from the original Streamlit ``app.py``. Streamlit's ``@st.cache_resource``
and ``@st.cache_data`` decorators are replaced with explicit module-level caches
so the same connection / listing / table-read behaviour is preserved in a
stateless REST backend.
"""

from __future__ import annotations

import os
import threading
import time
from functools import lru_cache
from typing import Callable

import numpy as np
import pandas as pd
from databricks import sql as dbsql
from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config, oauth_service_principal


class DatabricksNotConfigured(RuntimeError):
    """Raised when the app is not bound to a SQL Warehouse."""


def warehouse_id() -> str:
    wid = os.environ.get("DATABRICKS_WAREHOUSE_ID")
    if not wid:
        raise DatabricksNotConfigured(
            "DATABRICKS_WAREHOUSE_ID is not set. Bind a SQL Warehouse to this app "
            "via the Resources tab and redeploy."
        )
    return wid


# ---------- connection helpers (singletons, like @st.cache_resource) ----------
@lru_cache(maxsize=1)
def get_workspace_client() -> WorkspaceClient:
    return WorkspaceClient()


@lru_cache(maxsize=1)
def get_sql_connection():
    cfg = Config()
    host = cfg.host.replace("https://", "").rstrip("/")

    def cred_provider():
        # On Databricks Apps the injected service principal has client_id/secret,
        # so use the OAuth M2M flow (the path the deployed app relies on). For
        # local dev / other auth (PAT, user OAuth) fall back to the SDK's unified
        # auth so the same code can be exercised end-to-end off-platform.
        if getattr(cfg, "client_id", None) and getattr(cfg, "client_secret", None):
            return oauth_service_principal(cfg)
        return cfg.authenticate

    return dbsql.connect(
        server_hostname=host,
        http_path=f"/sql/1.0/warehouses/{warehouse_id()}",
        credentials_provider=cred_provider,
        # Databricks Apps run in a sandbox with restricted network egress and
        # cannot reach the external cloud-storage host that Cloud Fetch returns
        # pre-signed URLs for (*.storage.cloud.databricks.com -> Connection
        # refused). Force results to stream inline through the SQL endpoint.
        use_cloud_fetch=False,
    )


# ---------- small TTL cache (replaces @st.cache_data(ttl=...)) ----------
class _TTLCache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self._store: dict = {}
        self._lock = threading.Lock()

    def get_or(self, key, fn: Callable):
        now = time.time()
        with self._lock:
            hit = self._store.get(key)
            if hit and now - hit[0] < self.ttl:
                return hit[1]
        val = fn()
        with self._lock:
            self._store[key] = (now, val)
        return val


_listing_cache = _TTLCache(ttl=300)


def list_catalogs() -> list[str]:
    def _fetch():
        w = get_workspace_client()
        return sorted({c.name for c in w.catalogs.list() if c.name})

    return _listing_cache.get_or(("catalogs",), _fetch)


def list_schemas(catalog: str) -> list[str]:
    def _fetch():
        w = get_workspace_client()
        return sorted({s.name for s in w.schemas.list(catalog_name=catalog) if s.name})

    return _listing_cache.get_or(("schemas", catalog), _fetch)


def list_tables(catalog: str, schema: str) -> list[str]:
    def _fetch():
        w = get_workspace_client()
        return sorted(
            {
                t.name
                for t in w.tables.list(catalog_name=catalog, schema_name=schema)
                if t.name
            }
        )

    return _listing_cache.get_or(("tables", catalog, schema), _fetch)


# ---------- table reads (cached DataFrames, like @st.cache_data(ttl=600)) ----------
_DF_TTL = 600
_DF_MAX = 4
_df_cache: dict = {}
_df_lock = threading.Lock()


def _query_table(catalog: str, schema: str, table: str, limit: int) -> pd.DataFrame:
    fqn = f"`{catalog}`.`{schema}`.`{table}`"
    q = f"SELECT * FROM {fqn}"
    if limit and limit > 0:
        q += f" LIMIT {int(limit)}"
    conn = get_sql_connection()
    with conn.cursor() as cur:
        cur.execute(q)
        return cur.fetchall_arrow().to_pandas()


def read_table(catalog: str, schema: str, table: str, limit: int) -> pd.DataFrame:
    """Read a Unity Catalog table into a DataFrame, with a small TTL + LRU cache.

    The same loaded frame is reused across /load, /profile and /column calls so a
    wide table is not re-read from the warehouse on every UI interaction.
    """
    key = (catalog, schema, table, int(limit))
    now = time.time()
    with _df_lock:
        hit = _df_cache.get(key)
        if hit and now - hit[0] < _DF_TTL:
            return hit[1]
    df = _query_table(catalog, schema, table, limit)
    with _df_lock:
        _df_cache[key] = (now, df)
        if len(_df_cache) > _DF_MAX:
            oldest = min(_df_cache, key=lambda k: _df_cache[k][0])
            _df_cache.pop(oldest, None)
    return df


# ---------- writing an ML-ready summary back to a Delta table ----------
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


def _to_native_write(v):
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
            tuple(_to_native_write(v) for v in tup)
            for tup in df.itertuples(index=False, name=None)
        ]
        cur.executemany(f"INSERT INTO {fqn} VALUES ({placeholders})", rows)
    return len(rows)


# ---------- Databricks Jobs (Model Monitor) ----------
def run_job(job_id: int) -> int:
    """Trigger a job run and return the new run_id (does not block)."""
    w = get_workspace_client()
    waiter = w.jobs.run_now(job_id=job_id)
    return int(waiter.run_id)


def cancel_run(run_id: int) -> None:
    """Request cancellation of a job run."""
    w = get_workspace_client()
    w.jobs.cancel_run(run_id=run_id)


def get_run_status(run_id: int) -> dict:
    """Current state of a job run, normalized for the UI."""
    w = get_workspace_client()
    run = w.jobs.get_run(run_id=run_id)
    state = run.state
    life = (
        state.life_cycle_state.value
        if state and state.life_cycle_state
        else None
    )
    result = (
        state.result_state.value if state and state.result_state else None
    )
    return {
        "run_id": int(run_id),
        "life_cycle_state": life,  # PENDING / RUNNING / TERMINATING / TERMINATED ...
        "result_state": result,  # SUCCESS / FAILED / CANCELED / TIMEDOUT
        "state_message": state.state_message if state else None,
        "run_page_url": run.run_page_url,
    }
