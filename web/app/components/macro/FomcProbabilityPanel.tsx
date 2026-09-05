import { PlotlyChart } from "./PlotlyChart";
import { DARK_LAYOUT, GRID_COLOR, COLORS } from "@/lib/macroConstants";
import type { FomcProbabilities } from "@/lib/macroTypes";
import type { Data } from "plotly.js";

/**
 * Ported from app.py:2148-2205: horizontal bar for the next meeting's
 * outcome probabilities, plus a table of the next 3-4 meetings.
 */
export function FomcProbabilityPanel({ probs }: { probs: FomcProbabilities }) {
  const rows = probs.probabilities;
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No upcoming meetings with futures data found.</p>;
  }

  const next = rows[0];
  const outcomeLabels = ["Hike 25bp", "Hold", "Cut 25bp"];
  const outcomeVals = [next.p_hike * 100, next.p_hold * 100, next.p_cut * 100];
  const barColors = [COLORS.hike, COLORS.hold, COLORS.cut];

  const data: Data[] = [
    {
      type: "bar",
      orientation: "h",
      x: outcomeVals,
      y: outcomeLabels,
      marker: { color: barColors },
      text: outcomeVals.map((v) => `${v.toFixed(1)}%`),
      textposition: "outside",
      textfont: { color: "#9CA3AF" },
    },
  ];

  const nextDate = new Date(next.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

  return (
    <div>
      <PlotlyChart
        height={200}
        data={data}
        layout={{
          ...DARK_LAYOUT,
          title: {
            text: `Next FOMC: ${nextDate}  (implied avg ${next.implied_avg.toFixed(3)}%)`,
            font: { size: 12, color: "#9CA3AF" },
          },
          xaxis: { range: [0, 110], gridcolor: GRID_COLOR, title: { text: "Probability (%)" } },
          yaxis: { gridcolor: "rgba(0,0,0,0)" },
        }}
      />
      {rows.length > 1 && (
        <table className="mt-3 w-full text-left text-xs">
          <thead>
            <tr className="bg-slate-800 uppercase text-[0.66rem] text-slate-400">
              <th className="px-2 py-1">Date</th>
              <th className="px-2 py-1">Futures</th>
              <th className="px-2 py-1">Implied Avg</th>
              <th className="px-2 py-1">Most Likely</th>
              <th className="px-2 py-1">Probability</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 4).map((p) => (
              <tr key={p.date} className="border-t border-slate-800">
                <td className="px-2 py-1">
                  {new Date(p.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                </td>
                <td className="px-2 py-1">{p.ticker}</td>
                <td className="px-2 py-1">{p.implied_avg.toFixed(3)}%</td>
                <td className="px-2 py-1">{p.most_likely}</td>
                <td className="px-2 py-1">{(p.prob_most_likely * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
