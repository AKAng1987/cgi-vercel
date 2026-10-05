"use client";

import { useState } from "react";
import { BacktestRow, MixtureResponse } from "@/lib/types";
import { TradingViewChart } from "../TradingViewChart";
import { MixtureTable } from "./MixtureTable";
import { TvList } from "@/lib/tvLists";
import { TvListLink } from "../TvListLink";

/**
 * Edge cards for the current regime, and the "across the next release" table,
 * both clickable to chart. The chart lives here rather than as a sibling so a click
 * can drive it without lifting state into the server component.
 *
 * Selection is {ticker, symbol}: the ticker highlights the card/row, the symbol is
 * what the chart is given. They differ for our custom labels (RICE is rough-rice
 * futures, CBOT:ZR1!, not a stock), so the chart is handed the verified TradingView
 * symbol and only falls back to the bare ticker when none is known.
 */
export function EdgeStrip({
  best,
  worst,
  cq,
  gq,
  mixture,
  tvNow,
  tvFlip,
}: {
  best: BacktestRow[];
  worst: BacktestRow[];
  cq: number;
  gq: number;
  mixture?: MixtureResponse | null;
  /** TradingView lists for the current regime / the regime if the next release flips. */
  tvNow?: TvList;
  tvFlip?: TvList;
}) {
  const [sel, setSel] = useState({ ticker: "SPY", symbol: "AMEX:SPY" });
  const select = (ticker: string, symbol: string) => setSel({ ticker, symbol });

  const Card = ({ r, dim }: { r: BacktestRow; dim?: boolean }) => (
    <button
      onClick={() => select(r.ticker, r.tv_symbol ?? r.ticker)}
      className={`rounded border px-2.5 py-1.5 text-left transition ${
        sel.ticker === r.ticker
          ? "border-[var(--cgi-accent)] bg-slate-800"
          : dim
          ? "border-slate-800/60 bg-slate-950/60 hover:border-slate-700"
          : "border-slate-800 bg-slate-900/60 hover:border-slate-600"
      }`}
    >
      <div className={`text-sm font-semibold ${dim ? "text-slate-400" : "text-slate-100"}`}>{r.ticker}</div>
      <div className={`text-[0.65rem] ${dim ? "text-slate-600" : "text-slate-500"}`}>
        edge {r.edge!.toFixed(2)} · {r.hit_rate.toFixed(0)}% · n={r.occurrences}
      </div>
    </button>
  );

  return (
    <>
      <section className="mb-6">
        <div className="mb-2 flex items-baseline gap-3">
          <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Edge in this regime</div>
          <div className="text-xs text-slate-500">
            C{cq}G{gq} · avg high ÷ |avg low|, min 5 occurrences · click to chart ·{" "}
            <a href={`/backtest?cq=${cq}&gq=${gq}`} className="underline hover:text-slate-300">
              full table
            </a>
            {tvNow && <> · <TvListLink list={tvNow} label="TradingView list" /></>}
          </div>
        </div>

        {/* Counts are DERIVED. They were typed as "best 20" / "worst 10",
            which was right only by coincidence and went wrong the moment the
            constant moved -- a thin regime shows fewer, and the label has to
            say so rather than claim a number that is not there. */}
        <div className="mb-1 text-[0.62rem] uppercase tracking-wide text-slate-500">
          best {best.length}
        </div>
        <div className="mb-3 flex flex-wrap gap-2">
          {best.map((r) => (
            <Card key={r.ticker} r={r} />
          ))}
        </div>

        {worst.length > 0 && (
          <>
            <div className="mb-1 text-[0.62rem] uppercase tracking-wide text-slate-500">
              worst {worst.length}
            </div>
            <div className="flex flex-wrap gap-2">
              {worst.map((r) => (
                <Card key={r.ticker} r={r} dim />
              ))}
            </div>
          </>
        )}
      </section>

      <section className="mb-6">
        <div className="mb-2 flex items-baseline gap-3">
          <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Chart</div>
          <div className="text-xs text-slate-500">
            {sel.ticker}
            {sel.symbol !== sel.ticker && sel.symbol !== `AMEX:${sel.ticker}` ? ` · ${sel.symbol}` : ""}
          </div>
        </div>
        <TradingViewChart symbol={sel.symbol} />
      </section>

      {mixture && (
        <MixtureTable data={mixture} selected={sel.ticker} onSelect={select} tvList={tvFlip} />
      )}
    </>
  );
}
