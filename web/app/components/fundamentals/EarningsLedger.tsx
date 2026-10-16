import ledger from "./earnings_facts.json";

type Delta = { ticker: string; metric: string; unit: string; from_q: string; to_q: string; from: number; to: number; change_pct: number | null };
type Claim = { id: string; date: string; thread: string; claim: string; ticker?: string; metric?: string; baseline?: number; direction?: string; check_quarter?: string; result: string | null };
type Facts = Record<string, Record<string, { source: string; filed?: string }>>;

const RESULT_STYLE: Record<string, string> = {
  held: "bg-emerald-950 text-emerald-400",
  "did not hold": "bg-rose-950 text-rose-400",
  flat: "bg-slate-900 text-slate-400",
  "not testable": "bg-slate-900 text-slate-600",
};

/** What the companies said last quarter vs this, and whether past thread claims held.
 *  Company-published figures only, each with its SEC source. Written by scripts/earnings_ledger.py publish. */
export function EarningsLedger() {
  const deltas = ledger.delta as Delta[];
  const claims = ledger.claims as Claim[];
  const facts = ledger.facts as Facts;
  const sc = ledger.scorecard;
  const link = (t: string, q: string) => facts[t]?.[q]?.source;

  return (
    <section className="mb-7">
      <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
        What companies said, quarter on quarter · {deltas.length}
      </div>
      <p className="mb-2 text-[0.7rem] text-slate-500">
        Figures the weekly brief read from each company&apos;s own results release, kept so the next quarter can say
        &ldquo;up from&rdquo; instead of starting cold. Each row links to the filing. Descriptive, not a signal.
      </p>
      {deltas.length === 0 ? (
        <p className="text-[0.72rem] text-slate-600">Nothing stored with two quarters yet.</p>
      ) : (
        <div className="space-y-1">
          {deltas.map((d) => (
            <div key={`${d.ticker}-${d.metric}`} className="flex flex-wrap items-baseline gap-2 border-l-2 border-slate-800 pl-2 text-[0.72rem]">
              <span className="w-12 font-mono text-slate-200">{d.ticker}</span>
              <span className="w-28 text-slate-400">{d.metric.replace(/_/g, " ")}</span>
              <span className="tabular-nums text-slate-300">
                {d.from} → {d.to} {d.unit}
              </span>
              <span className={`tabular-nums ${d.change_pct === null ? "text-slate-600" : d.change_pct > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {d.change_pct === null ? "—" : `${d.change_pct > 0 ? "+" : ""}${d.change_pct}%`}
              </span>
              <span className="text-[0.65rem] text-slate-600">
                {d.from_q} → {d.to_q}
              </span>
              <a href={link(d.ticker, d.to_q)} target="_blank" rel="noreferrer" className="text-[0.65rem] text-slate-600 underline">
                filing
              </a>
            </div>
          ))}
        </div>
      )}

      <div className="mb-2 mt-5 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
        Did the thread claims hold? · {sc.held} of {sc.tested} tested
      </div>
      <p className="mb-2 text-[0.7rem] text-slate-500">
        Each weekly thread records its claim with the figure it started from. When the next quarter is filed the claim
        is scored against the new number. Views that cannot be measured are listed but never counted.
        {" "}{sc.claims} recorded, {sc.waiting} waiting for their quarter, {sc.not_testable} not testable.
      </p>
      {claims.length === 0 ? (
        <p className="text-[0.72rem] text-slate-600">No claims recorded yet. The first Sunday brief that writes threads will add them.</p>
      ) : (
        <div className="space-y-1">
          {claims.map((c) => (
            <div key={c.id} className="flex flex-wrap items-baseline gap-2 border-l-2 border-slate-800 pl-2 text-[0.72rem]">
              <span className="text-slate-600">{c.date}</span>
              <span className="rounded bg-slate-900 px-1.5 text-[0.6rem] text-slate-500">{c.thread}</span>
              <span className="text-slate-300">{c.claim}</span>
              <span className={`rounded px-1.5 text-[0.6rem] ${RESULT_STYLE[c.result ?? ""] ?? "bg-amber-950 text-amber-300"}`}>
                {c.result ?? `waiting for ${c.check_quarter}`}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
