"use client";

import { useMemo, useState } from "react";
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

  // Available groups derived from the current result -- so if a regime
  // combo has zero occurrences in one asset class, that group's chip
  // simply doesn't appear rather than showing as "no data".
  const availableGroups = useMemo(
    () => Array.from(new Set(rows.map((r) => r.group))),
    [rows]
  );

  const [hiddenGroups, setHiddenGroups] = useState<Set<string>>(new Set());
  const filteredRows = useMemo(
    () => rows.filter((r) => !hiddenGroups.has(r.group)),
    [rows, hiddenGroups]
  );

  const grouped = groupRows(filteredRows);

  // Top-N by Edge across all shown groups. Shown above the grouped
  // tables so users can see the global winners without scrolling.
  // Uses the same filteredRows (respects group chip toggles), so
  // hiding a group also removes its tickers from the leaderboard.
  const topByEdge = useMemo(() => {
    return filteredRows
      .filter((r) => r.edge !== null && !Number.isNaN(r.edge))
      .sort((a, b) => (b.edge ?? 0) - (a.edge ?? 0))
      .slice(0, 10);
  }, [filteredRows]);

  function toggleGroup(g: string) {
    setHiddenGroups((prev) => {
      const next = new Set(prev);
      if (next.has(g)) next.delete(g);
      else next.add(g);
      return next;
    });
  }

  return (
    <div>
      {availableGroups.length > 1 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500">Show groups:</span>
          {availableGroups.map((g) => {
            const active = !hiddenGroups.has(g);
            return (
              <button
                key={g}
                onClick={() => toggleGroup(g)}
                className={`rounded border px-2 py-0.5 text-[0.68rem] uppercase tracking-wide transition ${
                  active
                    ? "border-[#3b4f8a] bg-[#1a1f35] text-[color:var(--cgi-accent)]"
                    : "border-slate-800 bg-slate-950 text-slate-600 line-through"
                }`}
              >
                {g}
              </button>
            );
          })}
        </div>
      )}

      {topByEdge.length > 0 && (
        <div className="mb-4 rounded border border-[#3b4f8a] bg-[#0f1425]">
          <div className="border-b border-[#1a2340] px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
            Top {topByEdge.length} by Edge — across all shown groups
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-[0.76rem]">
              <thead>
                <tr>
                  {["#", "Ticker", "Group", "Occ", "Edge", "Avg High%", "Avg Low%", "Hit Rate"].map(
                    (h, i) => (
                      <th
                        key={h}
                        className={`bg-[#131a2e] px-1.5 py-1 text-[0.68rem] uppercase tracking-wide text-slate-400 ${
                          i <= 2 ? "text-left" : "text-right"
                        }`}
                      >
                        {h}
                      </th>
                    )
                  )}
                </tr>
              </thead>
              <tbody>
                {topByEdge.map((r, i) => (
                  <tr
                    key={r.ticker}
                    onClick={() => setSelected(r.ticker)}
                    className={`cursor-pointer hover:bg-slate-800/50 ${
                      selected === r.ticker ? "bg-slate-800/70" : ""
                    }`}
                  >
                    <td className="px-1.5 py-0.5 text-slate-500">{i + 1}</td>
                    <td className="px-1.5 py-0.5 font-medium text-slate-100">{r.ticker}</td>
                    <td className="px-1.5 py-0.5 text-[0.68rem] uppercase tracking-wide text-slate-500">
                      {r.group}
                    </td>
                    <td className="px-1.5 py-0.5 text-right text-slate-300">{r.occurrences}</td>
                    <td className="px-1.5 py-0.5 text-right font-bold text-slate-100">
                      {fmtEdge(r.edge)}
                    </td>
                    <td
                      className="px-1.5 py-0.5 text-right"
                      style={{ color: pctColor(r.avg_high_pct) }}
                    >
                      {fmtPct(r.avg_high_pct)}
                    </td>
                    <td
                      className="px-1.5 py-0.5 text-right"
                      style={{ color: pctColor(r.avg_low_pct) }}
                    >
                      {fmtPct(r.avg_low_pct)}
                    </td>
                    <td className="px-1.5 py-0.5 text-right text-slate-300">
                      {r.hit_rate.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {Array.from(grouped.entries()).map(([group, rowsInGroup]) => (
        <div key={group} className="mt-4">
          <div className="mb-1 border-l-[3px] border-l-[#3b4f8a] bg-[#1a1f35] px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
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
