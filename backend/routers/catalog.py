"""Catalog browsing + table loading endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import databricks_client as dbx
from ..ml_ready import (
    build_auto_exclude,
    build_column_summary,
    build_health,
    inferred_task_map,
)
from ..serialize import df_records

router = APIRouter(tags=["catalog"])


def _guard(fn):
    try:
        return fn()
    except dbx.DatabricksNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # surface a readable message to the UI
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}")


@router.get("/catalogs")
def catalogs():
    return {"catalogs": _guard(dbx.list_catalogs)}


@router.get("/schemas")
def schemas(catalog: str):
    return {"schemas": _guard(lambda: dbx.list_schemas(catalog))}


@router.get("/tables")
def tables(catalog: str, schema: str):
    return {"tables": _guard(lambda: dbx.list_tables(catalog, schema))}


class LoadRequest(BaseModel):
    catalog: str
    schema: str
    table: str
    limit: int = 100_000
    target: str | None = None


@router.post("/load")
def load(req: LoadRequest):
    """Load a table and return everything the preview screen needs."""
    df = _guard(lambda: dbx.read_table(req.catalog, req.schema, req.table, req.limit))
    source_fqn = f"{req.catalog}.{req.schema}.{req.table}"
    return {
        "source_fqn": source_fqn,
        "columns": [str(c) for c in df.columns],
        "health": build_health(df),
        "column_summary": build_column_summary(df, req.target),
        "auto_exclude": build_auto_exclude(df, req.target),
        "inferred_task": inferred_task_map(df),
        "preview_rows": df_records(df.head(50)),
    }
