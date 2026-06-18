# BeeBI Intelligence Suite — Data Profiler

A Databricks-native data profiling tool with a modern React UI. Pick a Unity
Catalog table, profile it against a target column, explore distributions and
feature importance, and write an ML-ready feature summary back as a Delta table.

The profiler is the first tool in a growing suite — the app shell is built so new
tools slot in as their own backend router + frontend route.

## Architecture

```
┌──────────────────────────────────────────────┐
│  FastAPI (Python)                              │
│  ├── profiler.py        ← pure analysis engine │   one Databricks App,
│  ├── backend/           ← API + Databricks I/O │   Python runtime
│  │   └── /api/*  JSON endpoints                │
│  └── serves frontend/out/ as static files ─────┼──┐
└──────────────────────────────────────────────┘  │
        ▲ build output                              │
┌──────────────────────────────────────────────┐  │
│  Next.js (React, static export) → frontend/out │◄─┘
└──────────────────────────────────────────────┘
```

The Python heavy-lifting (pandas / scipy / scikit-learn) stays in Python; only
the presentation layer is Node/React. Next.js is built to **static HTML/JS**
(`output: 'export'`), which FastAPI serves — so the whole product deploys as a
**single Databricks App** on the Python runtime, exactly like the old Streamlit
app. There is no Node process at runtime.

## Project layout

```
beebi_suite/
├── profiler.py            # core analysis (unchanged, pure functions)
├── cli.py                 # command-line interface (unchanged)
├── backend/               # FastAPI app
│   ├── main.py            # entrypoint: mounts /api and serves frontend/out
│   ├── databricks_client.py
│   ├── ml_ready.py
│   ├── profiling.py
│   ├── serialize.py
│   └── routers/{catalog,profiler}.py
├── frontend/              # Next.js UI (React + Tailwind + Plotly)
│   ├── app/               # routes: / (dashboard), /profiler
│   ├── components/
│   └── lib/
├── app.yaml               # Databricks Apps: runs uvicorn
└── requirements.txt
```

## Local development

Run the API and the UI as two processes (two ports — only in dev):

```bash
# 1. Backend (port 8000)
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# 2. Frontend (port 3000) — in another terminal
cd frontend
cp .env.local.example .env.local      # points the UI at http://localhost:8000
npm install
npm run dev
```

Open http://localhost:3000. (Browsing Unity Catalog needs Databricks auth /
`DATABRICKS_WAREHOUSE_ID`; locally use a `.databrickscfg` profile or env vars.)

## Build for production

```bash
cd frontend
npm install
npm run build          # → frontend/out/ (static site)
```

Then the single FastAPI process serves both API and UI:

```bash
uvicorn backend.main:app --port 8000   # open http://localhost:8000
```

## Deploy to Databricks Apps

1. Build the frontend (`npm run build`) so `frontend/out/` exists.
2. Sync the project and deploy — `app.yaml` runs `uvicorn backend.main:app`.
3. Bind a SQL Warehouse via the app's **Resources** tab (provides
   `DATABRICKS_WAREHOUSE_ID`).

> `frontend/out/` **must** be present at deploy time. `databricks sync` skips
> `.gitignore`d paths, so `out/` is deliberately not ignored. Build it before
> deploying (or build it in CI). `node_modules/` and `.next/` are ignored.

## CLI / library use (unchanged)

```bash
python cli.py data.csv --target churn
python cli.py data.csv --target price --task regression --output report.xlsx
```

```python
import pandas as pd
from profiler import profile

result = profile(pd.read_csv("data.csv"), target="churn")
print(result.feature_importance)
```

## What it computes

Overview (rows/cols/memory/duplicates/missing), target analysis (class
distribution + imbalance, or regression stats), per-feature numeric &
categorical stats, target-conditioned analysis, feature importance (mutual
information + Pearson / ANOVA F / chi-square), missing-value report, numeric
correlation matrix, and an ML-ready per-column summary (kept/dropped with
reasons) written back to Delta or exported as CSV / multi-sheet Excel.

## Migrating from the old Streamlit app

`app.py` (Streamlit) is retained during the transition but no longer deployed —
`app.yaml` now runs FastAPI. To run the legacy UI locally:
`pip install streamlit plotly statsmodels && streamlit run app.py`. Delete
`app.py` once you're happy with the new UI.
