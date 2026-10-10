import type { ErpBlock } from "@/lib/types";
import { ErpChart } from "./ErpChart";

/**
 * Valuation cushion: Damodaran's implied equity risk premium against the 10-year T-bond rate he subtracts.
 * Descriptive. It says how stocks are priced against bonds, not what they will earn, and it moves with
 * price, the bond rate and analysts' cash-flow forecasts, so part of it is the same information as price.
 *
 * The chart (with its S&P 500, T-bond and gap switches) is ErpChart, a small client component.
 */
const pct = (v: number | null | undefined, dp = 2) => (v === null || v === undefined ? "n/a" : `${v.toFixed(dp)}%`);
const pts = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)} pts`;

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
      <div className="text-[0.62rem] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-2xl font-bold tabular-nums text-slate-100">{value}</div>
      {sub && <div className="text-[0.65rem] text-slate-500">{sub}</div>}
    </div>
  );
}

export function ErpGauge({ e }: { e?: ErpBlock }) {
  if (!e) return null;
  if (!e.available) {
    return (
      <div>
        <div className="mb-2 text-[0.72rem] uppercase tracking-wide text-slate-400">Valuation cushion (equity risk premium)</div>
        <p className="text-xs text-slate-500">Not available: {e.why ?? "no data"}.</p>
      </div>
    );
  }
  const c = e.current;
  const s = e.since_2008;
  const rankText =
    s.erp_rank_lowest === 1 ? `lowest of ${s.n_months} months since Sep 2008` : `${s.erp_rank_lowest}th lowest of ${s.n_months} months since Sep 2008`;
  const bandText = s.band === "bottom10" ? "bottom 10% of months since 2008" : s.band === "top10" ? "top 10% of months since 2008" : "middle of the range since 2008";
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.72rem] uppercase tracking-wide text-slate-400">Valuation cushion (equity risk premium)</div>
        <div className="text-[0.66rem] text-slate-500">{e.label} · as of {e.as_of}</div>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile label="Implied ERP" value={pct(c.erp)} sub={`${rankText} · ${bandText}`} />
        <Tile label="10-year T-bond rate" value={pct(c.tbond)} sub="the safe return he subtracts" />
        <Tile label="ERP minus T-bond" value={pts(c.gap)} sub={e.dotcom_1999 && e.dotcom_1999.gap !== null ? `1999: ${pts(e.dotcom_1999.gap)}` : undefined} />
        <Tile
          label="High-yield spread"
          value={e.hy_spread ? `${Math.round(e.hy_spread.bp)} bp` : "n/a"}
          sub={e.hy_spread ? `${e.hy_spread.percentile_since_2008}th percentile since 2008 · the bond market's own premium` : "credit-market premium, not available"}
        />
      </div>
      <p className="mt-2 max-w-4xl text-[0.72rem] leading-relaxed text-slate-400">
        {e.last_this_low ? <>The premium was last this thin at the end of {e.last_this_low.date.slice(0, 4)} ({pct(e.last_this_low.erp)}). </> : null}
        {e.dotcom_1999 ? <>At the 1999 low it was {pct(e.dotcom_1999.erp)} against a {pct(e.dotcom_1999.tbond)} T-bond. </> : null}
        Since 2008 it has ranged from {pct(s.low.erp)} ({s.low.date.slice(0, 7)}) to {pct(s.high.erp)} ({s.high.date.slice(0, 7)}), median {pct(s.median_erp)}.
        {c.expected_return !== null && c.expected_return !== undefined ? <> Expected return on stocks implied by the same model: {pct(c.expected_return)}.</> : null}
      </p>
      <ErpChart e={e} />
      {e.freshness.behind && (
        <p className="mt-1 text-[0.66rem] text-amber-400">
          Waiting for this month&apos;s update: newest month held is {e.freshness.newest_month}, expected {e.freshness.expected_month}.
        </p>
      )}
      <p className="mt-2 max-w-4xl text-[0.66rem] leading-relaxed text-slate-600">
        Source: {e.source}. {e.caveats.join(" ")}
      </p>
    </div>
  );
}
