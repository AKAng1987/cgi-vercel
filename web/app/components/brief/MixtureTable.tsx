"use client";

import { MixtureResponse, MixtureRow } from "@/lib/types";
import { TvList } from "@/lib/tvLists";
import { TvListLink } from "../TvListLink";

/**
 * Each ticker's average return in the regime we are in vs the one the next
 * release could land us in, weighted by how likely the flip is.
 *
 * The column that matters is SPREAD, not the mixture: two names can share a
 * mixture for opposite reasons -- one pays either way, the other earns its
 * whole edge on the flip NOT happening. A ranked list hides that. "reverses"
 * marks the extreme case, where the sign itself changes with the release.
 *
 * Rows are clickable: the chart lives in EdgeStrip, which owns the selection and
 * passes it down, so one chart serves the cards and this table. n sits beside every
 * number because both samples are a handful of occurrences and a figure without its
 * count reads as more certain than it is.
 */
const TOP = 20;

function pct(v: number | null) {
  if (v === null) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function tone(v: number | null) {
  if (v === null || v === 0) return undefined;
  return v > 0 ? "var(--cgi-up)" : "var(--cgi-down)";
}

export function MixtureTable({
  data,
  selected,
  onSelect,
  tvList,
}: {
  data: MixtureResponse;
  selected?: string | null;
  /** Called with the CGI ticker and the VERIFIED TradingView symbol (falls back to the ticker). */
  onSelect?: (ticker: string, tvSymbol: string) => void;
  /** The TradingView list for the regime the next release could land us in. */
  tvList?: TvList;
}) {
  if (data.error || data.rows.length === 0) return null;

  const rows: MixtureRow[] = data.rows.slice(0, TOP);
  const reversing = data.rows.filter((r) => r.sign_flips).length;
  const pHist = (data.p_flip_history * 100).toFixed(0);
  const pMkt = data.p_flip_market === null ? null : (data.p_flip_market * 100).toFixed(0);
  // "Market" only when it is a market price; for inflation/growth/credit it is the in-sample
  // Drivers table and calling it "market" would put a descriptive table beside real pricing.
  const second = (data.market_label ?? "Market").toLowerCase();

  return (
    <section className="mb-6">
      <div className="mb-1 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
          Across the next release
        </div>
        <div className="text-xs text-slate-500">
          {data.release.type} {data.release.date} · {data.regime_now} → {data.regime_if_flips} if{" "}
          {data.release.axis} flips · P(flip) {pHist}% history
          {pMkt !== null && <> · {pMkt}% {second}</>}
        </div>
      </div>
      <div className="mb-2 text-xs text-slate-500">
        {reversing} of {data.n_tickers} tickers change sign if it flips. Two small samples, weighted —
        not a forecast.{onSelect && " Click a row to chart it."}
        {tvList && <> · <TvListLink list={tvList} label="TradingView list if it flips" /></>}
      </div>

      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="w-full border-collapse text-[0.76rem]">
          <thead>
            <tr>
              {["Ticker", "Now", "n", "If flips", "n", "Mixture", `@ ${second}`, "Spread", ""].map((h, i) => (
                <th
                  key={`${h}${i}`}
                  className={`bg-[var(--cgi-surface-alt)] px-1.5 py-1 text-[0.68rem] uppercase tracking-wide text-slate-400 ${
                    i === 0 ? "text-left" : "text-right"
                  }`}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.ticker}
                onClick={onSelect ? () => onSelect(r.ticker, r.tv_symbol ?? r.ticker) : undefined}
                onKeyDown={
                  onSelect
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onSelect(r.ticker, r.tv_symbol ?? r.ticker);
                        }
                      }
                    : undefined
                }
                tabIndex={onSelect ? 0 : undefined}
                title={onSelect ? `chart ${r.tv_symbol ?? r.ticker}` : undefined}
                className={`${onSelect ? "cursor-pointer hover:bg-slate-800/50" : ""} ${
                  selected === r.ticker ? "bg-slate-800/70" : ""
                }`}
              >
                <td className="px-1.5 py-0.5 font-medium text-slate-100">{r.ticker}</td>
                <td className="px-1.5 py-0.5 text-right" style={{ color: tone(r.ret_now) }}>{pct(r.ret_now)}</td>
                <td className="px-1.5 py-0.5 text-right text-slate-500">{r.n_now}</td>
                <td className="px-1.5 py-0.5 text-right" style={{ color: tone(r.ret_flip) }}>{pct(r.ret_flip)}</td>
                <td className="px-1.5 py-0.5 text-right text-slate-500">{r.n_flip}</td>
                <td className="px-1.5 py-0.5 text-right font-bold text-slate-100">{pct(r.mix_hist)}</td>
                <td className="px-1.5 py-0.5 text-right text-slate-400">{pct(r.mix_market)}</td>
                <td className="px-1.5 py-0.5 text-right text-slate-300">{r.spread.toFixed(2)}</td>
                <td className="px-1.5 py-0.5 text-right">
                  {r.sign_flips && (
                    <span className="rounded border border-[var(--cgi-warn)] px-1 text-[0.62rem] uppercase tracking-wide text-[color:var(--cgi-warn)]">
                      reverses
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
