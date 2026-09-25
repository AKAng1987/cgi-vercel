import { BriefChange } from "@/lib/types";

/**
 * "What crossed" — the one thing the brief had that LIVE did not.
 *
 * It sits at the BOTTOM of LIVE deliberately. The page leads with the slow
 * layers (standing theme, then themes in force); what crossed overnight is the
 * fast, daily layer, and opening with it would make LIVE start on exactly the
 * noise the daily scan was moved to TAPE to avoid.
 *
 * Visual weight is DERIVED, not decided: `rate_per_year` is measured from
 * CGI's own history, so a compass flip (2.5/yr) reads louder than a breadth
 * colour change (32.1/yr) because it genuinely is rarer.
 */
function weight(c: BriefChange) {
  if (c.push) return "border-amber-500 bg-amber-950/20";
  if ((c.rate_per_year ?? 99) <= 12) return "border-slate-600";
  return "border-slate-800";
}

export function ChangeStrip({
  changes,
  headline,
  nothingCrossed,
  covers,
}: {
  changes: BriefChange[];
  headline: string;
  nothingCrossed: boolean;
  covers: string;
}) {
  return (
    <section className="mb-6">
      <div className="mb-2 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
          What crossed
        </div>
        <div className="text-xs text-slate-500">
          {covers} · ranked by how rarely each rule fires — measured, not judged
        </div>
      </div>

      {nothingCrossed ? (
        <p className="text-[0.75rem] leading-relaxed text-slate-400">
          <span className="text-slate-200">Nothing crossed.</span> No rule changed state, which
          is the normal outcome — a page that finds something to say every morning is how a
          weeks-to-months process gets traded daily.
        </p>
      ) : (
        <>
          <div className="mb-2 text-[0.72rem] text-slate-400">{headline}</div>
          <div className="space-y-1">
            {changes.map((c, i) => (
              <div key={i} className={`border-l-2 py-1.5 pl-3 ${weight(c)}`}>
                <div className="flex flex-wrap items-baseline gap-2">
                  {c.push && (
                    <span className="rounded bg-amber-500 px-1.5 text-[0.58rem] font-bold text-amber-950">
                      ACT
                    </span>
                  )}
                  <span className="text-[0.8rem] font-medium text-slate-100">{c.title}</span>
                  {c.rate_per_year && (
                    <span
                      className="text-[0.6rem] tabular-nums text-slate-500"
                      title={`Fires about ${c.rate_per_year} times a year, measured from CGI's own history`}
                    >
                      {c.rate_per_year}/yr
                    </span>
                  )}
                  {c.when && <span className="text-[0.6rem] text-slate-600">{c.when}</span>}
                </div>
                <div className="mt-0.5 text-[0.72rem] leading-relaxed text-slate-400">
                  {c.detail}
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
