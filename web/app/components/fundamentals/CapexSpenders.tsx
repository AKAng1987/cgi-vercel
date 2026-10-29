import type { CapexSpender } from "@/lib/types";

/** A ratio (1.33) shown as a percentage (133%). */
function pct(n: number | null) {
  return n === null ? <span className="text-slate-600">—</span> : <>{(n * 100).toFixed(0)}%</>;
}

/** The biggest spenders by trailing-twelve-month capex, with how they fund it. */
export function CapexSpenders({ top, top5Share }: { top: CapexSpender[]; top5Share: number | null }) {
  return (
    <div>
      <div className="mb-1 text-[0.7rem] text-slate-500">
        Top {top.length} by trailing-twelve-month capex
        {top5Share !== null && <> · the five largest are {top5Share}% of the S&amp;P 500 total</>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[0.72rem]">
          <thead>
            <tr className="text-left text-[0.6rem] uppercase tracking-wider text-slate-500">
              <th className="py-1 pr-2">Company</th>
              <th className="pr-2">Sector</th>
              <th className="pr-2 text-right">TTM $bn</th>
              <th className="pr-2 text-right">Last qtr $bn</th>
              <th className="pr-2 text-right">YoY</th>
              <th className="pr-2 text-right">Capex / op. cash flow</th>
              <th className="pr-2 text-right">Capex / revenue</th>
            </tr>
          </thead>
          <tbody>
            {top.map((r) => (
              <tr key={r.ticker} className="border-t border-slate-900">
                <td className="py-1 pr-2">
                  <span className="font-mono text-slate-200">{r.ticker}</span>
                </td>
                <td className="pr-2 text-slate-400">{r.sector}</td>
                <td className="pr-2 text-right tabular-nums text-slate-200">{r.capex_ttm_b.toFixed(1)}</td>
                <td className="pr-2 text-right tabular-nums text-slate-300">{r.capex_last_q_b.toFixed(1)}</td>
                <td className="pr-2 text-right tabular-nums text-slate-300">
                  {r.yoy_pct === null ? <span className="text-slate-600">—</span> : `${r.yoy_pct > 0 ? "+" : ""}${r.yoy_pct.toFixed(0)}%`}
                </td>
                <td className="pr-2 text-right tabular-nums">
                  {r.capex_to_ocf === null ? (
                    <span className="text-slate-600">—</span>
                  ) : (
                    <span className={r.outspends_cash_flow ? "text-amber-300" : "text-slate-300"}>
                      {pct(r.capex_to_ocf)}
                      {r.outspends_cash_flow ? " · outspends" : ""}
                    </span>
                  )}
                </td>
                <td className="pr-2 text-right tabular-nums text-slate-300">{pct(r.capex_to_revenue)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
