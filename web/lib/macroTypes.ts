/**
 * Response shapes for /api/macro/rates, /api/macro/growth,
 * /api/macro/dot-plot — confirmed against live production responses
 * on 2026-09-06 (not guessed from the spec's illustrative examples).
 * Backend returns raw data (PHASE2_PLAN.md decision #5) — no fig.to_dict(),
 * charts are built client-side from these shapes.
 */

export interface FedFundsPoint {
  date: string;
  upper: number;
  lower: number;
}

export interface FomcMeeting {
  date: string;
}

export interface FomcBucket {
  /** Whole 25bp steps from the rate expected going INTO this meeting.
   *  0 = hold, +1 = one hike, -2 = two cuts. */
  steps: number;
  prob: number;
  label: string;
}

/** A meeting whose pricing contract could not be read. Returned rather than
 *  dropped, so a missing quote shows as a gap instead of a shorter table. */
export interface FomcUnavailableRow {
  date: string;
  ticker: string;
  available: false;
  reason: string;
  method: string | null;
  lever: number | null;
  base_rate: number;
}

export interface FomcPricedRow {
  date: string;
  ticker: string;
  available: true;
  /** "next_month" = read straight off the following contract, whose whole
   *  month is post-meeting. "de_average" = split out of this month's. */
  method: "next_month" | "de_average";
  /** How much the quote is magnified to get post_rate. 1.0 under next_month. */
  lever: number;
  /** The lever this meeting's OWN month would have required, kept so the
   *  page can say what was avoided. */
  own_lever: number;
  confident: boolean;
  implied_avg: number;
  /** The target midpoint expected going INTO this meeting, on the 25bp grid. */
  base_rate: number;
  pre_rate: number;
  post_rate: number;
  buckets: FomcBucket[];
  p_cut: number;
  p_hold: number;
  p_hike: number;
  most_likely: string;
  prob_most_likely: number;
}

export type FomcProbabilityRow = FomcPricedRow | FomcUnavailableRow;

export interface FomcProbabilities {
  upper_target: number;
  lower_target: number;
  effr_latest: number;
  probabilities: FomcProbabilityRow[];
}

export interface TreasuryCurveSnapshotRow {
  label: "Latest" | "6M Ago" | "1Y Ago";
  date: string;
  "1M"?: number | null;
  "3M"?: number | null;
  "1Y"?: number | null;
  "2Y"?: number | null;
  "3Y"?: number | null;
  "5Y"?: number | null;
  "7Y"?: number | null;
  "10Y"?: number | null;
  "20Y"?: number | null;
  "30Y"?: number | null;
}

export interface TreasuryCurveHistoryPoint {
  date: string;
  value: number;
}

/**
 * Trimmed at the API layer (2026-09-07, Task 1b) -- backend only ships
 * the 3 snapshot rows + 10Y history line that YieldCurvePanel.tsx
 * actually renders, not the full 20-year x 10-tenor wide table. See
 * api/macro_data.py's _trim_treasury_curve.
 */
export interface TreasuryCurveResponse {
  snapshot: TreasuryCurveSnapshotRow[];
  history_10y: TreasuryCurveHistoryPoint[];
}

export interface SpreadPoint {
  date: string;
  T10Y2Y: number | null;
  HY_Spread: number | null;
}

export interface RatesResponse {
  fed_funds_range: FedFundsPoint[];
  fomc_meeting_calendar: FomcMeeting[];
  fomc_probabilities: FomcProbabilities;
  treasury_curve: TreasuryCurveResponse;
  spreads: SpreadPoint[];
}

export interface LendingStandardPoint {
  date: string;
  value: number;
}

export interface GdpQuarterlyPoint {
  date: string;
  gdp_pct: number;
}

export interface GdpVintageRow {
  quarter: string;
  vintage: "Advance" | "Second" | "Third";
  value: number;
  release_date: string;
  days_after_qend: number;
}

export interface GdpBlock {
  quarterly: GdpQuarterlyPoint[];
  vintages: GdpVintageRow[];
}

export interface GdpNowcastPoint {
  date: string;
  gdpnow: number;
}

export interface InflationPoint {
  date: string;
  CPI: number | null;
  "Core CPI": number | null;
  PPI: number | null;
}

export interface PcePoint {
  date: string;
  pce_core_yoy: number | null;
}

export interface GrowthResponse {
  lending_standards: LendingStandardPoint[];
  challenger: LendingStandardPoint[]; // {date, value} in thousands
  gdp: GdpBlock;
  gdp_nowcast: GdpNowcastPoint[];
  gdp_nowcast_freshness?: GdpNowcastFreshness;
  inflation: InflationPoint[];
  pce: PcePoint[];
}

export interface DotPlotRow {
  year: string; // "2026" | "2027" | "2028" | "LR"
  participant_id: number;
  projected_rate: number;
}

export interface DotPlotResponse {
  dot_plot: DotPlotRow[];
}

/** Whether GDPNow is still being REVISED -- which is a different question
 *  from how its rows are dated. Its newest row is dated to the start of the
 *  quarter being nowcast, so it is always months "old" by date while being
 *  days old in fact. Judging it by the date column would blank a healthy
 *  series for most of every quarter. */
export interface GdpNowcastFreshness {
  available: boolean;
  why?: string;
  last_updated?: string;
  newest_observation?: string | null;
  stale?: boolean;
  age_days?: number;
  cadence?: string;
  expected_every_days?: number;
  stale_after_days?: number;
  reason?: string;
  note?: string;
}
