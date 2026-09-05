import { PlotlyChart } from "./PlotlyChart";
import { DARK_LAYOUT, GRID_COLOR } from "@/lib/macroConstants";
import type { TreasuryCurvePoint } from "@/lib/macroTypes";
import type { Data, Layout } from "plotly.js";

const TENOR_ORDER = ["1M", "3M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"] as const;

function monthsAgo(dateStr: string, months: number): string {
  const d = new Date(dateStr);
  d.setMonth(d.getMonth() - months);
  return d.toISOString().slice(0, 10);
}

/**
 * Treasury Yield Curve -- 2-subplot layout ported from app.py:2308-2352:
 * left = curve snapshot (latest / 6M ago / 1Y ago), right = 10Y history.
 * Plotly.js subplots need explicit xaxis2/yaxis2 domains rather than
 * make_subplots' automatic layout -- hand-rolled here via `domain`.
 */
export function YieldCurvePanel({ points }: { points: TreasuryCurvePoint[] }) {
  if (points.length === 0) return null;

  const avail = TENOR_ORDER.filter((t) => points.some((p) => p[t] != null));
  const sorted = [...points].sort((a, b) => a.date.localeCompare(b.date));
  const latest = sorted[sorted.length - 1];
  const ago6mCutoff = monthsAgo(latest.date, 6);
  const ago1yCutoff = monthsAgo(latest.date, 12);

  const findAsOf = (cutoff: string) => {
    const candidates = sorted.filter((p) => p.date <= cutoff);
    return candidates.length > 0 ? candidates[candidates.length - 1] : null;
  };
  const ago6m = findAsOf(ago6mCutoff);
  const ago1y = findAsOf(ago1yCutoff);

  const snapshotSpecs: { row: TreasuryCurvePoint | null; label: string; color: string }[] = [
    { row: latest, label: "Latest", color: "#60A5FA" },
    { row: ago6m, label: "6M Ago", color: "#F59E0B" },
    { row: ago1y, label: "1Y Ago", color: "#9CA3AF" },
  ];
  const snapshotTraces: Data[] = snapshotSpecs
    .filter((s) => s.row !== null)
    .map(
      (s): Data => ({
        type: "scatter",
        mode: "lines+markers",
        name: s.label,
        x: avail,
        y: avail.map((t) => s.row![t] ?? null),
        line: { color: s.color, width: 2 },
        xaxis: "x",
        yaxis: "y",
      })
    );

  const hist10y = sorted.filter((p) => p["10Y"] != null);
  const historyTrace = {
    type: "scatter",
    mode: "lines",
    name: "10Y Yield",
    x: hist10y.map((p) => p.date),
    y: hist10y.map((p) => p["10Y"]),
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
