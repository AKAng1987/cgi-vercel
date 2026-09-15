import { MarkovEvent, MarkovResponse } from "@/lib/types";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

const TH = "bg-[#1F2937] px-2 py-1 text-[0.68rem] uppercase tracking-wide text-slate-400";
const TD = "px-2 py-1.5";

function q(model: "compass" | "grid", n: number | null): string {
  if (n === null) return "—";
  return model === "compass" ? `C${n}` : `G${n}`;
}
function qTitle(model: "compass" | "grid", n: number | null): string {
  if (n === null) return "";
  return model === "compass" ? COMPASS_Q_LABELS[n] : GRID_Q_LABELS[n];
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900/60 px-3 py-2">
      <div className="text-[0.65rem] uppercase tracking-[2px] text-slate-500">{label}</div>
      <div className="text-xl font-bold text-slate-100">{value}</div>
      {sub && <div className="text-[0.68rem] text-slate-500">{sub}</div>}
    </div>
  );
}

export function EventLog({ events, summary }: { events: MarkovEvent[]; summary: MarkovResponse["summary"] }) {
  const brier = summary.brier === null ? "—" : summary.brier.toFixed(3);
  const hit = summary.hit_rate === null ? "—" : `${Math.round(summary.hit_rate * 100)}%`;
  return (
    <section className="mb-6">
      <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
        Event log · since {summary.track_start}
      </div>
      <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Releases scored" value={String(summary.n_events)} sub={summary.n_unscheduled ? `+${summary.n_unscheduled} unscheduled` : undefined} />
        <Stat label="Flips" value={`${summary.n_flips}/${summary.n_events}`} />
        <Stat label="Brier score" value={brier} sub="0 perfect · 0.25 coin-flip" />
        <Stat label="Hit at 0.5" value={hit} sub="coarse companion to Brier" />
      </div>

      {events.length === 0 ? (
        <div className="rounded border border-slate-800 bg-slate-900/40 p-3 text-sm text-slate-400">
          No releases have landed since {summary.track_start} yet.
        </div>
      ) : (
        <div className="overflow-x-auto rounded border border-slate-800">
          <table className="w-full border-collapse text-[0.76rem]">
            <thead>
              <tr>
                <th className={`${TH} text-left`}>Release</th>
                <th className={`${TH} text-left`}>Axis</th>
                <th className={`${TH} text-left`}>Before</th>
                <th className={`${TH} text-right`}>P(flip) quoted</th>
                <th className={`${TH} text-left`}>Outcome</th>
                <th className={`${TH} text-left`}>After</th>
                <th className={`${TH} text-right`}>Brier</th>
                <th className={`${TH} text-left`}>Hit</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={`${e.date}-${e.axis}`} className="border-t border-slate-800/60 hover:bg-slate-800/40">
                  <td className={`${TD} whitespace-nowrap`}>
                    <span className="font-medium text-slate-200">{e.date}</span>
                    <span className="ml-2 text-slate-400">{e.type}</span>
                    {!e.scheduled && <span className="ml-2 rounded bg-[#FCD34D]/20 px-1 text-[0.65rem] text-[#FCD34D]">unscheduled</span>}
                  </td>
                  <td className={`${TD} capitalize text-slate-300`}>
                    {e.axis} <span className="text-slate-500">{e.state_before ? "↑" : "↓"}</span>
                  </td>
                  <td className={`${TD} text-slate-300`} title={qTitle(e.model, e.quadrant_before)}>{q(e.model, e.quadrant_before)}</td>
                  <td className={`${TD} text-right text-slate-200`}>{e.p_flip === null ? "—" : `${Math.round(e.p_flip * 100)}%`}</td>
                  <td className={`${TD} font-bold ${e.flipped ? "text-[#FCD34D]" : "text-slate-400"}`}>{e.flipped ? "FLIP" : "hold"}</td>
                  <td className={`${TD} text-slate-200`} title={qTitle(e.model, e.quadrant_after)}>{q(e.model, e.quadrant_after)}</td>
                  <td className={`${TD} text-right text-slate-300`}>{e.brier === null ? "—" : e.brier.toFixed(3)}</td>
                  <td className={`${TD} font-bold ${e.hit === null ? "text-slate-600" : e.hit ? "text-[#00C851]" : "text-[#FF4444]"}`}>
                    {e.hit === null ? "—" : e.hit ? "HIT" : "MISS"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
