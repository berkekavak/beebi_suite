"use client";

import { useMemo, useState } from "react";
import Plot from "@/components/Plot";
import { api, downloadBlob } from "@/lib/api";
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
  Spinner,
} from "@/components/ui";
import ColumnExplorer from "./ColumnExplorer";

export default function Results({ profile, selection, config }) {
  return (
    <div className="space-y-10">
      <Overview profile={profile} />
      <TargetAnalysis profile={profile} />
      <FeatureImportance profile={profile} />
      <NumericFeatures profile={profile} selection={selection} config={config} />
      <CategoricalFeatures profile={profile} selection={selection} config={config} />
      <Missing profile={profile} />
      <Correlations profile={profile} />
      <MlReady profile={profile} selection={selection} config={config} />
    </div>
  );
}

function Overview({ profile }) {
  const ov = profile.overview;
  return (
    <Section title="Overview">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Metric label="Rows" value={ov.rows.toLocaleString()} accent />
        <Metric label="Columns" value={ov.columns} />
        <Metric label="Memory (MB)" value={ov.memory_mb} />
        <Metric label="Duplicates" value={ov.duplicates.toLocaleString()} />
        <Metric label="Missing %" value={`${ov.missing_pct}%`} />
      </div>
    </Section>
  );
}

function TargetAnalysis({ profile }) {
  const t = profile.target_info;
  return (
    <Section title={`Target: ${profile.target}`} subtitle={profile.task}>
      {profile.task === "classification" ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-4">
            <DataTable rows={t.distribution || []} maxHeight={320} />
            {t.imbalance_ratio != null && (
              <p className="mt-3 text-sm text-ink-muted">
                Imbalance ratio (max/min):{" "}
                <span className="font-bold text-honey-700">{t.imbalance_ratio}</span>
              </p>
            )}
          </Card>
          <Card className="p-4">
            <Plot
              data={[
                {
                  type: "bar",
                  x: (t.distribution || []).map((d) => String(d.class)),
                  y: (t.distribution || []).map((d) => d.count),
                  text: (t.distribution || []).map((d) => d.count),
                  marker: { color: BRAND.honey },
                },
              ]}
            />
          </Card>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="p-4">
            <DataTable
              rows={Object.entries(t.stats || {}).map(([k, v]) => ({ stat: k, value: v }))}
              maxHeight={320}
            />
          </Card>
          <Card className="p-4">
            {t.histogram ? (
              <Plot
                data={[
                  {
                    type: "bar",
                    x: t.histogram.centers,
                    y: t.histogram.counts,
                    marker: { color: BRAND.honey },
                  },
                ]}
                layout={{ bargap: 0.02 }}
              />
            ) : (
              <p className="text-sm text-ink-muted">No histogram available.</p>
            )}
          </Card>
        </div>
      )}
    </Section>
  );
}

function FeatureImportance({ profile }) {
  const fi = profile.feature_importance;
  const idLike = fi.filter((r) => r.id_like);
  const [hideIds, setHideIds] = useState(idLike.length > 0);

  const shown = hideIds ? fi.filter((r) => !r.id_like) : fi;
  const top = shown.slice(0, 20);

  if (!fi.length) return null;

  return (
    <Section
      title="Feature importance vs target"
      subtitle="Mutual information measures non-linear dependence. id-like columns (≥95% unique) usually shouldn't be features."
    >
      {idLike.length > 0 && (
        <Banner tone="warn">
          ⚠️ {idLike.length} identifier-like column(s):{" "}
          <span className="font-semibold">{idLike.map((r) => r.feature).join(", ")}</span>
        </Banner>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={hideIds}
          onChange={(e) => setHideIds(e.target.checked)}
          className="accent-honey"
        />
        Hide id-like columns from ranking
      </label>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <Plot
            height={Math.max(300, 24 * top.length)}
            data={[
              {
                type: "bar",
                orientation: "h",
                x: top.map((r) => r.mutual_info).reverse(),
                y: top.map((r) => r.feature).reverse(),
                marker: { color: BRAND.honey },
                hovertemplate: "%{y}: %{x}<extra></extra>",
              },
            ]}
            layout={{ margin: { l: 150, r: 16, t: 10, b: 30 } }}
          />
        </Card>
        <DataTable
          rows={shown}
          columns={["feature", "type", "unique", "mutual_info", "test", "statistic", "p_value"]}
          render={{ id_like: (v) => (v ? "yes" : "no") }}
          maxHeight={Math.max(300, 24 * top.length)}
        />
      </div>
    </Section>
  );
}

function NumericFeatures({ profile, selection, config }) {
  const ns = profile.numeric_stats;
  if (!ns.length)
    return (
      <Section title="Numeric features">
        <Banner>No numeric features detected.</Banner>
      </Section>
    );
  const cols = ns.map((r) => r.feature);
  return (
    <Section title="Numeric features">
      <DataTable rows={ns} />
      <h3 className="pt-2 text-sm font-bold text-ink">Distribution explorer</h3>
      <ColumnExplorer
        selection={selection}
        config={config}
        columns={cols}
        label="distribution"
      />
    </Section>
  );
}

function CategoricalFeatures({ profile, selection, config }) {
  const cs = profile.categorical_stats;
  if (!cs.length)
    return (
      <Section title="Categorical features">
        <Banner>No categorical features detected.</Banner>
      </Section>
    );
  const cols = cs.map((r) => r.feature);
  return (
    <Section title="Categorical features">
      <DataTable rows={cs} />
      <h3 className="pt-2 text-sm font-bold text-ink">Category explorer</h3>
      <ColumnExplorer
        selection={selection}
        config={config}
        columns={cols}
        label="categories"
      />
    </Section>
  );
}

function Missing({ profile }) {
  const ms = profile.missing_summary;
  const nz = ms.filter((r) => r.missing > 0);
  return (
    <Section title="Missing values">
      <DataTable rows={ms} />
      {nz.length > 0 && (
        <Card className="p-4">
          <Plot
            data={[
              {
                type: "bar",
                x: nz.map((r) => r.feature),
                y: nz.map((r) => r.missing_pct),
                marker: { color: BRAND.honey },
              },
            ]}
            layout={{ margin: { b: 100 }, xaxis: { tickangle: -40 } }}
          />
        </Card>
      )}
    </Section>
  );
}

function Correlations({ profile }) {
  const c = profile.correlations;
  if (!c) return null;
  return (
    <Section title="Numeric correlation matrix">
      <Card className="p-4">
        <Plot
          height={Math.max(380, 26 * c.labels.length)}
          data={[
            {
              type: "heatmap",
              z: c.z,
              x: c.labels,
              y: c.index,
              zmin: -1,
              zmax: 1,
              colorscale: "RdBu",
              reversescale: true,
            },
          ]}
          layout={{ margin: { l: 120, b: 120, t: 10, r: 16 }, xaxis: { tickangle: -40 } }}
        />
      </Card>
    </Section>
  );
}

function MlReady({ profile, selection, config }) {
  const ml = profile.ml_ready;
  const [out, setOut] = useState(ml.default_output);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [msg, setMsg] = useState(null);

  const payload = useMemo(
    () => ({ ...selection, ...config, output_table: out }),
    [selection, config, out]
  );

  async function save() {
    setSaving(true);
    setMsg(null);
    try {
      const r = await api.save(payload);
      setMsg({ tone: "ok", text: `✅ Wrote ${r.written} rows to ${r.output_table}` });
    } catch (e) {
      setMsg({ tone: "error", text: e.message });
    } finally {
      setSaving(false);
    }
  }

  function downloadCsv() {
    const rows = ml.rows;
    if (!rows.length) return;
    const cols = Object.keys(rows[0]);
    const esc = (v) =>
      v == null ? "" : `"${String(v).replace(/"/g, '""')}"`;
    const csv = [cols.join(",")]
      .concat(rows.map((r) => cols.map((c) => esc(r[c])).join(",")))
      .join("\n");
    downloadBlob(new Blob([csv], { type: "text/csv" }), `${selection.table}_ml_ready.csv`);
  }

  async function downloadExcel() {
    setExporting(true);
    try {
      const blob = await api.exportExcel({ ...selection, ...config });
      downloadBlob(blob, `${selection.table}_profile.xlsx`);
    } catch (e) {
      setMsg({ tone: "error", text: e.message });
    } finally {
      setExporting(false);
    }
  }

  return (
    <Section
      title="Save ML-ready profile"
      subtitle="One row per source column. kept = passes auto-exclusion filters; mutual_info scores predictive value vs target."
    >
      <div className="grid grid-cols-3 gap-3">
        <Metric label="Total columns" value={ml.total} />
        <Metric label="Kept as features" value={ml.kept} accent />
        <Metric label="Dropped / target" value={ml.dropped} />
      </div>

      <DataTable
        rows={ml.rows}
        render={{
          kept: (v) => <Badge tone={v ? "ok" : "neutral"}>{v ? "kept" : "dropped"}</Badge>,
          is_target: (v) => (v ? <Badge tone="target">target</Badge> : "—"),
        }}
      />

      <Card className="p-5">
        <div className="grid gap-4 md:grid-cols-[1fr_auto] md:items-end">
          <Field label="Output table (fully qualified)">
            <input
              value={out}
              onChange={(e) => setOut(e.target.value)}
              className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none focus:border-honey focus:ring-2 focus:ring-honey-100"
            />
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button onClick={save} disabled={saving}>
              {saving ? "Saving…" : "💾 Save to table"}
            </Button>
            <Button variant="ghost" onClick={downloadCsv}>
              CSV
            </Button>
            <Button variant="ghost" onClick={downloadExcel} disabled={exporting}>
              {exporting ? "…" : "Excel"}
            </Button>
          </div>
        </div>
        {(saving || exporting) && (
          <div className="mt-3">
            <Spinner label="Working…" />
          </div>
        )}
        {msg && (
          <div className="mt-3">
            <Banner tone={msg.tone}>{msg.text}</Banner>
          </div>
        )}
      </Card>
    </Section>
  );
}
