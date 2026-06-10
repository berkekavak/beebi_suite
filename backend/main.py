"""BeeBI Data Profiler — FastAPI entrypoint.

Serves the JSON API under /api and the static Next.js build at the root, so the
whole product deploys as a single Databricks App (Python runtime).

Run locally:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .routers import catalog, profiler

app = FastAPI(title="BeeBI Data Profiler", version="2.0.0")

# Allow the Next.js dev server (next dev on :3000) to call the API directly.
# In production the frontend is served from this same origin, so CORS is moot.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router, prefix="/api")
app.include_router(profiler.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "beebi-data-profiler"}


# ---------- serve the static frontend build (must be mounted LAST) ----------
_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "out"

if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def _no_build():
        return JSONResponse(
            status_code=200,
            content={
                "message": "API is up, but the frontend has not been built yet.",
                "hint": "cd frontend && npm install && npm run build",
                "api_docs": "/docs",
            },
        )
