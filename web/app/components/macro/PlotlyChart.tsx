"use client";

/**
 * Thin client wrapper around react-plotly.js. Plotly needs `window`, so
 * this must be dynamically imported with ssr:false everywhere it's used
 * (done once here rather than at every call site) -- Server Components
 * can render this component, but the Plotly library itself only runs
 * in the browser.
 */
import dynamic from "next/dynamic";
import type { Data, Layout, Config } from "plotly.js";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface PlotlyChartProps {
  data: Data[];
  layout: Partial<Layout>;
  height?: number;
  config?: Partial<Config>;
}

export function PlotlyChart({ data, layout, height = 300, config }: PlotlyChartProps) {
  return (
    <Plot
      data={data}
      layout={{ ...layout, height, autosize: true }}
      style={{ width: "100%" }}
      useResizeHandler
      config={{ displayModeBar: false, responsive: true, ...config }}
    />
  );
}
