"use client";

import { useEffect, useState } from "react";
import { BacktestOccurrence, BacktestOccurrencesResponse } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";

function fmtPct(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export function OccurrenceDetail({
  ticker,
  compassQ,
  gridQ,
  onClose,
}: {
  ticker: string;
  compassQ: number;
  gridQ: number;
  onClose: () => void;
}) {
  const [data, setData] = useState<BacktestOccurrencesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setError(null);
    const controller = new AbortController();
    const qs = new URLSearchParams({
      cq: String(compassQ),
      gq: String(gridQ),
      ticker,
    });
    fetch(`/api/backtest-occurrences?${qs}`, { signal: controller.signal })
      .then((r) => r.json())
      .then((j) => {
        if (j.error) setError(j.error);
        else setData(j);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(String(e));
      });
    return () => controller.abort();
  }, [ticker, compassQ, gridQ]);

  const occurrences: BacktestOccurrence[] = data?.occurrences ?? [];

  return (
    <div className="mt-6 rounded border border-slate-800 bg-slate-900/60">
      <div className="flex items-center justify-between border-b border-slate-800 px-3 py-2">
        <div className="text-sm font-medium text-slate-100">
          Occurrences for <span className="font-bold">{ticker}</span> (C{compassQ}×G{gridQ})
        </div>
        <button
          onClick={onClose}
          className="rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-700"
        >
          Close
        </button>
      </div>

      {error ? (
        <div className="p-3 text-sm text-red-400">Error: {error}</div>
      ) : !data ? (
        <div className="p-3 text-sm text-slate-500">Loading…</div>
      ) : occurrences.length === 0 ? (
        <div className="p-3 text-sm text-slate-400">No occurrences found for {ticker}.</div>
      ) : (
        <div className="max-h-[400px] overflow-y-auto">
          <table className="w-full border-collapse text-[0.76rem]">
            <thead className="sticky top-0">
              <tr>
                {["Start Date", "End Date", "Days", "High%", "Low%", "Close%"].map((h, i) => (
                  <th
                    key={h}
                    className={`bg-[#1F2937] px-1.5 py-1 text-[0.68rem] uppercase tracking-wide text-slate-400 ${
                      i < 2 ? "text-left" : "text-right"
                    }`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {occurrences.map((o, i) => (
                <tr key={i} className="hover:bg-slate-800/40">
                  <td className="px-1.5 py-0.5 text-slate-300">{o.start_date}</td>
                  <td className="px-1.5 py-0.5 text-slate-300">{o.end_date}</td>
                  <td className="px-1.5 py-0.5 text-right text-slate-300">{o.duration_days}</td>
                  <td
                    className="px-1.5 py-0.5 text-right font-medium"
                    style={{ color: pctColor(o.high_pct) }}
                  >
                    {fmtPct(o.high_pct)}
                  </td>
                  <td
                    className="px-1.5 py-0.5 text-right font-medium"
                    style={{ color: pctColor(o.low_pct) }}
                  >
                    {fmtPct(o.low_pct)}
                  </td>
                  <td
                    className="px-1.5 py-0.5 text-right font-medium"
                    style={{ color: pctColor(o.return_pct) }}
                  >
                    {fmtPct(o.return_pct)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
