"""Model Monitor — start/stop Databricks jobs and display their output tables.

Each "tool" tab maps to a Databricks job plus the Unity Catalog table that job
writes its results to. Demand Forecasting is live; the others are placeholders.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import databricks_client as dbx
from ..serialize import df_records

router = APIRouter(tags=["monitor"])


# Per-tool wiring. Add Price Elasticity / MDO here once their jobs + tables exist.
TOOLS: dict[str, dict] = {
    "demand_forecasting": {
        "job_id": 795896357359091,
        "table": "workspace.demand_pred_outputs.demand_outputs_postprocessed",
        "limit": 1000,
    },
}


def _guard(fn):
    try:
        return fn()
    except dbx.DatabricksNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:  # surface a readable message to the UI
        raise HTTPException(status_code=502, detail=f"{type(e).__name__}: {e}")


def _tool(name: str) -> dict:
    cfg = TOOLS.get(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"Unknown tool '{name}'")
    return cfg


class ToolRequest(BaseModel):
    tool: str


class RunIdRequest(BaseModel):
    run_id: int


@router.post("/monitor/run")
def run(req: ToolRequest):
    cfg = _tool(req.tool)
    run_id = _guard(lambda: dbx.run_job(cfg["job_id"]))
    return {"run_id": run_id}


@router.post("/monitor/cancel")
def cancel(req: RunIdRequest):
    _guard(lambda: dbx.cancel_run(req.run_id))
    return {"canceled": req.run_id}


@router.get("/monitor/run-status")
def run_status(run_id: int):
    return _guard(lambda: dbx.get_run_status(run_id))


@router.post("/monitor/results")
def results(req: ToolRequest):
    cfg = _tool(req.tool)
    catalog, schema, table = cfg["table"].split(".")
    df = _guard(lambda: dbx.read_table(catalog, schema, table, cfg["limit"]))
    return {
        "table": cfg["table"],
        "columns": [str(c) for c in df.columns],
        "rows": df_records(df),
        "row_count": int(len(df)),
    }
