"""Profiling, save-to-table, column-detail and Excel-export endpoints."""

from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import databricks_client as dbx
from ..ml_ready import build_excel_report, build_ml_ready_summary
from ..profiling import ProfileKey, column_detail, run_profile, serialize_profile

router = APIRouter(tags=["profiler"])


class ProfileRequest(BaseModel):
    catalog: str
    schema: str
    table: str
    limit: int = 100_000
    target: str
    task: str  # "classification" | "regression"
    excluded: list[str] = []


def _load_and_key(req: ProfileRequest):
    try:
        df = dbx.read_table(req.catalog, req.schema, req.table, req.limit)
    except dbx.DatabricksNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}")
    key = ProfileKey(
        catalog=req.catalog,
        schema=req.schema,
        table=req.table,
        limit=int(req.limit),
        target=req.target,
        task=req.task,
        excluded=tuple(req.excluded),
    )
    return df, key


@router.post("/profile")
def profile_table(req: ProfileRequest):
    df, key = _load_and_key(req)
    source_fqn = f"{req.catalog}.{req.schema}.{req.table}"
    try:
        df_profile, result = run_profile(df, key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Profiling failed: {e}")
    return serialize_profile(
        df_profile, result, req.target, req.task, source_fqn, req.excluded
    )


class ColumnRequest(ProfileRequest):
    column: str


@router.post("/column")
def column(req: ColumnRequest):
    """Sampled data for one column, for the distribution / category explorer."""
    df, key = _load_and_key(req)
    df_profile, _ = run_profile(df, key)
    if req.column not in df_profile.columns:
        raise HTTPException(status_code=404, detail=f"Column '{req.column}' not found")
    return column_detail(df_profile, req.column, req.target, req.task)


class SaveRequest(ProfileRequest):
    output_table: str


@router.post("/save")
def save(req: SaveRequest):
    df, key = _load_and_key(req)
    source_fqn = f"{req.catalog}.{req.schema}.{req.table}"
    df_profile, result = run_profile(df, key)
    ml_ready = build_ml_ready_summary(df_profile, req.target, result, source_fqn)
    try:
        n = dbx.write_summary_table(ml_ready, req.output_table)
    except dbx.DatabricksNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Write failed: {e}")
    return {"written": n, "output_table": req.output_table}


@router.post("/export")
def export_excel(req: ProfileRequest):
    df, key = _load_and_key(req)
    _, result = run_profile(df, key)
    data = build_excel_report(result)
    filename = f"{req.table}_profile.xlsx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
