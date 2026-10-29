import { PlotlyChart } from "../macro/PlotlyChart";
import { CAPEX_SECTOR_COLORS, ZERO_LINE_COLOR } from "@/lib/macroConstants";
import type { CapexQuarter } from "@/lib/types";
import type { Data, Layout } from "plotly.js";

/** Stacked quarterly bars: each sector's contribution (points) to YoY growth in S&P 500 capex, with the total
 *  as a line. A quarter in which most spenders have not filed yet is drawn faded and labelled partial. */
export function CapexContribution({ quarters, sectors }: { quarters: CapexQuarter[]; sectors: string[] }) {
  const rows = quarters.filter((r) => r.total_yoy_pct !== null);
  const x = rows.map((r) => r.q.replace(/^(\d{4})(Q\d)$/, "$2 $1"));
  const opacity = rows.map((r) => (r.partial ? 0.4 : 1));
  const bars: Data[] = sectors.map((s) => ({
    type: "bar",
    name: s,
    x,
    y: rows.map((r) => r.contrib[s] ?? 0),
    marker: { color: CAPEX_SECTOR_COLORS[s] ?? "#6B7280", opacity },
    hovertemplate: `${s}: %{y:+.2f} pts<extra></extra>`,
  }));
  const total: Data = {
    type: "scatter",
    mode: "lines+markers",
    name: "Total YoY %",
    x,
    y: rows.map((r) => r.total_yoy_pct as number),
    line: { color: "#9CA3AF", width: 2, dash: "dot" },
    marker: { size: 5, color: "#9CA3AF" },
    hovertemplate: "Total: %{y:+.1f}%<extra></extra>",
  };
  const layout = {
    barmode: "relative",
    xaxis: { type: "category" },
    yaxis: { title: { text: "points of YoY capex growth" }, ticksuffix: "" },
    legend: { orientation: "h", y: -0.18, font: { size: 10 } },
    margin: { t: 10, b: 70, l: 50, r: 10 },
    shapes: [
      { type: "line", xref: "paper", x0: 0, x1: 1, yref: "y", y0: 0, y1: 0, line: { color: ZERO_LINE_COLOR, width: 1 } },
    ],
  } as unknown as Partial<Layout>;
  return <PlotlyChart height={360} data={[...bars, total]} layout={layout} />;
}
