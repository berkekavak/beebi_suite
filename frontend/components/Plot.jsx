"use client";

import dynamic from "next/dynamic";
import { baseLayout, PLOT_CONFIG } from "@/lib/theme";

// Client-only Plotly — never server-rendered (static export has no server anyway).
const PlotlyClient = dynamic(() => import("./PlotlyClient"), {
  ssr: false,
  loading: () => (
    <div className="flex h-64 items-center justify-center text-sm text-ink-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-sand border-t-honey" />
    </div>
  ),
});

export default function Plot({ data, layout = {}, height = 320, style }) {
  return (
    <PlotlyClient
      data={data}
      layout={baseLayout({ height, ...layout })}
      config={PLOT_CONFIG}
      useResizeHandler
      style={{ width: "100%", height, ...style }}
    />
  );
}
