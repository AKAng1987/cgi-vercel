import { PlotlyChart } from "./PlotlyChart";
import { DARK_LAYOUT, GRID_COLOR } from "@/lib/macroConstants";
import type { TreasuryCurveResponse, TreasuryCurveSnapshotRow } from "@/lib/macroTypes";
import type { Data, Layout } from "plotly.js";

const TENOR_ORDER = ["1M", "3M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"] as const;

const SNAPSHOT_COLORS: Record<TreasuryCurveSnapshotRow["label"], string> = {
  Latest: "#60A5FA",
  "6M Ago": "#F59E0B",
  "1Y Ago": "#9CA3AF",
};

/**
 * Treasury Yield Curve -- 2-subplot layout ported from app.py:2308-2352:
 * left = curve snapshot (latest / 6M ago / 1Y ago), right = 10Y history.
 * Plotly.js subplots need explicit xaxis2/yaxis2 domains rather than
 * make_subplots' automatic layout -- hand-rolled here via `domain`.
 *
 * As of 2026-09-07 (Task 1b), the snapshot-row-selection and 10Y-history
 * filtering this component used to do client-side (monthsAgo/findAsOf
 * over the full 20-year x 10-tenor table) now happens server-side in
 * api/macro_data.py's _trim_treasury_curve -- this component just plots
 * what it's given. Cuts the wire payload from ~730KB to ~70KB without
 * changing what's rendered (same rows, same algorithm, just moved).
 */
export function YieldCurvePanel({ data }: { data: TreasuryCurveResponse }) {
  if (data.snapshot.length === 0) return null;

  const avail = TENOR_ORDER.filter((t) => data.snapshot.some((p) => p[t] != null));

  const snapshotTraces: Data[] = data.snapshot.map(
    (row): Data => ({
      type: "scatter",
      mode: "lines+markers",
      name: row.label,
      x: avail,
      y: avail.map((t) => row[t] ?? null),
      line: { color: SNAPSHOT_COLORS[row.label], width: 2 },
      xaxis: "x",
      yaxis: "y",
    })
  );

  const historyTrace = {
    type: "scatter",
    mode: "lines",
    name: "10Y Yield",
    x: data.history_10y.map((p) => p.date),
    y: data.history_10y.map((p) => p.value),
    line: { color: "#60A5FA", width: 1.5 },
    showlegend: false,
    xaxis: "x2",
    yaxis: "y2",
  } as unknown as Data;

  return (
    <PlotlyChart
      height={340}
      data={[...snapshotTraces, historyTrace]}
      layout={
        {
          ...DARK_LAYOUT,
          grid: { rows: 1, columns: 2, pattern: "independent" },
          xaxis: { gridcolor: GRID_COLOR, domain: [0, 0.36] },
          yaxis: { gridcolor: GRID_COLOR, title: { text: "Yield (%)" } },
          xaxis2: { gridcolor: GRID_COLOR, domain: [0.42, 1] },
          yaxis2: { gridcolor: GRID_COLOR, title: { text: "Yield (%)" }, anchor: "x2" },
          annotations: [
            { text: "Curve Snapshot", x: 0.18, y: 1.08, xref: "paper", yref: "paper", showarrow: false, font: { size: 11, color: "#9CA3AF" } },
            { text: "10Y Historical", x: 0.71, y: 1.08, xref: "paper", yref: "paper", showarrow: false, font: { size: 11, color: "#9CA3AF" } },
          ],
        } as unknown as Partial<Layout>
      }
    />
  );
}
