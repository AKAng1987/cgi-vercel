import { PlotlyChart } from "./PlotlyChart";
import { COLORS } from "@/lib/macroConstants";
import type { RatePath } from "@/lib/macroTypes";
import type { Data, Layout } from "plotly.js";

const fmtDate = (iso: string) => new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "2-digit" });
const bp = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(0)}bp`);
const chg = (v: number | undefined) => (v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(0)}`);

/**
 * What futures price for the policy rate: the expected rate after each FOMC meeting (fed funds futures, solid) and the
 * average SOFR expected over each quarter further out (SOFR futures, squares), against today, with the pricing of four weeks
 * ago as a faint line so a repricing is visible. Descriptive: it is what is PRICED, not a forecast. Fed funds futures are on
 * EFFR and SOFR futures on SOFR, so the two strips differ by the SOFR-EFFR gap; it is shown, not netted.
 */
export function RatePathCard({ data }: { data: RatePath }) {
  const meetings = data.meetings.filter((m) => m.available && m.post_rate !== undefined);
  const sr3 = data.sr3.filter((s) => s.implied_sofr !== null);
  if (meetings.length === 0 && sr3.length === 0) {
    return <p className="text-sm text-slate-500">No futures could be read for the rate path.</p>;
  }
  const ghost = data.moved.four_weeks;
  const ghostByDate = new Map((ghost?.meetings ?? []).map((m) => [m.date, m.was]));
  const traces: Data[] = [];
  if (data.effr !== null && meetings.length) {
    traces.push({
      type: "scatter", mode: "lines", name: "Fed funds futures (after each meeting)",
      x: [data.as_of, ...meetings.map((m) => m.date)], y: [data.effr, ...meetings.map((m) => m.post_rate as number)],
      line: { color: COLORS.upper, width: 3, shape: "hv" }, hovertemplate: "%{x}: %{y:.3f}%<extra>fed funds futures</extra>",
    });
  }
  if (ghost && ghost.meetings.length) {
    traces.push({
      type: "scatter", mode: "lines", name: `same, ${fmtDate(ghost.snapshot_date)}`,
      x: meetings.filter((m) => ghostByDate.has(m.date)).map((m) => m.date),
      y: meetings.filter((m) => ghostByDate.has(m.date)).map((m) => ghostByDate.get(m.date) as number),
      line: { color: COLORS.upper, width: 1.5, dash: "dot", shape: "hv" }, opacity: 0.55,
      hovertemplate: "%{x}: %{y:.3f}%<extra>4 weeks ago</extra>",
    });
  }
  if (sr3.length) {
    traces.push({
      type: "scatter", mode: "lines+markers", name: "SOFR futures (quarter average)",
      x: sr3.map((s) => s.start), y: sr3.map((s) => s.implied_sofr as number),
      line: { color: COLORS.lower, width: 2 }, marker: { symbol: "square", size: 6, color: COLORS.lower },
      text: sr3.map((s) => s.label), hovertemplate: "%{text}: %{y:.3f}%<extra>SOFR futures</extra>",
    });
  }
  const layout = { yaxis: { title: { text: "Rate (%)" } }, xaxis: { type: "date" }, legend: { orientation: "h", y: -0.2, font: { size: 10 } },
    margin: { t: 10, b: 60, l: 50, r: 10 } } as unknown as Partial<Layout>;

  const wk = new Map((data.moved.week?.meetings ?? []).map((m) => [m.date, m.change_bp]));
  const mo = new Map((data.moved.four_weeks?.meetings ?? []).map((m) => [m.date, m.change_bp]));
  return (
    <div>
      <div className="mb-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
        <Stat label="Now (EFFR)" value={data.effr !== null ? `${data.effr.toFixed(2)}%` : "—"} help={`target ${data.target[0]?.toFixed(2)}–${data.target[1]?.toFixed(2)}%`} />
        <Stat label="SOFR minus EFFR" value={bp(data.sofr_minus_effr_bp)} help={data.sofr ? `SOFR ${data.sofr.value.toFixed(2)}% on ${data.sofr.date}` : "SOFR not read"} />
        <Stat label="Fed funds peak priced" value={data.peak_fed_funds ? `${data.peak_fed_funds.rate.toFixed(2)}%` : "—"}
          help={data.peak_fed_funds ? `${bp(data.peak_fed_funds.bp_vs_now)} by ${fmtDate(data.peak_fed_funds.date)} (thin far out)` : ""} />
        <Stat label="SOFR futures peak" value={data.peak_sofr ? `${data.peak_sofr.rate.toFixed(2)}%` : "—"}
          help={data.peak_sofr ? `${bp(data.peak_sofr.bp_vs_now)} in the quarter from ${fmtDate(data.peak_sofr.date)}` : ""} />
      </div>
      <PlotlyChart height={300} data={traces} layout={layout} />
      <table className="mt-2 w-full text-left text-xs">
        <thead>
          <tr className="bg-slate-800 text-[0.66rem] uppercase text-slate-400">
            <th className="px-2 py-1">Meeting</th>
            <th className="px-2 py-1 text-right">Rate after</th>
            <th className="px-2 py-1 text-right">This step</th>
            <th className="px-2 py-1 text-right">Cumulative</th>
            <th className="px-2 py-1">Hike / hold / cut</th>
            <th className="px-2 py-1 text-right">Moved 1w (bp)</th>
            <th className="px-2 py-1 text-right">Moved 4w (bp)</th>
          </tr>
        </thead>
        <tbody>
          {data.meetings.map((m) =>
            !m.available ? (
              <tr key={m.date} className="border-t border-slate-800 text-amber-400"><td className="px-2 py-1">{fmtDate(m.date)}</td><td className="px-2 py-1" colSpan={6}>no quote — {m.reason}</td></tr>
            ) : (
              <tr key={m.date} className="border-t border-slate-800">
                <td className="px-2 py-1">{fmtDate(m.date)}{m.confident === false && <span className="ml-1 text-amber-400" title="priced off a magnified contract">⚠</span>}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-100">{m.post_rate?.toFixed(3)}%</td>
                <td className="px-2 py-1 text-right tabular-nums">{bp(m.step_bp)}</td>
                <td className="px-2 py-1 text-right tabular-nums">{bp(m.cum_bp)}</td>
                <td className="px-2 py-1 tabular-nums text-slate-300">{Math.round((m.p_hike ?? 0) * 100)}% / {Math.round((m.p_hold ?? 0) * 100)}% / {Math.round((m.p_cut ?? 0) * 100)}%</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-400">{chg(wk.get(m.date))}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-400">{chg(mo.get(m.date))}</td>
              </tr>
            ),
          )}
        </tbody>
      </table>
      <p className="mt-2 text-[0.66rem] leading-relaxed text-slate-500">
        {data.caveat} {data.n_sr3_quoted} of {data.n_sr3} SOFR contracts quoted
        {data.history_days ? `; ${data.history_days} daily snapshots stored` : "; the movement columns fill in as daily snapshots accumulate"}.
        Fed funds contracts far out trade thinly; read the SOFR strip for the shape beyond a year.
      </p>
    </div>
  );
}

function Stat({ label, value, help }: { label: string; value: string; help?: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900/60 p-2">
      <div className="text-[0.62rem] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-lg font-bold text-slate-100">{value}</div>
      {help && <div className="text-[0.62rem] text-slate-600">{help}</div>}
    </div>
  );
}
