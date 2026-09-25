"use client";

import { useState } from "react";
import { BacktestRow } from "@/lib/types";
import { TradingViewChart } from "../TradingViewChart";

/**
 * Edge cards for the current regime, clickable to chart. The chart lives
 * here rather than as a sibling so a click can drive it without lifting
 * state into the server component.
 */
export function EdgeStrip({
  best,
  worst,
  cq,
  gq,
}: {
  best: BacktestRow[];
  worst: BacktestRow[];
  cq: number;
  gq: number;
}) {
  const [symbol, setSymbol] = useState("SPY");

  const Card = ({ r, dim }: { r: BacktestRow; dim?: boolean }) => (
    <button
      onClick={() => setSymbol(r.ticker)}
      className={`rounded border px-2.5 py-1.5 text-left transition ${
        symbol === r.ticker
          ? "border-[#8b9dc3] bg-slate-800"
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
          </div>
        </div>

        <div className="mb-1 text-[0.62rem] uppercase tracking-wide text-slate-500">best 20</div>
        <div className="mb-3 flex flex-wrap gap-2">
          {best.map((r) => (
            <Card key={r.ticker} r={r} />
          ))}
        </div>

        {worst.length > 0 && (
          <>
            <div className="mb-1 text-[0.62rem] uppercase tracking-wide text-slate-500">worst 10</div>
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
          <div className="text-xs text-slate-500">{symbol}</div>
        </div>
        <TradingViewChart symbol={symbol} />
      </section>
    </>
  );
}
