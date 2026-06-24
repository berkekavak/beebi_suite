"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Banner, Button, Card, DataTable, Badge, Spinner } from "@/components/ui";

const TOOL = "demand_forecasting";
const ACTIVE = ["PENDING", "QUEUED", "RUNNING", "TERMINATING", "BLOCKED"];
const RESULT_TONE = {
  SUCCESS: "ok",
  FAILED: "danger",
  CANCELED: "warn",
  TIMEDOUT: "danger",
};

function isActive(status) {
  return status && ACTIVE.includes(status.life_cycle_state);
}

export default function DemandForecasting() {
  const [runId, setRunId] = useState(null);
  const [status, setStatus] = useState(null);
  const [results, setResults] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loadedFor = useRef(null); // guards against loading results twice

  async function start() {
    setError("");
    setResults(null);
    setBusy(true);
    try {
      const { run_id } = await api.monitorRun(TOOL);
      setRunId(run_id);
      setStatus({ life_cycle_state: "PENDING", result_state: null });
      loadedFor.current = null;
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function stop() {
    if (!runId) return;
    setError("");
    try {
      await api.monitorCancel(runId);
    } catch (e) {
      setError(e.message);
    }
  }

  const loadResults = useCallback(async () => {
    try {
      const res = await api.monitorResults(TOOL);
      setResults(res);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  // Poll run status every 5s while the run is active.
  useEffect(() => {
    if (!runId || !isActive(status)) return;
    const id = setInterval(async () => {
      try {
        const s = await api.monitorStatus(runId);
        setStatus(s);
      } catch (e) {
        setError(e.message);
      }
    }, 5000);
    return () => clearInterval(id);
  }, [runId, status]);

  // Auto-load results once the run succeeds.
  useEffect(() => {
    if (
      status &&
      status.life_cycle_state === "TERMINATED" &&
      status.result_state === "SUCCESS" &&
      loadedFor.current !== runId
    ) {
      loadedFor.current = runId;
      loadResults();
    }
  }, [status, runId, loadResults]);

  const active = isActive(status);
  const terminated = status && status.life_cycle_state === "TERMINATED";

  return (
    <div className="space-y-5">
      <Card className="p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h3 className="font-bold text-ink">Demand Forecasting</h3>
            <p className="mt-1 text-sm text-ink-muted">
              Run the forecasting job, then view its output table.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={start} disabled={busy || active}>
              {busy ? "Starting…" : active ? "Running…" : "Run job"}
            </Button>
            {active && (
              <Button variant="ghost" onClick={stop}>
                Stop job
              </Button>
            )}
          </div>
        </div>

        {(status || active) && (
          <div className="mt-4 flex items-center gap-3 text-sm">
            {active && <Spinner label="Job running…" />}
            {status && (
              <Badge tone={RESULT_TONE[status.result_state] || "neutral"}>
                {status.result_state || status.life_cycle_state}
              </Badge>
            )}
            {status?.run_page_url && (
              <a
                href={status.run_page_url}
                target="_blank"
                rel="noreferrer"
                className="text-honey-700 underline"
              >
                open in Databricks
              </a>
            )}
            {status?.state_message && (
              <span className="text-ink-muted">{status.state_message}</span>
            )}
          </div>
        )}

        {error && (
          <div className="mt-4">
            <Banner tone="error">{error}</Banner>
          </div>
        )}

        {terminated && status.result_state !== "SUCCESS" && (
          <div className="mt-4">
            <Banner tone="warn">
              Job ended with state “{status.result_state || status.life_cycle_state}”.
              No results loaded.
            </Banner>
          </div>
        )}
      </Card>

      {results && (
        <Card className="p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-bold text-ink">Results</h3>
            <span className="text-xs text-ink-muted">
              {results.row_count.toLocaleString()} rows · {results.table}
            </span>
          </div>
          <DataTable rows={results.rows} columns={results.columns} />
        </Card>
      )}
    </div>
  );
}
