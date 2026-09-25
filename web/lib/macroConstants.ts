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

/**
 * Plotly draws its own canvas and never sees a Tailwind class, so the slate
 * ramp remap that themes the rest of the app cannot reach it -- the charts
 * stayed on a #0E1117 panel in the middle of a white page. These layouts are
 * the light equivalents, selected through layoutFor()/gridFor().
 *
 * The SERIES colours in COLORS below are deliberately NOT switched: they are
 * semantic (hike red, cut green, upper amber) and readable on both, and
 * changing them per theme would mean two palettes to keep honest.
 */
export const LIGHT_LAYOUT: Partial<Layout> = {
  paper_bgcolor: "#ffffff",
  plot_bgcolor: "#ffffff",
  font: { color: "#475569" },
  legend: { bgcolor: "rgba(0,0,0,0)", font: { size: 10 } },
  margin: { t: 30, b: 20, l: 0, r: 0 },
};

export const GRID_COLOR = "#1F2937";
export const ZERO_LINE_COLOR = "#4B5563";
export const GRID_COLOR_LIGHT = "#E2E8F0";
export const ZERO_LINE_COLOR_LIGHT = "#94A3B8";

export const layoutFor = (theme: string): Partial<Layout> =>
  theme === "light" ? LIGHT_LAYOUT : DARK_LAYOUT;
export const gridFor = (theme: string): string =>
  theme === "light" ? GRID_COLOR_LIGHT : GRID_COLOR;
export const zeroLineFor = (theme: string): string =>
  theme === "light" ? ZERO_LINE_COLOR_LIGHT : ZERO_LINE_COLOR;

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
