import { PlotlyChart } from "./PlotlyChart";
import { DARK_LAYOUT, GRID_COLOR, ZERO_LINE_COLOR } from "@/lib/macroConstants";
import type { Data, Layout } from "plotly.js";

// Plotly's TS defs use regex-literal types for axis refs ("y2", "x2", ...)
// that don't play well with dynamically-built shape/annotation arrays --
// built loosely here and cast at the layout boundary instead of fighting
// each literal type.

export interface LineSeries {
  name: string;
  x: (string | number)[];
  y: (number | null)[];
  color: string;
  width?: number;
  shape?: "linear" | "hv";
  fill?: "tonexty" | "tozeroy" | "none";
  fillColor?: string;
  yaxis?: "y" | "y2";
  showlegend?: boolean;
}

interface LineChartProps {
  title?: string;
  series: LineSeries[];
  height?: number;
  yTitle?: string;
  y2Title?: string;
  hLineY?: number; // e.g. 0 or 2 for reference lines
  hLineLabel?: string;
}

/**
 * Generic multi-series line/step chart. Covers Fed Funds Target Range
 * (dual step-trace with fill-between, app.py:2124-2140), Spreads
 * (dual-y-axis, app.py:2369-2386), Inflation (multi-line + 2% ref,
 * app.py:2665-2694), Core PCE (single line + 2% ref, app.py:2712-2733).
 */
export function LineChart({
  title,
  series,
  height = 300,
  yTitle,
  y2Title,
  hLineY,
  hLineLabel,
}: LineChartProps) {
  const hasY2 = series.some((s) => s.yaxis === "y2");

  const data: Data[] = series.map((s) => ({
    type: "scatter",
    mode: "lines",
    name: s.name,
    x: s.x,
    y: s.y,
    line: { color: s.color, width: s.width ?? 1.5, shape: s.shape ?? "linear" },
    fill: s.fill,
    fillcolor: s.fillColor,
    yaxis: s.yaxis === "y2" ? "y2" : "y",
    showlegend: s.showlegend ?? true,
    connectgaps: false,
  }));

  const shapes: Record<string, unknown>[] = [];
  const annotations: Record<string, unknown>[] = [];
  if (hLineY !== undefined) {
    shapes.push({
      type: "line",
      xref: "paper",
      x0: 0,
      x1: 1,
      yref: "y",
      y0: hLineY,
      y1: hLineY,
      line: { color: hLineY === 0 ? ZERO_LINE_COLOR : "#6B7280", width: 1, dash: hLineY === 0 ? "solid" : "dot" },
    });
    if (hLineLabel) {
      annotations.push({
        xref: "paper",
        x: 1,
        xanchor: "left",
        yref: "y",
        y: hLineY,
        text: hLineLabel,
        showarrow: false,
        font: { color: "#6B7280", size: 10 },
      });
    }
  }

  return (
    <PlotlyChart
      height={height}
      data={data}
      layout={
        {
          ...DARK_LAYOUT,
          title: title ? { text: title, font: { size: 11, color: "#9CA3AF" } } : undefined,
          xaxis: { gridcolor: GRID_COLOR },
          yaxis: { gridcolor: GRID_COLOR, title: yTitle ? { text: yTitle } : undefined },
          yaxis2: hasY2
            ? { gridcolor: GRID_COLOR, title: y2Title ? { text: y2Title } : undefined, overlaying: "y", side: "right" }
            : undefined,
          shapes,
          annotations,
        } as Partial<Layout>
      }
    />
  );
}
