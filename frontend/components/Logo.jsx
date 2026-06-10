"use client";

// Official BeeBI wordmark (yellow on transparent) — looks best on dark surfaces.
export default function Logo({ width = 132, tagline = true }) {
  return (
    <div className="space-y-1.5">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/beebi-logo.png"
        alt="BeeBI"
        width={width}
        style={{ width, height: "auto" }}
        className="block select-none"
      />
      {tagline && (
        <div className="pl-0.5 text-[10px] font-medium uppercase tracking-[0.18em] text-white/45">
          Intelligence Suite
        </div>
      )}
    </div>
  );
}
