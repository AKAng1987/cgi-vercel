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

/** The lean: is the market/drivers probability ABOVE or BELOW the base rate for that state? Above = it leans
 *  toward a flip, below = toward no change. This is the rule used here because the 0.5 cut-off is wrong for
 *  releases whose base rate is far from 0.5 (FOMC 8%, CPI 30%): nothing would ever be called a flip. The history
 *  probability IS the base rate, so it has no lean of its own; only the market/drivers number can lean. */
function lean(e: MarkovEvent): "flip" | "hold" | null {
  if (e.p_market === null || e.p_flip === null) return null;
  const d = e.p_market - e.p_flip;
  if (Math.abs(d) < 0.005) return null;
  return d > 0 ? "flip" : "hold";
}
function leanRight(e: MarkovEvent): boolean | null {
  const l = lean(e);
  return l === null ? null : (l === "flip") === e.flipped;
}
/** What the stored "market" number actually is. For the FOMC it is fed funds futures. For CPI / GDP / SLOOS the
 *  daily job stores an EXPERIMENTAL CLASSIFIER, which is not the Drivers figure the brief and the Upcoming table
 *  show (that one is not stored beforehand yet). They are scored apart so the classifier is never mistaken for
 *  the Drivers number. */
function isFutures(e: MarkovEvent): boolean {
  return (e.market_source ?? "").toLowerCase().includes("futures");
}
function leanRecord(events: MarkovEvent[], futures: boolean) {
  const sc = events.filter((e) => e.scheduled && lean(e) !== null && isFutures(e) === futures);
  const up = sc.filter((e) => lean(e) === "flip");
  const down = sc.filter((e) => lean(e) === "hold");
  return {
    n: sc.length,
    upRight: up.filter((e) => e.flipped).length, up: up.length,
    downRight: down.filter((e) => !e.flipped).length, down: down.length,
  };
}

export function EventLog({ events, pending, summary }: { events: MarkovEvent[]; pending: MarkovResponse["pending"]; summary: MarkovResponse["summary"] }) {
  const fut = leanRecord(events, true);
  const clf = leanRecord(events, false);
  return (
    <section className="mb-6">
      <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
        Event log · since {summary.track_start}
      </div>
      <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Releases scored" value={String(summary.n_events)}
          sub={`${summary.n_pre_registered} pre-registered${summary.n_unscheduled ? ` · +${summary.n_unscheduled} unscheduled` : ""}`} />
        <Stat label="Flips" value={`${summary.n_flips}/${summary.n_events}`} />
        <Stat label="Brier · history" value={brier(summary.brier)} sub="the base rate itself: no lean to score" />
        <Stat label="Brier · market" value={brier(summary.brier_market)} sub={`fed funds futures: above base flipped ${fut.upRight}/${fut.up}, below base held ${fut.downRight}/${fut.down} · experimental classifier: above ${clf.upRight}/${clf.up}, below ${clf.downRight}/${clf.down}`} />
        <div className="rounded border border-slate-800 bg-slate-900/60 px-3 py-2 text-[0.68rem] leading-snug text-slate-500">
          0 = perfect, 0.25 = coin-flip. Lower wins. The lean is simple: the market/drivers probability above its base rate leans toward a flip, below it toward no change; a correct no-change counts as much as a caught flip. History is the base rate, so it cannot lean. For the FOMC the stored number is fed funds futures; for CPI, GDP and SLOOS it is an experimental classifier that the brief never shows, NOT the Drivers figure (which is not stored beforehand yet), so the two are counted apart. Releases with no stored number are not scored.
        </div>
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
                <th className={`${TH} text-right`}>Market</th>
                <th className={`${TH} text-left`}>Outcome</th>
                <th className={`${TH} text-left`}>After</th>
                <th className={`${TH} text-right`}>Brier H / M</th>
                <th className={`${TH} text-left`}>Lean vs base</th>
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
                  <td className={`${TD} font-bold ${e.flipped ? "text-[var(--cgi-gold)]" : "text-slate-400"}`} title={e.flip_recorded_on ? `recorded in model-history on ${e.flip_recorded_on}` : ""}>{e.flipped ? "FLIP" : "hold"}</td>
                  <td className={`${TD} text-slate-200`} title={qTitle(e.model, e.quadrant_after)}>{q(e.model, e.quadrant_after)}</td>
                  <td className={`${TD} text-right text-slate-300`}>{brier(e.brier)} <span className="text-slate-600">/</span> {brier(e.brier_market)}</td>
                  <td className={TD} title="market/drivers probability above the base rate leans flip, below leans no change">
                    <span className="mr-1 text-slate-400">{lean(e) ?? "—"}</span><HitCell hit={leanRight(e)} />
                    {lean(e) !== null && !isFutures(e) && <span className="ml-1 text-[0.62rem] text-slate-600">classifier</span>}
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
