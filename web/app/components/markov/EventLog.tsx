import { MarkovEvent, MarkovResponse } from "@/lib/types";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

const TH = "bg-[var(--cgi-surface)] px-2 py-1 text-[0.68rem] uppercase tracking-wide text-slate-400";
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
  if (hit === null) return <span className="text-slate-600">—</span>;
  return <span className={`font-bold ${hit ? "text-[var(--cgi-up)]" : "text-[var(--cgi-down)]"}`}>{hit ? "HIT" : "MISS"}</span>;
}

/** What the stored "market" number actually is. For the FOMC it is fed funds futures. For CPI / GDP / SLOOS the
 *  daily job stores an EXPERIMENTAL CLASSIFIER, which is a different number from the Drivers table figure the brief
 *  and the Upcoming table show. The Drivers figure is stored separately (p_drivers). */
function isFutures(e: MarkovEvent): boolean {
  return (e.market_source ?? "").toLowerCase().includes("futures");
}

type Source = { name: string; note: string; p: (e: MarkovEvent) => number | null; always?: "hold" };
const SOURCES: Source[] = [
  { name: "Base rate", note: "history: its call is always no change; its Brier uses the base probability. The baseline every source has to beat", p: (e) => e.p_flip, always: "hold" },
  { name: "Fed funds futures", note: "FOMC only", p: (e) => (isFutures(e) ? e.p_market : null) },
  { name: "Drivers table", note: "what the brief prints; stored before the release from 2026-10-19", p: (e) => e.p_drivers ?? null },
  { name: "Experimental classifier", note: "stored daily, never shown in the brief", p: (e) => (!isFutures(e) && e.market_source ? e.p_market : null) },
];

/** One source's record. Two views are shown and neither is declared the winner: how often its calls were right
 *  (above the base rate = a flip call, at or below = no change), and its Brier score (lower is better). */
function record(events: MarkovEvent[], src: Source) {
  const sc = events.filter((e) => e.scheduled && e.p_flip !== null && src.p(e) !== null);
  const call = (e: MarkovEvent): "flip" | "hold" =>
    src.always ? "hold" : (src.p(e) as number) - (e.p_flip as number) > 0.005 ? "flip" : "hold";
  const up = sc.filter((e) => call(e) === "flip");
  const down = sc.filter((e) => call(e) === "hold");
  const b = sc.map((e) => ((src.p(e) as number) - (e.flipped ? 1 : 0)) ** 2);
  return {
    n: sc.length,
    flipRight: up.filter((e) => e.flipped).length, flipCalls: up.length,
    holdRight: down.filter((e) => !e.flipped).length, holdCalls: down.length,
    brier: b.length ? b.reduce((a, c) => a + c, 0) / b.length : null,
  };
}
function callOf(e: MarkovEvent, p: number | null): { call: "flip" | "hold"; right: boolean } | null {
  if (p === null || e.p_flip === null) return null;
  const call = p - e.p_flip > 0.005 ? "flip" : "hold";
  return { call, right: (call === "flip") === e.flipped };
}
function CallCell({ e, p }: { e: MarkovEvent; p: number | null }) {
  const c = callOf(e, p);
  if (!c) return <span className="text-slate-600">—</span>;
  return (
    <span>
      <span className="mr-1 text-slate-400">{c.call === "flip" ? "flip" : "no chg"}</span>
      <HitCell hit={c.right} />
    </span>
  );
}

export function EventLog({ events, pending, summary }: { events: MarkovEvent[]; pending: MarkovResponse["pending"]; summary: MarkovResponse["summary"] }) {
  const recs = SOURCES.map((src) => ({ src, r: record(events, src) }));
  return (
    <section className="mb-6">
      <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
        Event log · since {summary.track_start}
      </div>
      <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Releases scored" value={String(summary.n_events)}
          sub={`${summary.n_pre_registered} pre-registered${summary.n_unscheduled ? ` · +${summary.n_unscheduled} unscheduled` : ""}`} />
        <Stat label="Flipped" value={`${summary.n_flips}/${summary.n_events}`} sub="so the base rate's no-change call was right on the rest" />
        <div className="col-span-2 rounded border border-slate-800 bg-slate-900/60 px-3 py-2 text-[0.68rem] leading-snug text-slate-500 md:col-span-2">
          Every probability source is tracked side by side and none is declared better yet. A call is a flip call when
          its probability is above the base rate for that release, a no-change call when it is equal or below. Brier:
          0 = perfect, 0.25 = coin-flip, lower wins. Roughly 20 scored releases per source are needed before the
          comparison means anything.
        </div>
      </div>

      <div className="mb-3 overflow-x-auto rounded border border-slate-800">
        <table className="w-full border-collapse text-[0.76rem]">
          <thead>
            <tr>
              <th className={`${TH} text-left`}>Source</th>
              <th className={`${TH} text-right`}>Scored</th>
              <th className={`${TH} text-right`}>Flip calls right</th>
              <th className={`${TH} text-right`}>No-change calls right</th>
              <th className={`${TH} text-right`}>Brier</th>
              <th className={`${TH} text-left`}>What it is</th>
            </tr>
          </thead>
          <tbody>
            {recs.map(({ src, r }) => (
              <tr key={src.name} className="border-t border-slate-800/60">
                <td className={`${TD} font-medium text-slate-200`}>{src.name}</td>
                <td className={`${TD} text-right tabular-nums text-slate-300`}>{r.n}</td>
                <td className={`${TD} text-right tabular-nums text-slate-300`}>{r.flipCalls ? `${r.flipRight}/${r.flipCalls}` : "—"}</td>
                <td className={`${TD} text-right tabular-nums text-slate-300`}>{r.holdCalls ? `${r.holdRight}/${r.holdCalls}` : "—"}</td>
                <td className={`${TD} text-right tabular-nums text-slate-300`}>{brier(r.brier)}</td>
                <td className={`${TD} text-[0.68rem] text-slate-500`}>{src.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pending.length > 0 && (
        <div className="mb-3 rounded border border-[var(--cgi-gold)]/40 bg-[var(--cgi-gold-panel)] px-3 py-2 text-xs text-slate-300">
          <span className="font-bold text-[var(--cgi-gold)]">Settling:</span>{" "}
          {pending.map((p) => (
            <span key={`${p.date}-${p.axis}`} className="mr-3">
              {p.date} {p.type} · {p.axis} {p.state_before ? "↑" : "↓"} from {q(p.model, p.quadrant_before)} — the model records the
              print by its effective date at the next 00:25 UTC run; scored by {p.settle_by}.
            </span>
          ))}
        </div>
      )}

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
                <th className={`${TH} text-right`} title="fed funds futures for the FOMC; the experimental classifier for CPI, GDP and SLOOS">Stored</th>
                <th className={`${TH} text-right`} title="the Drivers table figure the brief prints">Drivers</th>
                <th className={`${TH} text-left`}>Outcome</th>
                <th className={`${TH} text-left`}>After</th>
                <th className={`${TH} text-right`}>Brier H / S / D</th>
                <th className={`${TH} text-left`}>Call · stored</th>
                <th className={`${TH} text-left`}>Call · drivers</th>
                <th className={`${TH} text-left`} title="GDP advance and CPI: did the stored consensus imply a flip, and was it right">Consensus</th>
                <th className={`${TH} text-left`}>Registered</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={`${e.date}-${e.axis}`} className="border-t border-slate-800/60 hover:bg-slate-800/40">
                  <td className={`${TD} whitespace-nowrap`}>
                    <span className="font-medium text-slate-200">{e.date}</span>
                    <span className="ml-2 text-slate-400">{e.type}</span>
                    {!e.scheduled && <span className="ml-2 rounded bg-[var(--cgi-gold)]/20 px-1 text-[0.65rem] text-[var(--cgi-gold)]">unscheduled</span>}
                  </td>
                  <td className={`${TD} capitalize text-slate-300`}>
                    {e.axis} <span className="text-slate-500">{e.state_before ? "↑" : "↓"}</span>
                  </td>
                  <td className={`${TD} text-slate-300`} title={qTitle(e.model, e.quadrant_before)}>{q(e.model, e.quadrant_before)}</td>
                  <td className={`${TD} text-right text-slate-200`}>{pct(e.p_flip)}</td>
                  <td className={`${TD} text-right text-slate-200`} title={e.market_source ?? ""}>{pct(e.p_market)}</td>
                  <td className={`${TD} text-right text-slate-200`} title={e.p_drivers_note ?? ""}>{pct(e.p_drivers ?? null)}</td>
                  <td className={`${TD} font-bold ${e.flipped ? "text-[var(--cgi-gold)]" : "text-slate-400"}`} title={e.flip_recorded_on ? `recorded in model-history on ${e.flip_recorded_on}` : ""}>{e.flipped ? "FLIP" : "hold"}</td>
                  <td className={`${TD} text-slate-200`} title={qTitle(e.model, e.quadrant_after)}>{q(e.model, e.quadrant_after)}</td>
                  <td className={`${TD} text-right text-slate-300`}>{brier(e.brier)} <span className="text-slate-600">/</span> {brier(e.brier_market)} <span className="text-slate-600">/</span> {brier(e.brier_drivers ?? null)}</td>
                  <td className={TD} title="above the base rate is a flip call, at or below is a no-change call"><CallCell e={e} p={e.p_market} /></td>
                  <td className={TD} title="above the base rate is a flip call, at or below is a no-change call"><CallCell e={e} p={e.p_drivers ?? null} /></td>
                  <td className={`${TD} text-[0.68rem]`}>
                    {e.consensus_implied == null ? <span className="text-slate-600">—</span> : (
                      <span className={e.consensus_hit ? "text-[var(--cgi-up)]" : "text-[var(--cgi-down)]"}>{e.consensus_implied ? "flip" : "no flip"} · {e.consensus_hit ? "right" : "wrong"}</span>
                    )}
                  </td>
                  <td className={`${TD} text-[0.68rem]`}>
                    {e.pre_registered_on
                      ? <span className={e.pre_registration_note ? "text-[var(--cgi-gold)]" : "text-[var(--cgi-up)]"} title={e.pre_registration_note ?? "both probabilities were in DynamoDB before the release"}>{e.pre_registered_on.replace("T", " ").replace("Z", "Z")}</span>
                      : e.scheduled ? <span className="text-slate-600" title="history recomputed from model-history after the fact; no market number was stored">recomputed</span> : <span className="text-slate-600">—</span>}
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
