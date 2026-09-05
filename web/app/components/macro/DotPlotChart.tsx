import { PlotlyChart } from "./PlotlyChart";
import { DARK_LAYOUT, GRID_COLOR, DOT_PLOT_COLORS, DOT_PLOT_LABELS, DOT_PLOT_HORIZON_ORDER } from "@/lib/macroConstants";
import type { DotPlotRow } from "@/lib/macroTypes";
import type { Data, Layout } from "plotly.js";

/**
 * SEP dot plot -- ported from app.py:2233-2295. Per-rate-level jitter:
 * dots sharing the same projected_rate within a horizon are spread
 * evenly across a ±0.15 x-offset band so overlapping votes are visible
 * side-by-side rather than stacking into one marker. A thick horizontal
 * bar marks the median rate per horizon.
 */
export function DotPlotChart({ rows }: { rows: DotPlotRow[] }) {
  const availHorizons = DOT_PLOT_HORIZON_ORDER.filter((h) => rows.some((r) => r.year === h));

  const data: Data[] = [];
  const shapes: Record<string, unknown>[] = [];

  availHorizons.forEach((horizon, i) => {
    const sub = rows.filter((r) => r.year === horizon);

    const grouped = new Map<number, DotPlotRow[]>();
    for (const r of sub) {
      const list = grouped.get(r.projected_rate) ?? [];
      list.push(r);
      grouped.set(r.projected_rate, list);
    }

    const xs: number[] = [];
    const ys: number[] = [];
    for (const [rate, grp] of grouped.entries()) {
      const n = grp.length;
      const offsets = n === 1 ? [0] : Array.from({ length: n }, (_, k) => (k * 0.3) / (n - 1) - 0.15);
      offsets.forEach((o) => {
        xs.push(i + o);
        ys.push(rate);
      });
    }

    data.push({
      type: "scatter",
      mode: "markers",
      name: horizon,
      x: xs,
      y: ys,
      marker: {
        size: 10,
        color: DOT_PLOT_COLORS[horizon] ?? "#9CA3AF",
        opacity: 0.75,
        line: { width: 1, color: "#0E1117" },
      },
      showlegend: false,
    });

    const rates = sub.map((r) => r.projected_rate).sort((a, b) => a - b);
    if (rates.length > 0) {
      const mid = Math.floor(rates.length / 2);
      const median = rates.length % 2 === 0 ? (rates[mid - 1] + rates[mid]) / 2 : rates[mid];
      shapes.push({
        type: "line",
        x0: i - 0.35,
        x1: i + 0.35,
        y0: median,
        y1: median,
        xref: "x",
        yref: "y",
        line: { color: DOT_PLOT_COLORS[horizon] ?? "#9CA3AF", width: 3 },
      });
    }
  });

  return (
    <PlotlyChart
      height={320}
      data={data}
      layout={
        {
          ...DARK_LAYOUT,
          showlegend: false,
          xaxis: {
            gridcolor: GRID_COLOR,
            tickvals: availHorizons.map((_, i) => i),
            ticktext: availHorizons.map((h) => DOT_PLOT_LABELS[h] ?? h),
            range: [-0.6, availHorizons.length - 0.4],
          },
          yaxis: { gridcolor: GRID_COLOR, title: { text: "Target Rate (%)" } },
          shapes,
        } as Partial<Layout>
      }
    />
  );
}
