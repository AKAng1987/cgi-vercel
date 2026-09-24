export interface CompassGridMetric {
  reference_date?: string | null;
  reference_value?: number | string | null;
  release_date?: string | null;
  current_date?: string | null;
  previous_value?: number | string | null;
  current_value: number | string | null;
  pct_change: number | null;
}

export interface RegimeBlock {
  quadrant: number | null;
  label: string;
  since: string | null;
  stale_note?: string | null;
  metrics: Record<string, CompassGridMetric>;
}

export interface HudTicker {
  symbol: string;
  sector: string;
  current: number | null;
  ema_7d: number | null;
  sd_7d: number | null;
  pct_1d: number | null;
  pct_5d: number | null;
  pct_7d: number | null;
  pct_1m: number | null;
  pct_3m: number | null;
  pct_6m: number | null;
  pct_1y: number | null;
  as_of: string | null;
  stale_days: number | null;
}

export interface HudGroup {
  name: string;
  default_rs_denom: string | null;
  tickers: HudTicker[];
}

export interface LiveResponse {
  as_of: string;
  generated_at: string;
  compass: RegimeBlock;
  grid: RegimeBlock;
  hud_groups: HudGroup[];
  hud_group_order: string[];
}

export interface BacktestRow {
  ticker: string;
  group: string;
  occurrences: number;
  avg_high_pct: number;
  avg_low_pct: number;
  hit_rate: number;
  edge: number | null;
  avg_return_pct: number;
}

export interface BacktestTableResponse {
  schema_version: number;
  last_refreshed_at: string | null;
  compass_q: number;
  grid_q: number;
  min_occ: number;
  lookback: string;
  from_combo?: string;
  from_counts?: Record<string, number>; // "C2G3" -> distinct regime windows entered from there
  rows: BacktestRow[];
  error?: string;
}

export interface BacktestOccurrence {
  start_date: string;
  end_date: string;
  duration_days: number;
  high_pct: number;
  low_pct: number;
  return_pct: number;
  pre_entry_ret_20d?: number | null;
  pre_entry_ret_20d_pctile?: number | null;
  above_sma50_at_entry?: boolean | null;
}

export interface SignalAxis {
  current: number | null;
  top1_next_probability: number | null;
  transition_entropy: number | null;
  next_top3: { quadrant: number; probability: number }[];
}

export interface SignalOutcomeAxis {
  actual: number | null;
  changed: boolean;
  top3_hit: boolean | null;
}

export interface SignalOutcome {
  check_date: string | null;
  spx_return_pct: number | null;
  axes: { compass: SignalOutcomeAxis; grid: SignalOutcomeAxis };
}

export interface SignalDivergenceAxis {
  p_up: number | null;
  discrete_up: number | null;
  discrete_quadrant: number | null;
  divergence_score: number | null;
  direction: "market_up" | "market_down" | null;
}

export interface SignalDivergence {
  model_version: string | null;
  features_as_of: string | null;
  axes: { credit?: SignalDivergenceAxis; inflation?: SignalDivergenceAxis };
}

export interface SignalRow {
  signal_date: string;
  signal_id: string;
  timestamp_utc: string | null;
  spx_close_at_signal: number | null;
  compass: SignalAxis;
  grid: SignalAxis;
  outcomes: { "1w": SignalOutcome | null; "1m": SignalOutcome | null; "3m": SignalOutcome | null };
  divergence: SignalDivergence | null;
  upcoming_releases: unknown[] | null;
}

export interface SignalHorizonAxisSummary {
  n_scored: number;
  n_changed: number;
  n_top3_hit: number;
  hit_rate_on_changed: number | null;
}

export interface SignalsResponse {
  summary: {
    n_signals: number;
    first_signal_date: string | null;
    last_signal_date: string | null;
    n_with_divergence: number;
    horizons: Record<"1w" | "1m" | "3m", { compass: SignalHorizonAxisSummary; grid: SignalHorizonAxisSummary }>;
  };
  signals: SignalRow[];
}

export type MarkovAxis = "liquidity" | "credit" | "growth" | "inflation";
export type ReleaseType = "FOMC" | "SLOOS" | "CPI" | "GDP";

export interface FlipBasis {
  p_flip: number;
  n_flips: number;
  expected_releases: number;
  dwell_days: number;
}

export interface MarketRead {
  p_flip: number;
  source: string;
  detail: string;
  experimental: boolean;
}

export interface UpcomingRelease {
  date: string;
  type: ReleaseType;
  axis: MarkovAxis;
  model: "compass" | "grid";
  current_quadrant: number;
  current_state: 0 | 1;
  p_flip: number;
  if_flip_quadrant: number;
  basis: FlipBasis;
  market: MarketRead | null;
  gap: number | null;
  context: { gdpnow: number | null; as_of: string | null } | null;
}

export interface MarkovEvent {
  date: string;
  type: ReleaseType;
  axis: MarkovAxis;
  model: "compass" | "grid";
  scheduled: boolean;
  quadrant_before: number | null;
  state_before: 0 | 1;
  p_flip: number | null;
  p_market: number | null;
  market_source: string | null;
  pre_registered_on: string | null;
  pre_registration_note: string | null;
  flipped: boolean;
  flip_recorded_on: string | null;
  quadrant_after: number | null;
  brier: number | null;
  brier_market: number | null;
  hit: boolean | null;
  hit_market: boolean | null;
}

export interface AxisDriver {
  name: string;
  n: number;
  insufficient?: boolean;
  mean_flip?: number | null;
  mean_noflip?: number | null;
  terciles?: [number, number];
  p_by_tercile?: (number | null)[];
  n_by_tercile?: number[];
  current_value?: number | null;
  current_tercile?: 0 | 1 | 2 | null;
  p_current?: number | null;
  base_rate?: number | null;
  window_start?: string | null;
  categorical?: boolean;
  buckets?: Record<string, { n: number; p_flip: number | null }>;
  current_bucket?: string | null;
}

export interface AxisDriverState {
  n_windows: number;
  n_flips: number;
  base_rate: number | null;
  drivers: AxisDriver[];
  conditioned_p_flip: number | null;
  n_drivers_used: number;
}

export interface AxisDrivers {
  cadence_days: number;
  n_windows: number;
  window_range: [string, string] | null;
  release_type: ReleaseType;
  current_state: 0 | 1;
  current: AxisDriverState;
  from_state: Record<"0" | "1", AxisDriverState>;
}

export interface MarkovRun {
  compass: number;
  grid: number;
  start: string;
  end: string;
  days: number;
}

export interface MarkovResponse {
  as_of: string;
  current: { compass: number; grid: number };
  upcoming: UpcomingRelease[];
  flip_rates: Record<MarkovAxis, Record<"0" | "1", FlipBasis>>;
  event_log: MarkovEvent[];
  pending: { date: string; type: ReleaseType; axis: MarkovAxis; model: "compass" | "grid"; quadrant_before: number; state_before: 0 | 1; settle_by: string }[];
  summary: {
    n_events: number;
    n_unscheduled: number;
    n_pending: number;
    n_flips: number;
    n_pre_registered: number;
    brier: number | null;
    hit_rate: number | null;
    n_market_scored: number;
    brier_market: number | null;
    hit_rate_market: number | null;
    track_start: string;
  };
  runs: MarkovRun[];
  latest_daily: SignalRow | null;
  n_daily_rows: number;
  drivers: { as_of: string; lookback_rows: number; axes: Record<MarkovAxis, AxisDrivers> } | null;
  timeline: TimelineEvent[];
}

export interface TimelineEvent {
  date: string;
  type: string;
  tier: "axis" | "watch";
  label: string;
  informs: string[];
}

export interface BacktestOccurrencesResponse {
  schema_version: number;
  last_refreshed_at: string | null;
  ticker: string;
  compass_q: number;
  grid_q: number;
  occurrences: BacktestOccurrence[];
  error?: string;
}

export interface StandingTheme {
  name: string;
  since: string;
  horizon: string;
  review_on: string;
  thesis: string;
  expressions: string[];
  watchlist?: string[];
  exit_rule?: string | null;
  days_to_review: number | null;
}

export interface ThemeLeg {
  symbol: string;
  status: "running" | "no active run" | "insufficient history" | "not in price-history";
  onset?: string;
  age_days?: number;
  rs_gain_pct?: number;
  price_gain_pct?: number;
  persistence?: number;
  rs_vs_trend_pct?: number;
  last_above?: string | null;
  n_days?: number;
}

export interface ThemeRow {
  theme: string;
  class: "megatrend" | "rotation";
  legs: ThemeLeg[];
  n_running: number;
  n_legs: number;
  onset: string | null;
  age_days: number | null;
  lead_symbol: string | null;
  stage: "early" | "mid" | "late" | null;
  survival_pct: number | null;
}

export interface RunStats {
  n_runs: number;
  median_days: number;
  mean_days: number;
  p75_days: number;
  p90_days: number;
  measured_on: string;
}

export interface ThemesResponse {
  as_of: string | null;
  benchmark: string;
  method: string;
  note: string;
  standing: StandingTheme[];
  run_stats: RunStats;
  themes: ThemeRow[];
  generated_at: string;
}

export interface BreadthGauge {
  symbol: string;
  label: string;
  as_of: string;
  value: number;
  change: number | null;
  zone: "oversold" | "neutral" | "overbought";
  days_below_30_of_60: number;
}

export interface TechnicalsResponse {
  as_of: string;
  universe?: string;
  net_new_highs: {
    value: number;
    ema_fast: number;
    ema_slow: number;
    spread: number;
    colour: "red" | "white" | "green";
    streak_days: number;
    state: string;
    cross_signal: string | null;
    last_cross: { date: string; direction: "up" | "down"; days_ago: number } | null;
    series: { date: string; net: number; fast: number; slow: number; colour: "green" | "red" | "white" }[];
  };
  gauges: BreadthGauge[];
  oversold: string[];
  confirmation: string;
  caveat: string;
  generated_at: string;
}

export interface Note {
  date: string;
  kind?: "data" | "narrative" | "policy";
  scope: string;
  title: string;
  body: string;
  source: string;
  confidence?: "confirmed" | "likely" | "speculative";
  age_days?: number | null;
}

export interface PolicyNote {
  country: string;
  type: "monetary" | "fiscal" | "trade" | "geopolitical";
  announced: string;
  effective: string | null;
  title: string;
  detail: string;
  themes: string[];
  tickers: string[];
  source: string;
  confidence?: string;
  age_days: number | null;
  live_themes: string[];
  is_live: boolean;
}

export interface NotesResponse {
  as_of: string;
  counts: { policy: number; narrative: number; findings: number };
  countries: string[];
  policy: PolicyNote[];
  narrative: Note[];
  findings: Note[];
  note: string;
}

export interface CotContract {
  contract: string;
  status: string;
  as_of?: string;
  open_interest?: number;
  spec: number;
  comm: number;
  small: number;
  spec_pct_oi: number;
  spec_change_4w: number;
  cot_index: Record<string, number | null>;
  cot_index_pct_oi: Record<string, number | null>;
  signal: string | null;
  n_weeks: number;
  history_from: string;
  spark: number[];
}

export interface CotResponse {
  as_of: string | null;
  source: string;
  groups: { group: string; contracts: CotContract[] }[];
  extremes: { contract: string; cot_index_3y: number | null; cot_index_3y_pct_oi: number | null; spec: number; signal: string | null }[];
  caveat: string;
  generated_at: string;
}

export interface PolicyCandidate {
  country: string;
  source: string;
  type: string;
  announced: string | null;
  title: string;
  link: string;
}

export interface PolicyWatchResponse {
  as_of: string;
  window_days: number;
  candidates: PolicyCandidate[];
  no_feed: { country: string; source: string; reason: string }[];
  errors: { country: string; source: string; error: string }[];
  note: string;
}
