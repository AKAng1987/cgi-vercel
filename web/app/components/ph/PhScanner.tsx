"use client";

import { useMemo, useState } from "react";
import { PhScannerRow } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { PhTicker } from "./PhSelect";
import { peso, pct, price } from "./phFormat";

type Key = "s" | "d" | "w" | "m" | "q" | "y" | "vs50" | "vs200" | "from_high3m" | "mc" | "v30" | "fl";
const COLS: { key: Key; label: string; kind: "text" | "pct" | "peso" | "plain" }[] = [
  { key: "s", label: "Stock", kind: "text" }, { key: "d", label: "1D", kind: "pct" }, { key: "w", label: "1W", kind: "pct" }, { key: "m", label: "1M", kind: "pct" }, { key: "q", label: "3M", kind: "pct" },
  { key: "y", label: "YTD", kind: "pct" }, { key: "vs50", label: "vs 50d", kind: "pct" }, { key: "vs200", label: "vs 200d", kind: "pct" },
  { key: "from_high3m", label: "from 3M high", kind: "pct" }, { key: "mc", label: "Mkt cap", kind: "peso" }, { key: "v30", label: "Avg ₱/day", kind: "peso" }, { key: "fl", label: "Float %", kind: "plain" },
];

/** Every liquid name, sortable and filterable. "Copy TradingView list" puts the filtered tickers on the clipboard for a watchlist import. */
export function PhScanner({ rows }: { rows: PhScannerRow[] }) {
  const [key, setKey] = useState<Key>("m");
  const [asc, setAsc] = useState(false);
  const [sec, setSec] = useState("all");
  const [psei, setPsei] = useState(false);
  const [q, setQ] = useState("");
  const [copied, setCopied] = useState(false);
  const sectors = useMemo(() => Array.from(new Set(rows.map((r) => r.sec).filter(Boolean) as string[])).sort(), [rows]);
  const shown = useMemo(() => {
    const f = rows.filter((r) => (sec === "all" || r.sec === sec) && (!psei || r.psei) && (!q || r.s.toLowerCase().includes(q.toLowerCase())));
    return [...f].sort((a, b) => {
      const x = a[key as keyof PhScannerRow] as number | string | null;
      const y = b[key as keyof PhScannerRow] as number | string | null;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1);
    });
  }, [rows, key, asc, sec, psei, q]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(shown.map((r) => `PSE:${r.s}`).join(","));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  }
  return (
    <section className="mb-4 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Scanner · liquid PSE names</div>
        <div className="text-[0.68rem] text-slate-500">{shown.length} of {rows.length}</div>
        <select value={sec} onChange={(e) => setSec(e.target.value)} className="rounded border border-slate-700 bg-slate-950 px-1 py-0.5 text-xs text-slate-200">
          <option value="all">all sectors</option>
          {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <label className="flex items-center gap-1 text-xs text-slate-400"><input type="checkbox" checked={psei} onChange={(e) => setPsei(e.target.checked)} />PSEi only</label>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ticker" className="w-24 rounded border border-slate-700 bg-slate-950 px-2 py-0.5 text-xs text-slate-200" />
        <button onClick={copy} className="ml-auto rounded border border-slate-700 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-800">{copied ? "copied" : "Copy as TradingView list"}</button>
      </div>
      <div className="max-h-[32rem] overflow-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-slate-900">
            <tr className="text-left text-[0.6rem] uppercase text-slate-500">
              {COLS.map((c) => (
                <th key={c.key} className={`cursor-pointer pb-1 pr-2 font-normal hover:text-slate-200 ${c.kind === "text" ? "" : "text-right"}`}
                    onClick={() => (key === c.key ? setAsc(!asc) : (setKey(c.key), setAsc(c.key === "s")))}>
                  {c.label}{key === c.key ? (asc ? " ▲" : " ▼") : ""}
                </th>
              ))}
              <th className="pb-1 font-normal">Last</th><th className="pb-1 font-normal">Industry</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.s} className="border-t border-slate-800/70">
                {COLS.map((c) => {
                  const v = r[c.key as keyof PhScannerRow] as number | string | null;
                  if (c.kind === "text") return <td key={c.key} className="py-1 pr-2 font-semibold text-slate-100"><PhTicker s={r.s} list={shown.map((x) => x.s)} className="hover:underline">{r.s}</PhTicker>{r.psei ? <span className="ml-1 text-[0.55rem] text-slate-500">PSEi</span> : null}{r.below_line ? <span className="ml-1 text-[0.55rem] text-slate-500" title="below ₱5M a day; in the list by request">thin</span> : null}</td>;
                  if (c.kind === "pct") return <td key={c.key} className="py-1 pr-2 text-right tabular-nums" style={{ color: pctColor(v as number | null) }}>{pct(v as number | null)}</td>;
                  if (c.kind === "peso") return <td key={c.key} className="py-1 pr-2 text-right tabular-nums text-slate-400">{peso(v as number | null)}</td>;
                  return <td key={c.key} className="py-1 pr-2 text-right tabular-nums text-slate-400">{v != null ? `${Math.round(v as number)}` : "—"}</td>;
                })}
                <td className="py-1 pr-2 tabular-nums text-slate-400">{price(r.c)}</td>
                <td className="py-1 text-slate-500">{r.ind ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
