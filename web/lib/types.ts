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
  summary: {
    n_events: number;
    n_unscheduled: number;
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
