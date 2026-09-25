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
import { layoutFor, gridFor } from "@/lib/macroConstants";
import { useTheme } from "@/lib/useTheme";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface PlotlyChartProps {
  data: Data[];
  layout: Partial<Layout>;
  height?: number;
  config?: Partial<Config>;
}

export function PlotlyChart({ data, layout, height = 300, config }: PlotlyChartProps) {
  // The theme is resolved HERE, in the one component that was already a client
  // component and already worked.
  //
  // It was previously resolved in each chart wrapper, which meant adding
  // "use client" + useTheme to LineChart -- until then a SERVER component.
  // That conversion broke it: next/dynamic with ssr:false renders nothing on
  // the server and never loaded in the newly-converted tree, so all six
  // LineChart panels on MACRO produced correctly-sized but completely empty
  // divs while every BarChart (already a client component) rendered fine.
  //
  // Centralising it means the wrappers stay server components, there is one
  // place that knows about themes instead of five, and the grid colour is
  // applied to whichever axes a caller actually passed.
  const theme = useTheme();
  const grid = gridFor(theme);
  const axis = (a: unknown) =>
    a && typeof a === "object" ? { gridcolor: grid, ...(a as object) } : a;
  const themed: Partial<Layout> = {
    ...layoutFor(theme),
    ...layout,
    xaxis: axis(layout.xaxis) as Layout["xaxis"],
    yaxis: axis(layout.yaxis) as Layout["yaxis"],
    ...(layout.yaxis2 ? { yaxis2: axis(layout.yaxis2) as Layout["yaxis2"] } : {}),
  };
  return (
    <Plot
      data={data}
      layout={{ ...themed, height, autosize: true }}
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
