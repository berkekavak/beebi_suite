// Shared brand tokens for Plotly charts so every figure matches the BeeBI look.

export const BRAND = {
  honey: "#FADB49",
  honeyDark: "#EFC820",
  ink: "#1A1714",
  inkMuted: "#6B6256",
  sand: "#EFE7DA",
  line: "#E7DDCB",
};

// Honey-forward categorical palette
export const COLORWAY = [
  "#FADB49",
  "#1A1714",
  "#EFC820",
  "#B08F00",
  "#8A7A5C",
  "#D9B36A",
  "#C9A30C",
  "#403628",
];

export function baseLayout(overrides = {}) {
  return {
    font: { family: "Inter, system-ui, sans-serif", color: BRAND.ink, size: 12 },
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    colorway: COLORWAY,
    margin: { l: 48, r: 16, t: 36, b: 40 },
    xaxis: { gridcolor: BRAND.sand, zerolinecolor: BRAND.line },
    yaxis: { gridcolor: BRAND.sand, zerolinecolor: BRAND.line },
    legend: { orientation: "h", y: -0.2 },
    ...overrides,
  };
}

export const PLOT_CONFIG = { displayModeBar: false, responsive: true };
