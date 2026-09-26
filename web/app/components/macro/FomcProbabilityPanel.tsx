import { PlotlyChart } from "./PlotlyChart";
import { COLORS } from "@/lib/macroConstants";
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
  // Listed bottom-to-top: Plotly puts the FIRST category at the bottom of a
  // horizontal bar chart, so this reads Hike / Hold / Cut top-to-bottom.
  // Previously the order was reversed AND the y tick labels were clipped off
  // the left edge (no automargin), leaving three unlabelled bars -- the 0.0%
  // at the top was the CUT, and a reader reasonably took it for the hike.
  const outcomeLabels = ["Cut 25bp", "Hold", "Hike 25bp"];
  const outcomeVals = [next.p_cut * 100, next.p_hold * 100, next.p_hike * 100];
  const barColors = [COLORS.cut, COLORS.hold, COLORS.hike];

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
          title: {
            text: `Next FOMC: ${nextDate} — implied avg ${next.implied_avg.toFixed(3)}%`,
            font: { size: 12, color: "#9CA3AF" },
          },
          xaxis: { range: [0, 110], title: { text: "Probability (%)" } },
          // automargin: without it the category names are clipped and the
          // chart shows three anonymous bars.
          yaxis: { gridcolor: "rgba(0,0,0,0)", automargin: true },
        }}
      />
      <p className="mt-1 text-[0.66rem] leading-relaxed text-slate-500">
        CME FedWatch method: the futures-implied average for the meeting month is split into the
        days before and after the meeting to back out the implied post-meeting rate, which is then
        compared with the current target midpoint. It will not match CME exactly &mdash; they use
        intraday settlement prices and a finer outcome grid. Note the sensitivity when a meeting
        falls late in the month: with only a few days after it, a 1bp move in the implied average
        is amplified roughly tenfold in the implied post-meeting rate.
      </p>
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
