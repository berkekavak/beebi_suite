"use client";

import { useMemo, useState } from "react";
import Plot from "@/components/Plot";
import { BRAND } from "@/lib/theme";
import {
  Badge,
  Banner,
  Button,
  Card,
  DataTable,
  Field,
  Metric,
  Section,
  Select,
  Spinner,
} from "@/components/ui";

const FLAG_TONE = {
  target: "target",
  "id-like": "warn",
  constant: "danger",
  "mostly-missing": "danger",
  "high-missing": "warn",
  "high-cardinality": "warn",
  "mode-dominant": "warn",
};

export default function Preview({ selection, data, config, setConfig, onRun, running, error }) {
  const [showExclude, setShowExclude] = useState(false);

  const missingRows = useMemo(
    () =>
      [...data.column_summary]
        .filter((c) => c.missing > 0)
        .sort((a, b) => a.missing_pct - b.missing_pct),
    [data]
  );

  const availableCols = data.columns.filter((c) => c !== config.target);

  function toggleExclude(col) {
    setConfig((c) => ({
      ...c,
      excluded: c.excluded.includes(col)
        ? c.excluded.filter((x) => x !== col)
        : [...c.excluded, col],
    }));
  }

  const h = data.health;

  return (
    <div className="space-y-8">
      {/* health */}
      <Section title="Dataset health" subtitle={data.source_fqn}>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <Metric label="Rows" value={h.rows.toLocaleString()} accent />
          <Metric label="Columns" value={h.columns} />
          <Metric label="Duplicate rows" value={h.duplicates.toLocaleString()} />
          <Metric label="Missing cells" value={h.missing_cells.toLocaleString()} />
          <Metric label="Memory" value={`${h.memory_mb} MB`} />
        </div>
      </Section>

      {/* configure */}
      <Section
        title="Configure profiling"
        subtitle="Choose the target, confirm the task type, and drop columns you don't want profiled."
      >
        <Card className="p-5">
          <div className="grid gap-5 md:grid-cols-3">
            <Field label="Target column">
              <Select
                value={config.target}
                onChange={(target) =>
                  setConfig((c) => ({
                    ...c,
                    target,
                    task: data.inferred_task[target] || c.task,
                    excluded: c.excluded.filter((x) => x !== target),
                  }))
                }
                options={data.columns}
              />
            </Field>
            <Field
              label="Task type"
              hint={`Auto-inferred: ${data.inferred_task[config.target] || "—"}`}
            >
              <Select
                value={config.task}
                onChange={(task) => setConfig((c) => ({ ...c, task }))}
                options={["classification", "regression"]}
              />
            </Field>
            <Field label="Excluded columns" hint={`${availableCols.length - config.excluded.length} features will be profiled.`}>
              <Button variant="ghost" onClick={() => setShowExclude((s) => !s)} className="w-full">
                {config.excluded.length} excluded · {showExclude ? "hide" : "edit"}
              </Button>
            </Field>
          </div>

          {data.auto_exclude.length > 0 && (
            <div className="mt-4">
              <Banner tone="warn">
                <span className="font-semibold">{data.auto_exclude.length} auto-suggestion(s):</span>{" "}
                {data.auto_exclude.map((a) => `${a.column} (${a.reason})`).join(" · ")}
              </Banner>
            </div>
          )}

          {showExclude && (
            <div className="mt-4 grid max-h-56 grid-cols-2 gap-1 overflow-auto rounded-lg border border-line p-3 md:grid-cols-3">
              {availableCols.map((col) => (
                <label key={col} className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={config.excluded.includes(col)}
                    onChange={() => toggleExclude(col)}
                    className="accent-honey"
                  />
                  <span className="truncate">{col}</span>
                </label>
              ))}
            </div>
          )}

          {error && (
            <div className="mt-4">
              <Banner tone="error">{error}</Banner>
            </div>
          )}

          <div className="mt-5 flex items-center gap-3">
            <Button onClick={onRun} disabled={running || !config.target}>
              {running ? "Profiling…" : "Run profile"}
            </Button>
            {running && <Spinner label="Computing mutual information & statistics…" />}
          </div>
        </Card>
      </Section>

      {/* column scan */}
      <Section
        title="Column summary"
        subtitle="Quick scan to decide what to exclude. Flags mark likely-problematic columns."
      >
        <DataTable
          rows={data.column_summary}
          columns={[
            "column",
            "dtype",
            "missing_pct",
            "unique",
            "unique_pct",
            "top_value",
            "top_pct",
            "mean",
            "range",
            "flags",
          ]}
          render={{
            flags: (flags) =>
              flags && flags.length ? (
                <span className="flex flex-wrap gap-1">
                  {flags.map((f) => (
                    <Badge key={f} tone={FLAG_TONE[f] || "neutral"}>
                      {f}
                    </Badge>
                  ))}
                </span>
              ) : (
                "—"
              ),
          }}
        />
      </Section>

      {/* missing chart */}
      {missingRows.length > 0 && (
        <Section title="Missing values">
          <Card className="p-4">
            <Plot
              height={Math.max(220, 26 * missingRows.length)}
              data={[
                {
                  type: "bar",
                  orientation: "h",
                  x: missingRows.map((r) => r.missing_pct),
                  y: missingRows.map((r) => r.column),
                  marker: { color: missingRows.map((r) => r.missing_pct), colorscale: "Reds" },
                  hovertemplate: "%{y}: %{x}%<extra></extra>",
                },
              ]}
              layout={{
                margin: { l: 140, r: 16, t: 10, b: 30 },
                xaxis: { title: "% missing", gridcolor: BRAND.sand },
              }}
            />
          </Card>
        </Section>
      )}
    </div>
  );
}
