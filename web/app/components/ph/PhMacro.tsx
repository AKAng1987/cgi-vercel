import { PhCalEvent, PhMacroPoint, PhResponse } from "@/lib/types";
import { dayLabel, num, pct } from "./phFormat";

const ORDER = ["policy", "cpi", "core", "cpi_mom", "gdp_yoy", "gdp_qoq", "unemployment", "loans", "ip", "pmi", "remit", "reserves", "m2"];
// Which direction is "good" is not for the page to say: arrows only, in the neutral tone, plus the size of the move.

function headline(p: PhMacroPoint): { main: string; sub: string } {
  if (p.kind === "level") {
    const big = p.unit === "USD" ? `$${(p.latest / 1e9).toFixed(2)}B` : num(p.latest / 1e9, 0) + "B";
    return { main: p.yoy_pct != null ? pct(p.yoy_pct) + " y/y" : big, sub: p.yoy_pct != null ? `level ${big}` : "level only" };
  }
  const unit = p.unit === "%" ? "%" : "";
  return { main: `${p.latest.toFixed(2)}${unit}`, sub: p.prior != null ? `was ${p.prior.toFixed(2)}${unit}` : "" };
}

function Card({ p }: { p: PhMacroPoint }) {
  const h = headline(p);
  const arrow = p.direction === "up" ? "↑" : p.direction === "down" ? "↓" : "→";
  return (
    <div className="rounded border border-slate-800 bg-slate-900/40 p-2">
      <div className="text-[0.62rem] uppercase tracking-wide text-slate-500">{p.label}</div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-lg font-bold text-slate-100">{h.main}</span>
        {p.direction && <span className="text-sm text-slate-400">{arrow}</span>}
      </div>
      <div className="text-[0.65rem] text-slate-500">{h.sub}{h.sub ? " · " : ""}{p.as_of.slice(0, 7)}{p.age_days != null && p.age_days > 75 ? ` (${p.age_days}d old)` : ""}</div>
    </div>
  );
}

const KIND_LABEL: Record<string, string> = {
  rate: "BSP decision", cpi: "Inflation y/y", cpi_core: "Core inflation", cpi_mom: "Inflation m/m", gdp: "GDP", labor: "Unemployment",
  pmi: "Manufacturing PMI", ip: "Industrial production", remit: "Remittances", reserves: "FX reserves",
};

function Event({ e }: { e: PhCalEvent }) {
  const past = e.days_to_go < 0;
  const late = e.loaded === false;
  return (
    <li className={`flex items-baseline gap-2 text-xs ${late ? "text-amber-300" : past ? "text-slate-500" : "text-slate-300"}`}>
      <span className="w-14 shrink-0 tabular-nums text-slate-500">{dayLabel(e.date)}</span>
      <span className="font-medium">{e.kind === "gdp" ? (/qoq/i.test(e.title) ? "GDP q/q" : "GDP y/y") : (KIND_LABEL[e.kind] ?? e.kind)}{e.period ? ` ${e.period}` : ""}</span>
      <span className="text-slate-500">
        {e.previous != null ? `prev ${e.previous}` : ""}{e.forecast != null ? ` · exp ${e.forecast}` : ""}{e.actual != null ? ` · actual ${e.actual}` : ""}
      </span>
      {late && <span className="text-[0.65rem]">released, not yet in CGI</span>}
    </li>
  );
}

export function PhMacro({ d }: { d: PhResponse }) {
  const pts = ORDER.map((k) => d.macro[k]).filter(Boolean);
  const cal = d.calendar.events;
  return (
    <section className="mb-4 grid gap-4 lg:grid-cols-[2fr_1fr]">
      <div className="rounded border border-slate-800 bg-slate-900/50 p-3">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Philippine macro</div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">{pts.map((p) => <Card key={p.symbol} p={p} />)}</div>
        <p className="mt-2 text-[0.65rem] leading-relaxed text-slate-600">
          Arrows show the move since the prior print, not good or bad. Bank lending is loans to the private sector (level, year on year). The
          manufacturing PMI is S&amp;P Global&apos;s headline, kept from the calendar&apos;s actuals, so its history starts at the first release CGI saw.
        </p>
      </div>
      <div className="rounded border border-slate-800 bg-slate-900/50 p-3">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">PH calendar</div>
        {d.calendar.late.length > 0 && (
          <p className="mb-2 rounded border border-amber-800 bg-amber-950/40 p-1.5 text-[0.7rem] text-amber-300">
            Released but not yet loaded: {d.calendar.late.join(", ")}
          </p>
        )}
        <ul className="space-y-1">
          {d.header.bsp.next && (
            <li className="flex items-baseline gap-2 text-xs font-bold text-slate-100">
              <span className="w-14 shrink-0 tabular-nums text-slate-400">{dayLabel(d.header.bsp.next)}</span>BSP Monetary Board meeting
            </li>
          )}
          {cal.length === 0 && <li className="text-xs text-slate-500">calendar not loaded yet</li>}
          {cal.map((e, i) => <Event key={`${e.kind}-${e.date}-${i}`} e={e} />)}
        </ul>
        <p className="mt-2 text-[0.62rem] text-slate-600">{d.calendar.note}</p>
      </div>
    </section>
  );
}
