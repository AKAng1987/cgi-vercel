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
