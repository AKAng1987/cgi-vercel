/**
 * Pure helpers for the TAPE views (heatmap, movers, ladder, rotation, stretch).
 * No React and no fetching: everything is computed from the rows /api/live already returns, and every function
 * returns null when an input is missing -- a gap is shown as a gap, never filled.
 */
import { HudGroup, HudTicker } from "@/lib/types";

export type HKey = "pct_1d" | "pct_5d" | "pct_1m" | "pct_3m" | "pct_6m" | "pct_1y";

/** Trading days in each window; `cap` is the move (in %) that fills a heatmap tile completely. */
export const HORIZONS: { key: HKey; label: string; days: number; cap: number }[] = [
  { key: "pct_1d", label: "1D", days: 1, cap: 2 },
  { key: "pct_5d", label: "5D", days: 5, cap: 4 },
  { key: "pct_1m", label: "1M", days: 21, cap: 8 },
  { key: "pct_3m", label: "3M", days: 63, cap: 15 },
  { key: "pct_6m", label: "6M", days: 126, cap: 25 },
  { key: "pct_1y", label: "1Y", days: 252, cap: 40 },
];

export const num = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

export function newestClose(groups: HudGroup[]): string {
  return groups.flatMap((g) => g.tickers.map((t) => t.as_of ?? "")).reduce((a, b) => (b > a ? b : a), "");
}

/**
 * The close date most rows share (ties go to the newer date). The new views measure "stale" against THIS, not the
 * newest date any row has: feeds do not all publish at once (2026-10-28: FX and the VIX were already at the 28th while
 * 166 ETFs were still at the 27th), and against the newest date nearly the whole universe would read as stale.
 * The table keeps its stricter per-row "as of" tag.
 */
export function commonClose(groups: HudGroup[]): string {
  const count = new Map<string, number>();
  for (const g of groups) for (const t of g.tickers) if (t.as_of) count.set(t.as_of, (count.get(t.as_of) ?? 0) + 1);
  let best = "", bestN = 0;
  for (const [d, n] of count) if (n > bestN || (n === bestN && d > best)) { best = d; bestN = n; }
  return best;
}

/** A row whose newest close is older than the newest any row has. Same rule the table uses for its "as of" tag. */
export function isStale(t: HudTicker, latest: string): boolean {
  return !!(latest && t.as_of && t.as_of < latest);
}

/** Return of `t` minus the return of the benchmark row over the same window (percentage points). */
export function relStrength(t: HudTicker, bench: HudTicker | undefined, key: HKey): number | null {
  if (!bench) return null;
  const a = t[key], b = bench[key];
  return num(a) && num(b) ? a - b : null;
}

/** Price against its 7-day EMA, in 7-day standard deviations of price. Null when the spread is missing or zero. */
export function stretchZ(t: HudTicker): number | null {
  const { current, ema_7d, sd_7d } = t;
  if (!num(current) || !num(ema_7d) || !num(sd_7d) || sd_7d <= 0) return null;
  const z = (current - ema_7d) / sd_7d;
  // With one consistent unit, a value over 7 closes cannot sit more than about 2.5 standard deviations from their
  // average. A bigger number means the row's spread came in another unit (seen 2026-10-28 on RUT, USDKRW, USDIDR,
  // BTC and ETH, which carry workbook values): show a gap, not a made-up reading.
  return Math.abs(z) > 4 ? null : z;
}

export function mean(xs: (number | null)[]): number | null {
  const v = xs.filter(num);
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null;
}

/** Share of a group's rows with a positive return over the window, among rows that have one. */
export function breadthUp(rows: HudTicker[], key: HKey): number | null {
  const v = rows.map((r) => r[key]).filter(num);
  return v.length ? v.filter((x) => x > 0).length / v.length : null;
}

/** Return per trading day for each window, so a longer window is not simply a bigger number. */
export function paces(t: HudTicker): (number | null)[] {
  return HORIZONS.map((h) => (num(t[h.key]) ? t[h.key]! / h.days : null));
}

export type LadderState = "speeding up" | "fading" | "mixed" | "n/a";

/** Compares the pace over 1M, 3M and 6M: strictly growing in size with the same sign = speeding up; shrinking = fading. */
export function ladderState(t: HudTicker): LadderState {
  const p = paces(t);
  const [m1, m3, m6] = [p[2], p[3], p[4]];
  if (!num(m1) || !num(m3) || !num(m6)) return "n/a";
  const same = Math.sign(m1) === Math.sign(m3) && Math.sign(m3) === Math.sign(m6) && m1 !== 0;
  if (!same) return "mixed";
  if (Math.abs(m1) > Math.abs(m3) && Math.abs(m3) > Math.abs(m6)) return "speeding up";
  if (Math.abs(m1) < Math.abs(m3) && Math.abs(m3) < Math.abs(m6)) return "fading";
  return "mixed";
}

export type Quadrant = "leading" | "weakening" | "improving" | "lagging";

/** x = 3M relative return, y = 1M relative return. Leading: both above the benchmark; weakening: 3M above, 1M below; etc. */
export function quadrant(x: number, y: number): Quadrant {
  if (x >= 0 && y >= 0) return "leading";
  if (x >= 0 && y < 0) return "weakening";
  if (x < 0 && y >= 0) return "improving";
  return "lagging";
}

/** Fraction of full colour (0..1) for a return, on the horizon's fixed scale. */
export function tileStrength(v: number | null, key: HKey): number {
  if (!num(v)) return 0;
  const cap = HORIZONS.find((h) => h.key === key)?.cap ?? 5;
  return Math.min(1, Math.abs(v) / cap);
}

/** CSS colour for a heatmap tile from the theme's up/down tokens, so light and dark themes both work. */
export function tileColor(v: number | null, key: HKey): string {
  if (!num(v)) return "var(--cgi-surface-alt)";
  const s = Math.round(tileStrength(v, key) * 70);
  const tok = v >= 0 ? "var(--cgi-up)" : "var(--cgi-down)";
  return `color-mix(in srgb, ${tok} ${s}%, var(--cgi-surface-alt))`;
}

/** Groups whose returns are returns on a price (not a percent change in a yield or a spread). */
export function isPriceGroup(g: HudGroup): boolean {
  return g.default_rs_denom != null;
}

export function benchmarkRow(groups: HudGroup[], symbol: string | null | undefined): HudTicker | undefined {
  if (!symbol) return undefined;
  for (const g of groups) for (const t of g.tickers) if (t.symbol === symbol) return t;
  return undefined;
}
