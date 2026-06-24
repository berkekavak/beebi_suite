"use client";

import { useState } from "react";
import DemandForecasting from "@/components/monitor/DemandForecasting";
import ComingSoon from "@/components/monitor/ComingSoon";

const TABS = [
  { id: "demand", label: "Demand Forecasting", ready: true },
  { id: "elasticity", label: "Price Elasticity", ready: false },
  { id: "mdo", label: "MDO", ready: false },
];

export default function MonitorPage() {
  const [tab, setTab] = useState("demand");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">Model Monitor</h1>
        <p className="mt-1 text-sm text-ink-muted">
          Run your Databricks jobs and inspect the tables they produce.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-b border-line">
        {TABS.map((t) => {
          const active = t.id === tab;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`relative -mb-px rounded-t-lg px-4 py-2 text-sm font-semibold transition ${
                active
                  ? "border-b-2 border-honey text-ink"
                  : "text-ink-muted hover:text-ink"
              }`}
            >
              {t.label}
              {!t.ready && (
                <span className="ml-2 rounded-md bg-sand px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-ink-muted">
                  soon
                </span>
              )}
            </button>
          );
        })}
      </div>

      {tab === "demand" && <DemandForecasting />}
      {tab === "elasticity" && (
        <ComingSoon
          title="Price Elasticity"
          desc="Elasticity modelling and what-if pricing analysis. Coming soon."
        />
      )}
      {tab === "mdo" && (
        <ComingSoon
          title="MDO"
          desc="Marketing & demand optimization monitoring. Coming soon."
        />
      )}
    </div>
  );
}
