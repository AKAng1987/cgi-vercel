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
      // The height is set on the STYLE as well as in the layout, deliberately.
      //
      // Plotly with autosize + useResizeHandler re-measures its container on
      // every re-render, and if it measures while the container has no height
      // it collapses to zero and stays there. Adding useTheme() to the chart
      // components introduced exactly that: the hook starts at "dark" and sets
      // state in an effect, so every chart re-renders once immediately after
      // mount. Six charts on MACRO -- Fed Funds, Lending Standards, Challenger,
      // Real GDP, Inflation and Core PCE -- silently collapsed to 0px while
      // still holding all their data, which looked like missing charts rather
      // than broken ones.
      //
      // An explicit style height means the container can never be zero for
      // Plotly to measure, whatever re-renders around it.
      style={{ width: "100%", height }}
      useResizeHandler
      config={{ displayModeBar: false, responsive: true, ...config }}
    />
  );
}
