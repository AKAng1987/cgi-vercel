import { MarkovAxis, RegimeBlock } from "@/lib/types";
import { COMPASS_Q_MAP, GRID_Q_MAP, compassLabel, gridLabel, dirColor } from "@/lib/regimeConstants";

/**
 * Everything the regime card SAYS, with no markup: the words, arrows, colours (still CSS variables) and the
 * formatted readings. The page card (components/RegimeCard.tsx) and the picture posted to CTS
 * (app/share/regime.png) both render from this, so the two cannot drift apart: change a word here and both change.
 */
export interface StatView {
  label: string;
  value: number | string | null;
  ref: number | string | null | undefined;
  pct: string;
  asOf: string | null | undefined;
}

export interface AxisView {
  label: string;
  arrow: string;
  word: string;
  color: string;
}

export interface RegimeView {
  title: string;
  regimeLabel: string;
  staleNote: string | null;
  axes: [AxisView, AxisView];
  stats: StatView[];
  since: string | null;
}

/**
 * The ONE place the words for an axis state live. "up" is the arrow ↑: Easing for the Compass axes (liquidity,
 * credit), Rising for the Grid axes (growth, inflation). The regime card and the "What moves each axis" panel both
 * read from here, so an axis cannot be described in two vocabularies.
 */
const COMPASS_AXES: ReadonlySet<MarkovAxis> = new Set<MarkovAxis>(["liquidity", "credit"]);
export function stateWord(axis: MarkovAxis, up: boolean): string {
  if (COMPASS_AXES.has(axis)) return up ? "Easing" : "Tightening";
  return up ? "Rising" : "Falling";
}
/** Where an axis goes when it flips: the opposite of its current state, with the arrow. */
export function flipTo(axis: MarkovAxis, currentUp: boolean): { arrow: string; word: string } {
  return { arrow: currentUp ? "↓" : "↑", word: stateWord(axis, !currentUp) };
}

export function regimeView(kind: "compass" | "grid", data: RegimeBlock): RegimeView {
  const isCompass = kind === "compass";
  const qMap = isCompass ? COMPASS_Q_MAP : GRID_Q_MAP;
  const [arr1, arr2] = data.quadrant ? qMap[data.quadrant] ?? ["?", "?"] : ["?", "?"];
  const word = (axis: MarkovAxis, arr: string) => stateWord(axis, arr === "↑");
  const label = (k: string) => (isCompass ? compassLabel(k) : gridLabel(k));

  return {
    title: isCompass ? "COMPASS — Liquidity / Credit" : "GRID — Growth / Inflation",
    regimeLabel: data.label,
    staleNote: data.stale_note ?? null,
    axes: [
      { label: isCompass ? "LIQUIDITY" : "GROWTH", arrow: arr1, word: word(isCompass ? "liquidity" : "growth", arr1),
        color: dirColor(arr1, isCompass ? "liquidity" : "growth") },
      { label: isCompass ? "CREDIT" : "INFLATION", arrow: arr2, word: word(isCompass ? "credit" : "inflation", arr2),
        color: dirColor(arr2, isCompass ? "credit" : "inflation") },
    ],
    stats: Object.entries(data.metrics).map(([key, m]) => ({
      label: label(key),
      value: m.current_value,
      ref: "reference_value" in m ? m.reference_value : m.previous_value,
      pct: m.pct_change === null || m.pct_change === undefined
        ? "—"
        : `${m.pct_change >= 0 ? "+" : ""}${m.pct_change.toFixed(2)}%`,
      asOf: m.current_date ?? m.release_date,
    })),
    since: data.since,
  };
}
