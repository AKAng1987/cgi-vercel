import { PhBuyback, PhEarningsNext, PhResult } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { PhTicker } from "./PhSelect";
import { dayLabel, edgeLink, num, peso, pct } from "./phFormat";

function Yoy({ v, loss, swing }: { v: number | null; loss?: boolean; swing?: boolean }) {
  if (loss) return <span className="text-slate-400">loss</span>;
  if (swing) return <span className="text-slate-300">swing to profit</span>;
  return <span style={{ color: pctColor(v) }}>{pct(v)}</span>;
}

/** Reported results (read from each 17-Q / 17-A on EDGE), expected reporting dates, and the buy-back board. */
export function PhEarnings({ next, reported, buybacks }: { next: PhEarningsNext[]; reported: PhResult[]; buybacks: PhBuyback[] }) {
  return (
    <section className="mb-4 grid gap-4 xl:grid-cols-[1.5fr_1fr]">
      <div className="rounded border border-slate-800 bg-slate-900/50 p-3">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Earnings · filed in the last 60 days</div>
        <div className="max-h-[26rem] overflow-y-auto pr-1">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[0.58rem] uppercase text-slate-600">
                <th className="pb-1 font-normal">Filed</th><th className="pb-1 font-normal">Stock</th><th className="pb-1 text-right font-normal">Revenue</th>
                <th className="pb-1 text-right font-normal">y/y</th><th className="pb-1 text-right font-normal">Net income*</th><th className="pb-1 text-right font-normal">y/y</th>
                <th className="pb-1 text-right font-normal">EPS</th><th className="pb-1 text-right font-normal" title="share price over the last month">1M px</th><th className="pb-1" />
              </tr>
            </thead>
            <tbody>
              {reported.map((r) => (
                <tr key={r.edge_no} className="border-t border-slate-800/70">
                  <td className="py-1 pr-2 tabular-nums text-slate-500">{dayLabel(r.announced)}</td>
                  <td className="py-1 pr-2" title={r.ind ?? ""}><PhTicker s={r.s} list={reported.map((x) => x.s)}>{r.s}</PhTicker><span className="ml-1 text-[0.58rem] text-slate-500">{r.kind === "A" ? "FY" : `Q to ${r.period.slice(5, 7)}/${r.period.slice(2, 4)}`}</span></td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-300">{r.revenue ? peso(r.revenue) : "—"}</td>
                  <td className="py-1 pr-2 text-right tabular-nums" style={{ color: pctColor(r.rev_yoy) }}>{pct(r.rev_yoy)}</td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-300">{peso(r.ni)}</td>
                  <td className="py-1 pr-2 text-right tabular-nums"><Yoy v={r.ni_yoy} loss={r.ni_loss} swing={r.ni_swing} /></td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-400">{r.eps != null ? r.eps.toFixed(Math.abs(r.eps) >= 1 ? 2 : 3) : "—"}</td>
                  <td className="py-1 pr-2 text-right tabular-nums" style={{ color: pctColor(r.ret_1m) }}>{pct(r.ret_1m, 0)}</td>
                  <td className="py-1 text-right"><a className="text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={edgeLink(r.edge_no)}>EDGE ↗</a></td>
                </tr>
              ))}
              {reported.length === 0 && <tr><td className="py-3 text-slate-500" colSpan={9}>no filings read yet</td></tr>}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[0.62rem] leading-relaxed text-slate-600">
          *Attributable to the parent. y/y compares with the same period a year earlier in the filing itself (3 months for a quarterly report); a loss or a swing from a loss shows in words, not a percentage.
          Beat or miss against forecasts is not shown: EDGE carries none.
        </p>
      </div>
      <div className="space-y-4">
        <div className="rounded border border-slate-800 bg-slate-900/50 p-3">
          <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Expected to report · next 5 weeks</div>
          <ul className="max-h-48 space-y-0.5 overflow-y-auto text-xs">
            {next.map((e) => (
              <li key={e.s} className="flex items-baseline gap-2" title={e.basis}>
                <span className="w-14 tabular-nums text-slate-500">{dayLabel(e.date)}</span>
                <span className="w-14"><PhTicker s={e.s} list={next.map((x) => x.s)}>{e.s}</PhTicker></span>
                <span className="text-slate-500">{e.ind ?? ""}{e.psei ? " · PSEi" : ""}</span>
              </li>
            ))}
            {next.length === 0 && <li className="text-slate-500">none estimated</li>}
          </ul>
          <p className="mt-1 text-[0.62rem] text-slate-600">An estimate: the date each company filed this report last year plus a year. EDGE publishes no calendar.</p>
        </div>
        <div className="rounded border border-slate-800 bg-slate-900/50 p-3">
          <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Buy-backs · active in 60 days</div>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[0.58rem] uppercase text-slate-600">
                <th className="pb-1 font-normal">Stock</th><th className="pb-1 text-right font-normal">30d value</th><th className="pb-1 text-right font-normal">% of shares</th>
                <th className="pb-1 text-right font-normal">Cumulative</th><th className="pb-1 text-right font-normal">Last</th><th className="pb-1" />
              </tr>
            </thead>
            <tbody>
              {buybacks.map((b) => (
                <tr key={b.s} className="border-t border-slate-800/70">
                  <td className="py-1 pr-2"><PhTicker s={b.s} list={buybacks.map((x) => x.s)}>{b.s}</PhTicker></td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-300">{b.value_30d ? peso(b.value_30d) : "—"}</td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-400">{b.pct_outstanding_30d != null ? `${b.pct_outstanding_30d.toFixed(3)}%` : "—"}</td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-500">{b.cumulative ? `${num(b.cumulative / 1e6, 1)}M sh` : "—"}</td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-500">{dayLabel(b.last_date)}</td>
                  <td className="py-1 text-right"><a className="text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={edgeLink(b.edge_no)}>↗</a></td>
                </tr>
              ))}
              {buybacks.length === 0 && <tr><td className="py-3 text-slate-500" colSpan={6}>none</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
