"use client";

import { useMemo, useState } from "react";
import { FundCompany } from "@/lib/types";

const VERDICT_COLOR: Record<string, string> = {
  capturing: "text-emerald-400",
  accelerating: "text-emerald-300",
  "buying growth": "text-amber-300",
  holding: "text-slate-400",
  slowing: "text-orange-400",
  "rolling over": "text-rose-400",
  unknown: "text-slate-600",
};

type Key = "symbol" | "sector" | "verdict" | "yoy" | "accel" | "seasonal" | "margin" | "payout" | "burden" | "z";

/** Sort value per column. null always sorts LAST regardless of direction:
 *  a missing figure is not a small figure, and letting it rank as one would
 *  put companies with no data at the top of an ascending sort. */
function val(c: FundCompany, k: Key): number | string | null {
  switch (k) {
    case "symbol":
      return c.symbol;
    case "sector":
      return c.sector ?? null;
    case "verdict":
      return c.read.verdict;
    case "yoy":
      return c.revenue.status === "ok" ? c.revenue.yoy_pct ?? null : null;
    case "accel":
      return c.revenue.status === "ok" ? c.revenue.acceleration_pp ?? null : null;
    case "seasonal":
      return c.seasonal_qoq?.status === "ok" ? c.seasonal_qoq.surprise_pp ?? null : null;
    case "margin":
      return c.margin.status === "ok" ? c.margin.margin_change_yoy_pp ?? null : null;
    case "payout":
      return c.return_to_shareholders.status === "ok"
        ? c.return_to_shareholders.payout_of_ocf_pct ?? null
        : null;
    case "burden":
      return c.rate_risk.interest_burden_pct ?? null;
    case "z":
      return c.risk_of_ruin.status === "ok" ? c.risk_of_ruin.altman_z2 ?? null : null;
  }
}

function sign(n: number | null | undefined, unit = "pp") {
  if (n === null || n === undefined) return <span className="text-slate-600">—</span>;
  const c = n > 0.5 ? "text-emerald-400" : n < -0.5 ? "text-rose-400" : "text-slate-400";
  return (
    <span className={c}>
      {n > 0 ? "+" : ""}
      {n.toFixed(1)}
      {unit}
    </span>
  );
}

function Spark({ pts }: { pts: number[] }) {
  if (pts.length < 3) return null;
  const w = 64;
  const h = 16;
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const span = hi - lo || 1;
  const d = pts.map((v, i) => `${(i / (pts.length - 1)) * w},${h - ((v - lo) / span) * h}`).join(" ");
  const rising = pts[pts.length - 1] > pts[pts.length - 2];
  return (
    <svg width={w} height={h} className="inline-block align-middle">
      <polyline
        points={d}
        fill="none"
        strokeWidth="1.2"
        className={rising ? "stroke-emerald-500" : "stroke-rose-500"}
      />
    </svg>
  );
}

const COLS: { key: Key; label: string; right?: boolean }[] = [
  { key: "symbol", label: "sym" },
  { key: "sector", label: "sector" },
  { key: "verdict", label: "read" },
  { key: "yoy", label: "rev yoy", right: true },
  { key: "accel", label: "accel", right: true },
  { key: "seasonal", label: "seas. QoQ", right: true },
  { key: "margin", label: "margin Δ", right: true },
  { key: "payout", label: "payout", right: true },
  { key: "burden", label: "int burden", right: true },
  { key: "z", label: "Z''", right: true },
];

export function FundamentalsTable({ companies }: { companies: FundCompany[] }) {
  const [key, setKey] = useState<Key>("accel");
  const [desc, setDesc] = useState(true);

  const rows = useMemo(() => {
    const out = [...companies];
    out.sort((a, b) => {
      const x = val(a, key);
      const y = val(b, key);
      if (x === null && y === null) return 0;
      if (x === null) return 1; // nulls last, both directions
      if (y === null) return -1;
      const c = typeof x === "string" ? String(x).localeCompare(String(y)) : Number(x) - Number(y);
      return desc ? -c : c;
    });
    return out;
  }, [companies, key, desc]);

  function click(k: Key) {
    if (k === key) setDesc(!desc);
    else {
      setKey(k);
      setDesc(k !== "symbol" && k !== "verdict");
    }
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[0.72rem]">
        <thead>
          <tr className="border-b border-slate-800 text-[0.6rem] uppercase tracking-wider text-slate-500">
            {COLS.map((c) => (
              <th
                key={c.key}
                onClick={() => click(c.key)}
                className={`cursor-pointer select-none pb-1 pr-2 font-medium hover:text-slate-300 ${
                  c.right ? "text-right" : "text-left"
                } ${key === c.key ? "text-slate-200" : ""}`}
                title={`Sort by ${c.label}`}
              >
                {c.label}
                {key === c.key && <span className="ml-0.5">{desc ? "▾" : "▴"}</span>}
              </th>
            ))}
            <th className="pb-1 text-left font-medium">yoy shape</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => {
            const r = c.revenue;
            const m = c.margin;
            const ruin = c.risk_of_ruin;
            const hist = (r.history ?? []).map((h) => h.yoy_pct).filter((v): v is number => v !== null);
            return (
              <tr key={c.symbol} className="border-b border-slate-900/70 hover:bg-slate-900/40">
                <td className="py-1 pr-2 font-mono text-slate-200">
                  {c.symbol}
                  {c.annual_only && (
                    <span
                      className="ml-1 text-[0.55rem] text-amber-400"
                      title="20-F/40-F filer, read annually — excluded from quarterly medians"
                    >
                      A
                    </span>
                  )}
                </td>
                <td className="max-w-[12rem] truncate py-1 pr-3 text-[0.66rem] text-slate-500" title={c.sector ?? ""}>
                  {c.sector ?? "—"}
                </td>
                <td className={`py-1 pr-3 text-[0.68rem] ${VERDICT_COLOR[c.read.verdict] ?? "text-slate-400"}`}>
                  {c.read.verdict}
                </td>
                <td className="py-1 pr-2 text-right tabular-nums text-slate-300">
                  {r.status === "ok" && r.yoy_pct !== null && r.yoy_pct !== undefined
                    ? `${r.yoy_pct.toFixed(1)}%`
                    : "—"}
                </td>
                <td className="py-1 pr-2 text-right tabular-nums">{sign(r.acceleration_pp)}</td>
                <td
                  className="py-1 pr-2 text-right tabular-nums"
                  title={c.seasonal_qoq?.note}
                >
                  {c.seasonal_qoq?.status === "ok" ? (
                    sign(c.seasonal_qoq.surprise_pp)
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                <td className="py-1 pr-2 text-right tabular-nums">
                  {m.status === "ok" ? sign(m.margin_change_yoy_pp) : <span className="text-slate-600">—</span>}
                </td>
                <td className="py-1 pr-2 text-right tabular-nums text-slate-400">
                  {c.return_to_shareholders.status === "ok"
                    ? `${c.return_to_shareholders.payout_of_ocf_pct?.toFixed(0)}%`
                    : "—"}
                </td>
                <td className="py-1 pr-2 text-right tabular-nums text-slate-400">
                  {c.rate_risk.interest_burden_pct !== undefined
                    ? `${c.rate_risk.interest_burden_pct.toFixed(0)}%`
                    : "—"}
                </td>
                <td className="py-1 pr-2 text-right tabular-nums">
                  {ruin.status === "ok" && ruin.altman_z2 !== undefined ? (
                    <span
                      className={
                        ruin.band === "distress"
                          ? "text-rose-400"
                          : ruin.band === "grey"
                          ? "text-amber-300"
                          : ruin.band === "safe"
                          ? "text-slate-400"
                          : "text-slate-600"
                      }
                      title={ruin.note}
                    >
                      {ruin.altman_z2.toFixed(1)}
                      {ruin.accumulated_deficit ? "*" : ""}
                    </span>
                  ) : (
                    <span className="text-slate-600">—</span>
                  )}
                </td>
                <td className="py-1">
                  <Spark pts={[...hist].reverse()} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
