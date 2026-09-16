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
function pct(p: number | null): string {
  return p === null ? "—" : `${Math.round(p * 100)}%`;
}
function brier(b: number | null): string {
  return b === null ? "—" : b.toFixed(3);
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

function HitCell({ hit }: { hit: boolean | null }) {
  if (hit === null) return <span className="text-slate-700">—</span>;
  return <span className={`font-bold ${hit ? "text-[#00C851]" : "text-[#FF4444]"}`}>{hit ? "HIT" : "MISS"}</span>;
}

export function EventLog({ events, summary }: { events: MarkovEvent[]; summary: MarkovResponse["summary"] }) {
  return (
    <section className="mb-6">
      <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
        Event log · since {summary.track_start}
      </div>
      <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Releases scored" value={String(summary.n_events)}
          sub={`${summary.n_pre_registered} pre-registered${summary.n_unscheduled ? ` · +${summary.n_unscheduled} unscheduled` : ""}`} />
        <Stat label="Flips" value={`${summary.n_flips}/${summary.n_events}`} />
        <Stat label="Brier · history" value={brier(summary.brier)} sub={`hit ${pct(summary.hit_rate)} at 0.5`} />
        <Stat label="Brier · market" value={brier(summary.brier_market)} sub={`${summary.n_market_scored} scored · hit ${pct(summary.hit_rate_market)}`} />
        <div className="rounded border border-slate-800 bg-slate-900/60 px-3 py-2 text-[0.68rem] leading-snug text-slate-500">
          0 = perfect, 0.25 = coin-flip. Lower wins. History vs. market on the same events is the experiment.
        </div>
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
                <th className={`${TH} text-right`}>History</th>
                <th className={`${TH} text-right`}>Market</th>
                <th className={`${TH} text-left`}>Outcome</th>
                <th className={`${TH} text-left`}>After</th>
                <th className={`${TH} text-right`}>Brier H / M</th>
                <th className={`${TH} text-left`}>Hit H / M</th>
                <th className={`${TH} text-left`}>Registered</th>
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
                  <td className={`${TD} text-right text-slate-200`}>{pct(e.p_flip)}</td>
                  <td className={`${TD} text-right text-slate-200`} title={e.market_source ?? ""}>{pct(e.p_market)}</td>
                  <td className={`${TD} font-bold ${e.flipped ? "text-[#FCD34D]" : "text-slate-400"}`}>{e.flipped ? "FLIP" : "hold"}</td>
                  <td className={`${TD} text-slate-200`} title={qTitle(e.model, e.quadrant_after)}>{q(e.model, e.quadrant_after)}</td>
                  <td className={`${TD} text-right text-slate-300`}>{brier(e.brier)} <span className="text-slate-600">/</span> {brier(e.brier_market)}</td>
                  <td className={TD}><HitCell hit={e.hit} /> <span className="text-slate-600">/</span> <HitCell hit={e.hit_market} /></td>
                  <td className={`${TD} text-[0.68rem]`}>
                    {e.pre_registered_on
                      ? <span className={e.pre_registration_note ? "text-[#FCD34D]" : "text-[#00C851]"} title={e.pre_registration_note ?? "both probabilities were in DynamoDB before the release"}>{e.pre_registered_on.replace("T", " ").replace("Z", "Z")}</span>
                      : e.scheduled ? <span className="text-slate-600" title="history recomputed from model-history after the fact; no market number was stored">recomputed</span> : <span className="text-slate-700">—</span>}
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
