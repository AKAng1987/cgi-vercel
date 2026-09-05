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

export interface FomcProbabilityRow {
  date: string;
  ticker: string;
  implied_avg: number;
  pre_rate: number;
  post_rate: number;
  p_cut: number;
  p_hold: number;
  p_hike: number;
  most_likely: string;
  prob_most_likely: number;
}

export interface FomcProbabilities {
  upper_target: number;
  lower_target: number;
  effr_latest: number;
  probabilities: FomcProbabilityRow[];
}

export interface TreasuryCurvePoint {
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

export interface SpreadPoint {
  date: string;
  T10Y2Y: number | null;
  HY_Spread: number | null;
}

export interface RatesResponse {
  fed_funds_range: FedFundsPoint[];
  fomc_meeting_calendar: FomcMeeting[];
  fomc_probabilities: FomcProbabilities;
  treasury_curve: TreasuryCurvePoint[];
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
  gdp: GdpBlock;
  gdp_nowcast: GdpNowcastPoint[];
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
