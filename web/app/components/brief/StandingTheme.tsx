import { StandingTheme as ST } from "@/lib/types";

/**
 * Layer 1 -- the slow layer. Set deliberately, reviewed monthly, held for
 * its horizon. It does NOT change when the regime rotates; if the two
 * disagree the page shows the tension rather than resolving it, because
 * that disagreement is information (either the theme is breaking or the
 * rotation is noise).
 */
export function StandingTheme({ themes }: { themes: ST[] }) {
  if (!themes?.length) {
    return (
      <section className="mb-5 rounded border border-dashed border-slate-700 bg-slate-900/40 p-4 text-sm text-slate-500">
        No standing theme set. Promote one from the detector below when a
        candidate earns it — then hold it for its horizon.
      </section>
    );
  }
  return (
    <section className="mb-5 space-y-3">
      {themes.map((t) => {
        const due = t.days_to_review !== null && t.days_to_review <= 7;
        return (
          <div key={t.name} className="rounded border border-slate-700 bg-slate-900/70 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-lg font-bold text-slate-100">{t.name}</h2>
              <div className="text-[0.7rem] uppercase tracking-wide text-slate-500">
                since {t.since} · {t.horizon} horizon ·{" "}
                <span className={due ? "text-[#FCD34D]" : ""}>
                  review {t.review_on}
                  {t.days_to_review !== null && ` (${t.days_to_review}d)`}
                </span>
              </div>
            </div>
            <p className="mt-1 text-sm leading-relaxed text-slate-300">{t.thesis}</p>
            <div className="mt-2 flex flex-wrap items-center gap-1">
              <span className="mr-1 text-[0.62rem] uppercase tracking-wide text-slate-500">tracked</span>
              {t.expressions.map((e) => (
                <span key={e} className="rounded bg-slate-800 px-2 py-0.5 text-[0.7rem] text-slate-300">
                  {e}
                </span>
              ))}
            </div>
            {t.watchlist && t.watchlist.length > 0 && (
              <div className="mt-1 flex flex-wrap items-center gap-1">
                <span className="mr-1 text-[0.62rem] uppercase tracking-wide text-slate-600" title="named in the thesis but not tracked by CGI — it stays ETF-level by design">
                  named
                </span>
                {t.watchlist.map((e) => (
                  <span key={e} className="rounded border border-slate-800 px-2 py-0.5 text-[0.7rem] text-slate-500">
                    {e}
                  </span>
                ))}
              </div>
            )}
            {t.exit_rule && (
              <p className="mt-2 text-[0.7rem] text-slate-500">
                <span className="text-slate-400">Exit:</span> {t.exit_rule}
              </p>
            )}
          </div>
        );
      })}
    </section>
  );
}
