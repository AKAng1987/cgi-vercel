import { PhPinned as Pinned } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { PhTicker } from "./PhSelect";
import { dayLabel, edgeLink, num, peso, pct, price } from "./phFormat";

/** Names asked for by name (COL, CTS): shown whatever they trade, with their latest filings. */
export function PhPinnedStrip({ rows }: { rows: Pinned[] }) {
  if (!rows.length) return null;
  const list = rows.map((r) => r.s);
  return (
    <section className="mb-4 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Pinned names</div>
      <div className="grid gap-4 md:grid-cols-2">
        {rows.map((r) => (
          <div key={r.s} className="rounded border border-slate-800 bg-slate-900/40 p-2 text-xs">
            <div className="flex flex-wrap items-baseline gap-2">
              <PhTicker s={r.s} list={list} className="text-base font-bold text-slate-100 hover:underline">{r.s}</PhTicker>
              <span className="text-slate-400">{r.name}</span>
              <span className="ml-auto tabular-nums text-slate-100">{price(r.c)}</span>
            </div>
            <div className="mt-1 flex flex-wrap gap-x-4 tabular-nums">
              {([["1W", r.w], ["1M", r.m], ["3M", r.q], ["YTD", r.y]] as const).map(([l, v]) => (
                <span key={l}><span className="text-slate-600">{l} </span><span style={{ color: pctColor(v) }}>{pct(v)}</span></span>
              ))}
              <span className="text-slate-500">{peso(r.v30)} a day{r.liquid ? "" : " · below ₱5M"}</span>
            </div>
            {r.expected_report && <div className="mt-1 text-slate-400">expected to report ~{dayLabel(r.expected_report.date)}</div>}
            {r.last_result && (
              <div className="mt-1 text-slate-300">
                latest {r.last_result.kind === "A" ? "FY" : `Q to ${r.last_result.period.slice(5, 7)}/${r.last_result.period.slice(2, 4)}`}: revenue{" "}
                <span style={{ color: pctColor(r.last_result.rev_yoy) }}>{pct(r.last_result.rev_yoy)}</span>, net income{" "}
                {r.last_result.ni_loss ? "loss" : r.last_result.ni_swing ? "swing to profit" : <span style={{ color: pctColor(r.last_result.ni_yoy) }}>{pct(r.last_result.ni_yoy)}</span>}
                <a className="ml-2 text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={edgeLink(r.last_result.edge_no)}>EDGE ↗</a>
              </div>
            )}
            {r.last_buyback && <div className="mt-1 text-emerald-300">buy-back {dayLabel(r.last_buyback.report_date)}: {num(r.last_buyback.shares)} sh · {peso(r.last_buyback.value)}</div>}
            <ul className="mt-1 space-y-0.5">
              {r.disclosures.map((d) => (
                <li key={d.edge_no} className="flex gap-2"><span className="w-12 shrink-0 tabular-nums text-slate-500">{dayLabel(d.announced)}</span>
                  <span className="text-slate-300">{d.subject ?? d.title}
                    {d.insider && <span className={`ml-1 ${d.insider.side === "bought" ? "text-emerald-300" : "text-red-300"}`}>{d.insider.side} {num(Math.abs(d.insider.net_shares))}</span>}</span>
                  <a className="ml-auto shrink-0 text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={edgeLink(d.edge_no)}>↗</a></li>
              ))}
              {r.disclosures.length === 0 && <li className="text-slate-600">no disclosures in the stored window</li>}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
