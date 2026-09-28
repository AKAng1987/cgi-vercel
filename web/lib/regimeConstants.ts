/**
 * Ported from ~/market-dashboard/app.py (COMPASS_Q_MAP / GRID_Q_MAP /
 * _dir_color, lines ~30-49 and ~648-651). Quadrant->arrow lookups are
 * static tables keyed by quadrant number, not derived from metric values.
 */
export const COMPASS_Q_MAP: Record<number, [string, string]> = {
  1: ["↑", "↓"],
  2: ["↑", "↑"],
  3: ["↓", "↑"],
  4: ["↓", "↓"],
};

export const GRID_Q_MAP: Record<number, [string, string]> = COMPASS_Q_MAP;

type Axis = "liquidity" | "credit" | "growth" | "inflation";

export function dirColor(arrow: string, axis: Axis): string {
  // CSS variables, not literals: a literal cannot be themed, and these are
  // the largest text on the regime card. #00C851 measures ~2.2:1 on white.
  if (axis === "inflation") return arrow === "↑" ? "var(--cgi-warn)" : "var(--cgi-up)";
  if (axis === "credit") return arrow === "↑" ? "var(--cgi-up)" : "var(--cgi-warn)";
  return arrow === "↑" ? "var(--cgi-up)" : "var(--cgi-down)";
}

/**
 * Streamlit's render_compass_box/render_grid_box (app.py:546-620) do NOT
 * show raw sheet labels ("DFEDTARU", "Growth / GDP") — they hardcode
 * "Fed Funds" / "SLOS" and "GDP" / "CPI" for the first two metrics in
 * each block. Mirrored exactly here per the approved decision to match
 * Streamlit's real display labels rather than the illustrative examples
 * in the original spec.
 */
export const COMPASS_LABEL_MAP: Record<string, string> = {
  DFEDTARU: "Fed Funds",
  DRTSCILM: "SLOS",
};

export const GRID_LABEL_MAP: Record<string, string> = {
  "Growth / GDP": "GDP",
  "Inflation Rate": "CPI",
};

export function compassLabel(key: string): string {
  return COMPASS_LABEL_MAP[key] ?? key;
}

export function gridLabel(key: string): string {
  return GRID_LABEL_MAP[key] ?? key;
}

/**
 * HUD table column set + order, matching Streamlit's DISPLAY_TF
 * (app.py:27) exactly -- notably no 7D% column, even though the API
 * carries pct_7d (parsed but never rendered in the existing UI either).
 */
export const HUD_DISPLAY_COLUMNS = [
  { key: "pct_1d", label: "1D%" },
  { key: "pct_5d", label: "5D%" },
  { key: "pct_1m", label: "1M%" },
  { key: "pct_3m", label: "3M%" },
  { key: "pct_6m", label: "6M%" },
  { key: "pct_1y", label: "1Y%" },
] as const;

export function pctColor(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "var(--cgi-null)";
  if (v > 0) return "var(--cgi-up)";
  if (v < 0) return "var(--cgi-down)";
  return "var(--cgi-neutral)";
}

/**
 * BACKTEST tab quadrant labels, ported verbatim from app.py's
 * GRID_Q_LABELS / COMPASS_Q_LABELS (lines 36-47). Kept as full labels
 * (not just "C2" / "G4") because the Streamlit tab uses these directly
 * in the info line "Regime {compass} × {grid} has occurred N times".
 */
export const GRID_Q_LABELS: Record<number, string> = {
  1: "G1 — Goldilocks",
  2: "G2 — Reflation",
  3: "G3 — Inflation",
  4: "G4 — Deflation",
};

export const COMPASS_Q_LABELS: Record<number, string> = {
  1: "C1 — Liquidity↑ Credit↓",
  2: "C2 — Liquidity↑ Credit↑",
  3: "C3 — Liquidity↓ Credit↑",
  4: "C4 — Liquidity↓ Credit↓",
};
