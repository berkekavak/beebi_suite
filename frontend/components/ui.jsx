"use client";

// Small set of branded, reusable UI primitives.

export function Card({ children, className = "" }) {
  return (
    <div
      className={`rounded-xl2 border border-line bg-white shadow-card ${className}`}
    >
      {children}
    </div>
  );
}

export function Section({ title, subtitle, right, children, className = "" }) {
  return (
    <section className={`space-y-4 ${className}`}>
      {(title || right) && (
        <div className="flex items-end justify-between gap-4">
          <div>
            {title && (
              <h2 className="text-lg font-bold tracking-tight text-ink">{title}</h2>
            )}
            {subtitle && (
              <p className="mt-0.5 max-w-2xl text-sm text-ink-muted">{subtitle}</p>
            )}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export function Metric({ label, value, accent = false }) {
  return (
    <Card className={`px-4 py-3 ${accent ? "border-l-4 border-l-honey" : ""}`}>
      <div className="text-xs font-medium uppercase tracking-wide text-ink-muted">
        {label}
      </div>
      <div className="mt-1 text-2xl font-extrabold tabular-nums text-ink">
        {value}
      </div>
    </Card>
  );
}

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled = false,
  className = "",
  type = "button",
}) {
  const styles = {
    primary:
      "bg-honey text-ink hover:bg-honey-600 shadow-glow disabled:shadow-none",
    ghost: "bg-transparent text-ink hover:bg-sand border border-line",
    dark: "bg-ink text-white hover:bg-ink-soft",
  };
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Badge({ children, tone = "neutral" }) {
  const tones = {
    neutral: "bg-sand text-ink-muted",
    target: "bg-honey-100 text-honey-700",
    danger: "bg-red-100 text-red-700",
    warn: "bg-amber-100 text-amber-800",
    ok: "bg-emerald-100 text-emerald-700",
  };
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold ${
        tones[tone] || tones.neutral
      }`}
    >
      {children}
    </span>
  );
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-semibold text-ink">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-ink-muted">{hint}</span>}
    </label>
  );
}

export function Select({ value, onChange, options, disabled = false }) {
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      disabled={disabled}
      className="w-full rounded-lg border border-line bg-white px-3 py-2 text-sm outline-none transition focus:border-honey focus:ring-2 focus:ring-honey-100 disabled:bg-sand/50"
    >
      {options.map((o) => {
        const val = typeof o === "string" ? o : o.value;
        const lab = typeof o === "string" ? o : o.label;
        return (
          <option key={val} value={val}>
            {lab}
          </option>
        );
      })}
    </select>
  );
}

export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-3 text-sm text-ink-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-sand border-t-honey" />
      {label}
    </div>
  );
}

export function Banner({ tone = "info", children }) {
  const tones = {
    info: "border-line bg-white text-ink",
    error: "border-red-200 bg-red-50 text-red-800",
    ok: "border-emerald-200 bg-emerald-50 text-emerald-800",
    warn: "border-amber-200 bg-amber-50 text-amber-900",
  };
  return (
    <div className={`rounded-lg border px-4 py-3 text-sm ${tones[tone]}`}>
      {children}
    </div>
  );
}

// Generic data table from an array of row objects.
export function DataTable({ rows, columns, render = {}, maxHeight = 460 }) {
  if (!rows || rows.length === 0) {
    return <p className="text-sm text-ink-muted">No data.</p>;
  }
  const cols = columns || Object.keys(rows[0]);
  return (
    <div className="table-scroll rounded-xl2 border border-line" style={{ maxHeight }}>
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-ink text-left text-white">
          <tr>
            {cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-3 py-2 font-semibold">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              className={i % 2 ? "bg-cream/60" : "bg-white"}
            >
              {cols.map((c) => (
                <td key={c} className="whitespace-nowrap px-3 py-1.5 tabular-nums">
                  {render[c] ? render[c](r[c], r) : formatCell(r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function formatCell(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") {
    if (Number.isInteger(v)) return v.toLocaleString();
    return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  if (typeof v === "boolean") return v ? "✓" : "✗";
  return String(v);
}
