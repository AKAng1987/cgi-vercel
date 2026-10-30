import { PlotlyChart } from "../macro/PlotlyChart";
import type { CapexFlow as Flow } from "@/lib/types";
import type { Data, Layout } from "plotly.js";

const AI = "AI receivers (12)";
const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(0)}%`);
const lab = (q: string) => q.replace(/^(\d{4})(Q\d)$/, "$2 $1");

/** The five hyperscalers' capex growth drawn beside the revenue growth of the companies that supply them (AI power, chips,
 *  data-centre equipment), then three sectors. Descriptive: it shows whether the spending is arriving as suppliers' revenue,
 *  not what happens next (research/capex_flow tested that and the AI forecasting result is thin: see RESULTS.md). */
export function CapexFlow({ flow }: { flow: Flow }) {
  const ai = (flow.series[AI] ?? []).filter((r) => r.revenue_yoy !== null || r.spender_capex_yoy !== null);
  if (ai.length === 0) return null;
  const x = ai.map((r) => lab(r.q));
  const traces: Data[] = [
    { type: "scatter", mode: "lines+markers", name: "Five hyperscalers: capex growth", x, y: ai.map((r) => r.spender_capex_yoy),
      line: { color: "#F59E0B", width: 3 }, marker: { size: 5 }, connectgaps: false },
    { type: "scatter", mode: "lines+markers", name: "AI suppliers: revenue growth", x, y: ai.map((r) => r.revenue_yoy),
      line: { color: "#60A5FA", width: 3 }, marker: { size: 5 }, connectgaps: false },
  ];
  const layout = { yaxis: { title: { text: "year over year, %" }, ticksuffix: "%" }, xaxis: { type: "category" },
    legend: { orientation: "h", y: -0.25, font: { size: 10 } }, margin: { t: 10, b: 70, l: 55, r: 10 } } as unknown as Partial<Layout>;
  const ll = flow.lead_lag[AI] ?? {};
  const others = Object.keys(flow.series).filter((k) => k !== AI);
  const latest = (rows: { q: string; revenue_yoy: number | null }[]) => [...rows].reverse().find((r) => r.revenue_yoy !== null);
  return (
    <div className="mt-6">
      <div className="mb-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Where the money goes</div>
      <p className="mb-2 text-[0.7rem] leading-relaxed text-slate-400">
        Hyperscaler spending is suppliers&apos; revenue. The chart sets the five spenders&apos; capex growth against the revenue growth of
        twelve suppliers: power ({flow.members[AI]?.slice(0, 4).join(" ")}), chips ({flow.members[AI]?.slice(4, 8).join(" ")}) and data-centre
        equipment ({flow.members[AI]?.slice(8, 12).join(" ")}). Both are as first reported.
      </p>
      <PlotlyChart height={300} data={traces} layout={layout} />
      <div className="mt-2 text-[0.7rem] text-slate-400">
        How closely supplier revenue growth tracks spender capex growth k quarters earlier (correlation, whole sample, overlapping quarters, not a test):{" "}
        {Object.entries(ll).map(([k, v]) => (
          <span key={k} className="mr-3 whitespace-nowrap text-slate-300">k={k}: <span className="tabular-nums">{v.corr === null ? "—" : v.corr.toFixed(2)}</span></span>
        ))}
      </div>
      <table className="mt-2 w-full text-left text-xs">
        <thead>
          <tr className="bg-slate-800 text-[0.66rem] uppercase text-slate-400">
            <th className="px-2 py-1">Receivers</th><th className="px-2 py-1 text-right">Latest revenue growth</th><th className="px-2 py-1">Quarter</th>
          </tr>
        </thead>
        <tbody>
          {[AI, ...others].map((k) => {
            const r = latest(flow.series[k] ?? []);
            return (
              <tr key={k} className="border-t border-slate-800">
                <td className="px-2 py-1 text-slate-200">{k}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-100">{pct(r?.revenue_yoy)}</td>
                <td className="px-2 py-1 text-slate-500">{r ? lab(r.q) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2 text-[0.62rem] leading-relaxed text-slate-600">
        Does knowing the spenders&apos; capex improve a forecast of next quarter&apos;s supplier revenue beyond that group&apos;s own trend? Tested
        out of sample (research/capex_flow): it did not: for the AI suppliers the forecast was no better with the capex than without (17 quarters scored: too few to rule a modest link out), and none of the three sectors improved either. Descriptive, not a signal. Today&apos;s S&amp;P 500 members and today&apos;s layer lists applied to
        all history.
      </p>
    </div>
  );
}
