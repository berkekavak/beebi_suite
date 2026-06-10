"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import TablePicker from "@/components/profiler/TablePicker";
import Preview from "@/components/profiler/Preview";
import Results from "@/components/profiler/Results";

const STEPS = ["Pick table", "Preview & configure", "Results"];

export default function ProfilerPage() {
  const [step, setStep] = useState(0);
  const [selection, setSelection] = useState(null);
  const [data, setData] = useState(null); // /load response
  const [config, setConfig] = useState({ target: "", task: "classification", excluded: [] });
  const [profile, setProfile] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  function onLoaded({ selection, data }) {
    setSelection(selection);
    setData(data);
    const target = data.columns[0] || "";
    setConfig({
      target,
      task: data.inferred_task[target] || "classification",
      excluded: data.auto_exclude.map((a) => a.column),
    });
    setProfile(null);
    setStep(1);
  }

  async function runProfile() {
    setRunning(true);
    setError("");
    try {
      const result = await api.profile({ ...selection, ...config });
      setProfile(result);
      setStep(2);
    } catch (e) {
      setError(e.message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <Header step={step} setStep={setStep} hasData={!!data} hasProfile={!!profile} />

      {step === 0 && <TablePicker onLoaded={onLoaded} />}
      {step === 1 && data && (
        <Preview
          selection={selection}
          data={data}
          config={config}
          setConfig={setConfig}
          onRun={runProfile}
          running={running}
          error={error}
        />
      )}
      {step === 2 && profile && (
        <Results profile={profile} selection={selection} config={config} />
      )}
    </div>
  );
}

function Header({ step, setStep, hasData, hasProfile }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">Data Profiler</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Profile a Unity Catalog table and export an ML-ready feature summary.
        </p>
      </div>
      <ol className="flex items-center gap-2 text-sm">
        {STEPS.map((label, i) => {
          const reachable = i === 0 || (i === 1 && hasData) || (i === 2 && hasProfile);
          const active = i === step;
          return (
            <li key={label} className="flex items-center gap-2">
              <button
                disabled={!reachable}
                onClick={() => reachable && setStep(i)}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 font-medium transition ${
                  active
                    ? "bg-ink text-white"
                    : reachable
                      ? "text-ink hover:bg-sand"
                      : "cursor-not-allowed text-ink-muted/50"
                }`}
              >
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full text-[11px] font-bold ${
                    active ? "bg-honey text-ink" : "bg-sand text-ink-muted"
                  }`}
                >
                  {i + 1}
                </span>
                {label}
              </button>
              {i < STEPS.length - 1 && <span className="text-ink-muted/40">→</span>}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
