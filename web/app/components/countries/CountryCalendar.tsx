import { CalendarEvent, RegimeCountry } from "@/lib/types";

const KIND: Record<CalendarEvent["kind"], string> = { rate: "rate", cpi: "CPI", gdp: "GDP" };

/** TradingView lists GDP twice (year on year and quarter on quarter); one line per country, kind and day is enough. */
function unique(events: CalendarEvent[]): CalendarEvent[] {
  const seen = new Set<string>();
  return events.filter((e) => {
    const k = `${e.country}|${e.kind}|${e.date}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
}

function detail(e: CalendarEvent): string {
  const f = (v: number | null) => (v === null ? null : String(v));
  if (e.kind === "rate") {
    return [f(e.previous) && `prev ${f(e.previous)}`, f(e.forecast) && `exp ${f(e.forecast)}`].filter(Boolean).join(" · ");
  }
  return [e.period, f(e.previous) && `prev ${f(e.previous)}`].filter(Boolean).join(" · ");
}

/** "released, not loaded": the calendar says it printed, CGI's stored series has not reached that period yet. */
function missing(e: CalendarEvent): boolean {
  return e.days_to_go < 0 && !!e.series && e.loaded === false;
}

/**
 * The next releases for every country on the page, by day. Rate decisions are bold (they move the policy rate, the
 * curve and the regime); inflation and GDP prints are plain. A print that has happened but is not yet in CGI's series
 * shows amber, which is the check that would have caught the Philippine rate sitting at 5.0% after the 22 Oct hike.
 */
export function CalendarStrip({ countries, asOf }: { countries: RegimeCountry[]; asOf?: string | null }) {
  const events = unique(countries.flatMap((c) => c.calendar ?? []))
    .filter((e) => e.days_to_go >= -7 && e.days_to_go <= 31)
    .sort((a, b) => a.date.localeCompare(b.date) || a.country.localeCompare(b.country));
  if (!events.length) {
    return (
      <section className="space-y-1">
        <div className="text-[0.7rem] uppercase tracking-wide text-slate-500">release calendar</div>
        <p className="text-[0.75rem] text-slate-600">
          No calendar stored yet. The refresh routine posts it once a week from TradingView.
        </p>
      </section>
    );
  }
  const byDate = new Map<string, CalendarEvent[]>();
  for (const e of events) byDate.set(e.date, [...(byDate.get(e.date) ?? []), e]);
  const late = events.filter(missing);

  return (
    <section className="space-y-1">
      <div className="text-[0.7rem] uppercase tracking-wide text-slate-500">
        release calendar
        <span className="ml-2 normal-case text-slate-600">
          rates, inflation, GDP · next 30 days · from TradingView{asOf ? `, posted ${asOf.slice(0, 10)}` : ""} · bold = rate decision
        </span>
      </div>
      {late.length > 0 && (
        <p className="text-[0.72rem] text-amber-300">
          Released but not yet in CGI: {late.map((e) => `${e.country} ${KIND[e.kind]} (${e.date.slice(5)})`).join(", ")}
        </p>
      )}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {Array.from(byDate.entries()).map(([date, evs]) => {
          const d = evs[0].days_to_go;
          const rate = evs.some((e) => e.kind === "rate");
          return (
            <div
              key={date}
              className={`min-w-[8.5rem] shrink-0 rounded border px-2 py-1.5 ${rate ? "border-slate-600 bg-slate-900/80" : "border-slate-800 bg-slate-900/40"}`}
            >
              <div className="flex items-baseline justify-between text-[0.68rem]">
                <span className={rate ? "font-bold text-slate-100" : "text-slate-300"}>{date.slice(5)}</span>
                <span className="text-slate-600">{d === 0 ? "today" : d < 0 ? `${-d}d ago` : d === 1 ? "tmrw" : `+${d}d`}</span>
              </div>
              {evs.map((e, i) => (
                <div
                  key={`${e.country}-${e.kind}-${i}`}
                  className={`mt-0.5 text-[0.7rem] leading-tight ${missing(e) ? "text-amber-300" : e.kind === "rate" ? "font-bold text-slate-100" : "text-slate-400"}`}
                  title={e.title}
                >
                  {e.country} {KIND[e.kind]}
                  {detail(e) && <span className="ml-1 font-normal text-slate-500">{detail(e)}</span>}
                </div>
              ))}
            </div>
          );
        })}
      </div>
      <p className="text-[0.65rem] leading-relaxed text-slate-600">
        TradingView looks about 31 days ahead, so a central-bank meeting appears about a month before it. Money supply, loans
        and central-bank balance sheets have no calendar and are loaded in their usual windows. A decision date is the
        announcement; CGI&apos;s series is stamped with the month.
      </p>
    </section>
  );
}

/** One line under a country's macro figures: its next releases, nearest first, amber if one has printed and is not loaded. */
export function CalLine({ events }: { events?: CalendarEvent[] }) {
  const ev = unique(events ?? []).filter((e) => e.days_to_go >= -7);
  if (!ev.length) return null;
  const shown = ev.slice(0, 3);
  return (
    <div className="pt-0.5 text-[0.68rem] text-slate-500">
      next{" "}
      {shown.map((e, i) => (
        <span key={`${e.kind}-${e.date}-${i}`} className={missing(e) ? "text-amber-300" : ""}>
          {i > 0 && " · "}
          {KIND[e.kind]} {e.date.slice(5)}
          {e.kind === "rate" && e.forecast !== null ? ` (exp ${e.forecast})` : ""}
          {missing(e) ? " not loaded" : ""}
        </span>
      ))}
    </div>
  );
}
