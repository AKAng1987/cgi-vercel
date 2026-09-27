import { PlotlyChart } from "./PlotlyChart";
import { COLORS } from "@/lib/macroConstants";
import type { FomcProbabilities, FomcPricedRow } from "@/lib/macroTypes";
import type { Data } from "plotly.js";

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });

/**
 * Horizontal bar for the next meeting's outcome probabilities, plus a table
 * of the meetings after it.
 *
 * The number shown here used to be unusable. A monthly fed funds contract
 * settles on the AVERAGE rate over its month, so backing out a post-meeting
 * rate means de-averaging it over the days that follow the meeting -- and
 * for a meeting late in the month there are barely any. Oct 28 in a 31-day
 * month left 3 days, multiplying the quote, and every basis point of noise
 * in it, by 10.3. A 1bp wobble moved the displayed hike probability by ~41
 * points. The panel disclosed that amplification in a footnote and showed
 * the number anyway.
 *
 * The API now prices those meetings off the FOLLOWING contract, whose whole
 * month is post-meeting, so no de-averaging is needed at all. The same 1bp
 * now moves the probability ~4 points. `method` and `lever` are shown per
 * row so it is visible which contract did the work.
 */
export function FomcProbabilityPanel({ probs }: { probs: FomcProbabilities }) {
  const rows = probs.probabilities;
  const priced = rows.filter((r): r is FomcPricedRow => r.available !== false);
  const missing = rows.filter((r) => r.available === false);

  if (priced.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No upcoming meeting could be priced
        {missing.length > 0 && <> &mdash; {missing.map((m) => m.ticker).join(", ")} unavailable</>}.
      </p>
    );
  }

  const next = priced[0];
  // Listed bottom-to-top: Plotly puts the FIRST category at the bottom of a
  // horizontal bar chart, so this reads Hike / Hold / Cut top-to-bottom.
  const outcomeLabels = ["Cut", "Hold", "Hike"];
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

  return (
    <div>
      <PlotlyChart
        height={200}
        data={data}
        layout={{
          title: {
            text: `Next FOMC: ${fmtDate(next.date)} — priced off ${next.ticker}, implied avg ${next.implied_avg.toFixed(3)}%`,
            font: { size: 12, color: "#9CA3AF" },
          },
          xaxis: { range: [0, 110], title: { text: "Probability (%)" } },
          // automargin: without it the category names are clipped and the
          // chart shows three anonymous bars.
          yaxis: { gridcolor: "rgba(0,0,0,0)", automargin: true },
        }}
      />

      <p className="mt-1 text-[0.7rem] leading-relaxed text-slate-400">
        From {next.base_rate.toFixed(3)}% expected going into the meeting, the strip implies{" "}
        <strong className="text-slate-200">{next.post_rate.toFixed(3)}%</strong> after it.{" "}
        {next.method === "next_month" ? (
          <>
            Priced off <strong>{next.ticker}</strong>, the contract for the month{" "}
            <em>after</em> the meeting &mdash; its whole month is post-meeting, so the rate is
            read straight off it. Pricing this meeting off its own month&rsquo;s contract would
            have magnified the quote {next.own_lever.toFixed(1)}&times;.
          </>
        ) : (
          <>
            Split out of <strong>{next.ticker}</strong>, its own month&rsquo;s contract, which
            magnifies the quote {next.lever.toFixed(1)}&times;.
          </>
        )}
      </p>

      {!next.confident && (
        <p className="mt-1 text-[0.7rem] leading-relaxed text-amber-400">
          ⚠ This meeting could not be moved onto a later contract, so the quote is still
          magnified {next.lever.toFixed(1)}&times;. Treat the probability as indicative: a 1bp
          move in the contract shifts it by roughly {(next.lever * 4).toFixed(0)} points.
        </p>
      )}

      <p className="mt-1 text-[0.66rem] leading-relaxed text-slate-500">
        CME FedWatch method. The implied post-meeting rate is compared with the rate expected
        going <em>into</em> that meeting, not with today&rsquo;s target, so a second move shows up
        as a second move; the gap is split across whole 25bp steps. It will not match CME exactly
        &mdash; they use intraday settlement prices and a finer grid &mdash; but the difference
        should be a steady offset rather than a number that jumps.
      </p>

      {(priced.length > 1 || missing.length > 0) && (
        <table className="mt-3 w-full text-left text-xs">
          <thead>
            <tr className="bg-slate-800 uppercase text-[0.66rem] text-slate-400">
              <th className="px-2 py-1">Date</th>
              <th className="px-2 py-1">Contract</th>
              <th className="px-2 py-1">Implied avg</th>
              <th className="px-2 py-1">From &rarr; to</th>
              <th className="px-2 py-1">Most likely</th>
              <th className="px-2 py-1">Probability</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 6).map((p) =>
              p.available === false ? (
                <tr key={p.date} className="border-t border-slate-800 text-amber-400">
                  <td className="px-2 py-1">{fmtDate(p.date)}</td>
                  <td className="px-2 py-1">{p.ticker}</td>
                  <td className="px-2 py-1" colSpan={4}>
                    no quote &mdash; {p.reason}
                  </td>
                </tr>
              ) : (
                <tr key={p.date} className="border-t border-slate-800">
                  <td className="px-2 py-1">{fmtDate(p.date)}</td>
                  <td className="px-2 py-1">
                    {p.ticker}
                    {p.method === "de_average" && p.lever > 3 && (
                      <span className="ml-1 text-amber-400" title={`quote magnified ${p.lever}x`}>
                        {p.lever.toFixed(1)}&times;
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-1">{p.implied_avg.toFixed(3)}%</td>
                  <td className="px-2 py-1 text-slate-400">
                    {p.base_rate.toFixed(2)} &rarr; {p.post_rate.toFixed(2)}
                  </td>
                  <td className="px-2 py-1">{p.most_likely}</td>
                  <td className="px-2 py-1">{(p.prob_most_likely * 100).toFixed(1)}%</td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
