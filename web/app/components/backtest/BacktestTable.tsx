"use client";

import { useState } from "react";
import { BacktestRow } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { OccurrenceDetail } from "./OccurrenceDetail";

function fmtPct(v: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function fmtEdge(v: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toFixed(2);
}

function groupRows(rows: BacktestRow[]): Map<string, BacktestRow[]> {
  const map = new Map<string, BacktestRow[]>();
  for (const r of rows) {
    const arr = map.get(r.group) ?? [];
    arr.push(r);
    map.set(r.group, arr);
  }
  return map;
}

export function BacktestTable({
  rows,
  compassQ,
  gridQ,
}: {
  rows: BacktestRow[];
  compassQ: number;
  gridQ: number;
}) {
  const [selected, setSelected] = useState<string | null>(null);
  const grouped = groupRows(rows);

  return (
    <div>
      {Array.from(grouped.entries()).map(([group, rowsInGroup]) => (
        <div key={group} className="mt-4">
          <div className="mb-1 border-l-[3px] border-l-[#3b4f8a] bg-[#1a1f35] px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
            {group}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[0.76rem]">
              <thead>
                <tr>
                  {["Ticker", "Occ", "Avg High%", "Avg Low%", "Hit Rate", "Edge", "Avg Return%"].map(
                    (h, i) => (
                      <th
                        key={h}
                        className={`bg-[#1F2937] px-1.5 py-1 text-[0.68rem] uppercase tracking-wide text-slate-400 ${
                          i === 0 ? "text-left" : "text-right"
                        }`}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {rowsInGroup.map((r) => (
                  <tr
                    key={r.ticker}
                    onClick={() => setSelected(r.ticker)}
                    className={`cursor-pointer hover:bg-slate-800/50 ${
                      selected === r.ticker ? "bg-slate-800/70" : ""
                    }`}
                  >
                    <td className="px-1.5 py-0.5 font-medium text-slate-200">{r.ticker}</td>
                    <td className="px-1.5 py-0.5 text-right text-slate-300">{r.occurrences}</td>
                    <td
                      className="px-1.5 py-0.5 text-right font-medium"
                      style={{ color: pctColor(r.avg_high_pct) }}
                    >
                      {fmtPct(r.avg_high_pct)}
                    </td>
                    <td
                      className="px-1.5 py-0.5 text-right font-medium"
                      style={{ color: pctColor(r.avg_low_pct) }}
                    >
                      {fmtPct(r.avg_low_pct)}
                    </td>
                    <td className="px-1.5 py-0.5 text-right text-slate-200">
                      {r.hit_rate.toFixed(1)}%
                    </td>
                    <td className="px-1.5 py-0.5 text-right font-medium text-slate-100">
                      {fmtEdge(r.edge)}
                    </td>
                    <td
                      className="px-1.5 py-0.5 text-right font-medium"
                      style={{ color: pctColor(r.avg_return_pct) }}
                    >
                      {fmtPct(r.avg_return_pct)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {selected && (
        <OccurrenceDetail
          ticker={selected}
          compassQ={compassQ}
          gridQ={gridQ}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
