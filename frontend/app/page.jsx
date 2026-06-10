"use client";

import Link from "next/link";
import Logo from "@/components/Logo";
import { Card } from "@/components/ui";

const TOOLS = [
  {
    href: "/profiler/",
    title: "Data Profiler",
    desc: "Profile any Unity Catalog table against a target, surface feature importance, and export an ML-ready summary.",
    icon: "📊",
    ready: true,
  },
  {
    title: "Data Quality",
    desc: "Rule-based and statistical checks with drift alerts on Delta tables.",
    icon: "✓",
    ready: false,
  },
  {
    title: "Feature Store",
    desc: "Curate, version and serve engineered features across teams.",
    icon: "⬡",
    ready: false,
  },
  {
    title: "Model Monitor",
    desc: "Track production model performance and data drift over time.",
    icon: "◷",
    ready: false,
  },
];

export default function Dashboard() {
  return (
    <div className="space-y-8">
      <div className="honeycomb relative overflow-hidden rounded-xl2 px-8 py-10 text-white">
        <div className="relative z-10 max-w-2xl">
          <Logo width={150} tagline={false} />
          <h1 className="mt-5 text-3xl font-extrabold tracking-tight lg:text-4xl">
            We keep touching the intelligence.
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-white/70">
            A growing toolkit that runs natively on your Databricks workspace —
            profiling, quality, features and monitoring, all in one place.
          </p>
          <Link
            href="/profiler/"
            className="mt-6 inline-flex items-center gap-2 rounded-lg bg-honey px-5 py-2.5 text-sm font-bold text-ink shadow-glow transition hover:bg-honey-600 hover:text-white"
          >
            Open Data Profiler →
          </Link>
        </div>
      </div>

      <div>
        <h2 className="mb-4 text-lg font-bold tracking-tight">Tools</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {TOOLS.map((t) => {
            const inner = (
              <Card
                className={`h-full p-5 transition ${
                  t.ready
                    ? "hover:-translate-y-0.5 hover:shadow-glow"
                    : "opacity-60"
                }`}
              >
                <div className="flex items-start justify-between">
                  <span className="text-2xl">{t.icon}</span>
                  {!t.ready && (
                    <span className="rounded-md bg-sand px-2 py-0.5 text-[10px] font-semibold uppercase text-ink-muted">
                      Coming soon
                    </span>
                  )}
                </div>
                <h3 className="mt-3 font-bold text-ink">{t.title}</h3>
                <p className="mt-1 text-sm text-ink-muted">{t.desc}</p>
              </Card>
            );
            return t.ready ? (
              <Link key={t.title} href={t.href}>
                {inner}
              </Link>
            ) : (
              <div key={t.title}>{inner}</div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
