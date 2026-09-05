import { PlotlyChart } from "./PlotlyChart";
import { DARK_LAYOUT, GRID_COLOR, ZERO_LINE_COLOR } from "@/lib/macroConstants";
import type { Data, Layout } from "plotly.js";

export interface BarSeries {
  name: string;
  x: (string | number)[];
  y: number[];
  colors?: string | string[]; // single color or per-bar (e.g. red/green sign coloring)
}

export interface OverlaySeries {
  name: string;
  x: (string | number)[];
  y: number[];
  color: string;
  mode?: "lines+markers" | "markers";
  symbol?: string;
  size?: number;
}

interface BarChartProps {
  title?: string;
  bars: BarSeries[];
  overlays?: OverlaySeries[];
  height?: number;
  yTitle?: string;
  barmode?: "group" | "overlay";
  zeroLine?: boolean;
}

/**
 * Generic bar(+line-overlay) chart. Covers GDP 3a (BEA bars + GDPNow
 * line, app.py:2483-2517), GDP 3b (grouped Advance/Second/Third bars +
 * GDPNow-final diamond markers, app.py:2519-2578), Lending Standards QoQ
 * change bars (app.py:2436-2451).
 */
export function BarChart({ title, bars, overlays = [], height = 280, yTitle, barmode = "group", zeroLine = true }: BarChartProps) {
  const data: Data[] = [
    ...bars.map(
      (b): Data => ({
        type: "bar",
        name: b.name,
        x: b.x,
        y: b.y,
        marker: { color: b.colors },
      })
    ),
    ...overlays.map(
      (o): Data => ({
        type: "scatter",
        mode: o.mode ?? "lines+markers",
        name: o.name,
        x: o.x,
        y: o.y,
        line: { color: o.color, width: 3 },
        marker: { color: o.color, size: o.size ?? 6, symbol: o.symbol as never },
      })
    ),
  ];

  const shapes: Record<string, unknown>[] = zeroLine
    ? [
        {
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          yref: "y",
          y0: 0,
          y1: 0,
          line: { color: ZERO_LINE_COLOR, width: 1 },
        },
      ]
    : [];

  return (
    <PlotlyChart
      height={height}
      data={data}
      layout={
        {
          ...DARK_LAYOUT,
          title: title ? { text: title, font: { size: 11, color: "#9CA3AF" } } : undefined,
          barmode,
          xaxis: { gridcolor: GRID_COLOR },
          yaxis: { gridcolor: GRID_COLOR, title: yTitle ? { text: yTitle } : undefined },
          shapes,
        } as Partial<Layout>
      }
    />
  );
}
