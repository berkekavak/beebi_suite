"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import Logo from "./Logo";

// The product is a suite — the profiler is tool #1. New tools slot in here as
// their own nav entries (and their own backend router + frontend route).
const NAV = [
  { href: "/", label: "Dashboard", icon: "◆", ready: true },
  { href: "/profiler/", label: "Data Profiler", icon: "📊", ready: true },
  { href: "#", label: "Data Quality", icon: "✓", ready: false },
  { href: "#", label: "Feature Store", icon: "⬡", ready: false },
  { href: "#", label: "Model Monitor", icon: "◷", ready: false },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="honeycomb flex h-full w-60 flex-col justify-between p-4">
      <div>
        <div className="px-2 py-3">
          <Logo />
        </div>

        <nav className="mt-6 space-y-1">
          {NAV.map((item) => {
            const active =
              item.ready &&
              (item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href.replace(/\/$/, "")));
            if (!item.ready) {
              return (
                <div
                  key={item.label}
                  className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-white/35"
                >
                  <span className="flex items-center gap-2.5">
                    <span className="w-4 text-center">{item.icon}</span>
                    {item.label}
                  </span>
                  <span className="text-[9px] uppercase tracking-wide text-white/25">
                    soon
                  </span>
                </div>
              );
            }
            return (
              <Link
                key={item.label}
                href={item.href}
                className={`flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  active
                    ? "bg-honey text-ink shadow-glow"
                    : "text-white/70 hover:bg-white/10 hover:text-white"
                }`}
              >
                <span className="w-4 text-center">{item.icon}</span>
                {item.label}
              </Link>
            );
          })}
        </nav>
      </div>

      <div className="rounded-lg border border-white/10 bg-white/5 p-3">
        <p className="text-[11px] leading-relaxed text-white/55">
          We keep touching the intelligence.
        </p>
        <p className="mt-2 text-[10px] text-white/30">BeeBI Consulting · Databricks</p>
      </div>
    </aside>
  );
}
