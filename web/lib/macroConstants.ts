/**
 * Ported from ~/market-dashboard/app.py's MACRO tab block (_DARK dict,
 * app.py:2087-2093, and the per-panel color choices scattered through
 * the ~680-line MACRO block, app.py:2086-2765). Kept as one place so
 * every macro chart matches Streamlit's palette exactly rather than
 * each component picking its own colors.
 */
import type { Layout } from "plotly.js";

export const DARK_LAYOUT: Partial<Layout> = {
  paper_bgcolor: "#0E1117",
  plot_bgcolor: "#0E1117",
  font: { color: "#9CA3AF" },
  legend: { bgcolor: "rgba(0,0,0,0)", font: { size: 10 } },
  margin: { t: 30, b: 20, l: 0, r: 0 },
};

export const GRID_COLOR = "#1F2937";
export const ZERO_LINE_COLOR = "#4B5563";

export const COLORS = {
  upper: "#F59E0B",
  lower: "#60A5FA",
  hike: "#EF4444",
  hold: "#6B7280",
  cut: "#22C55E",
  cpi: "#60A5FA",
  coreCpi: "#34D399",
  ppi: "#F87171",
  pce: "#A78BFA",
  t10y2y: "#60A5FA",
  hySpread: "#F87171",
  gdpBarNeg: "#EF4444",
  gdpBarPos: "#22C55E",
  gdpNow: "#22d3ee",
  gdpNow3c: "#F59E0B",
  gdpNowFinalDiamond: "#fbbf24",
  vintageAdvance: "#60A5FA",
  vintageSecond: "#F59E0B",
  vintageThird: "#A78BFA",
};

export const DOT_PLOT_COLORS: Record<string, string> = {
  "2026": "#60A5FA",
  "2027": "#34D399",
  "2028": "#F59E0B",
  LR: "#A78BFA",
};

export const DOT_PLOT_LABELS: Record<string, string> = {
  "2026": "End-2026",
  "2027": "End-2027",
  "2028": "End-2028",
  LR: "Longer Run",
};

export const DOT_PLOT_HORIZON_ORDER = ["2026", "2027", "2028", "LR"];
