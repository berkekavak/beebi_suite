"use client";

import { useEffect, useState } from "react";
import Plot from "@/components/Plot";
import { api } from "@/lib/api";
import { BRAND } from "@/lib/theme";
import { Card, DataTable, Select, Spinner } from "@/components/ui";

export default function ColumnExplorer({ selection, config, columns, label }) {
  const [col, setCol] = useState(columns[0] || "");
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!col) return;
    setBusy(true);
    setError("");
    api
      .column({ ...selection, ...config, column: col })
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  }, [col]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Card className="p-4">
      <div className="mb-3 max-w-xs">
        <Select value={col} onChange={setCol} options={columns} />
      </div>
      {busy && <Spinner label={`Loading ${label}…`} />}
      {error && <p className="text-sm text-red-700">{error}</p>}
      {!busy && detail && detail.kind === "numeric" && (
        <NumericView detail={detail} task={config.task} target={config.target} />
      )}
      {!busy && detail && detail.kind === "categorical" && (
        <CategoricalView detail={detail} />
      )}
    </Card>
  );
}

function NumericView({ detail, task, target }) {
  const xs = detail.points.map((p) => p.x);
  if (task === "classification") {
    const byClass = {};
    detail.points.forEach((p) => {
      const k = String(p.t);
      (byClass[k] = byClass[k] || []).push(p.x);
    });
    const traces = Object.entries(byClass).map(([k, vals]) => ({
      type: "histogram",
      x: vals,
      name: k,
      opacity: 0.65,
      nbinsx: 40,
    }));
    return (
      <Plot data={traces} layout={{ barmode: "overlay", legend: { title: { text: target } } }} />
    );
  }
  // regression: histogram + a scatter vs target
  const ts = detail.points.map((p) => p.t);
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Plot data={[{ type: "histogram", x: xs, nbinsx: 40, marker: { color: BRAND.honey } }]} />
      <Plot
        data={[
          {
            type: "scattergl",
            mode: "markers",
            x: xs,
            y: ts,
            marker: { color: BRAND.honey, size: 5, opacity: 0.5 },
          },
        ]}
        layout={{ yaxis: { title: target } }}
      />
    </div>
  );
}

function CategoricalView({ detail }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Plot
        data={[
          {
            type: "bar",
            x: detail.counts.map((c) => c.value),
            y: detail.counts.map((c) => c.count),
            marker: { color: BRAND.honey },
          },
        ]}
        layout={{ margin: { b: 90 }, xaxis: { tickangle: -40 } }}
      />
      {detail.rates && detail.rates.length > 0 ? (
        <DataTable rows={detail.rates} maxHeight={320} />
      ) : (
        <div className="flex items-center justify-center text-sm text-ink-muted">
          No per-class rates for this column.
        </div>
      )}
    </div>
  );
}
