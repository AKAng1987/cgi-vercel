"use client";

import { useState } from "react";
import { PhHorizon, PhLeader, PhSegment } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { TradingViewChart } from "../TradingViewChart";
import { peso, pct, price, tvSymbol } from "./phFormat";

const HORIZONS = ["1W", "1M", "3M", "YTD"] as const;
type H = (typeof HORIZONS)[number];

function Trend({ r }: { r: PhLeader }) {
  const t = (v: number | null, l: string) =>
    v === null ? null : <span key={l} className={v >= 0 ? "text-slate-300" : "text-slate-600"} title={`${l}: ${pct(v)} vs its average`}>{v >= 0 ? "▲" : "▼"}</span>;
  return <span className="text-[0.6rem]">{t(r.vs50, "50d")}{t(r.vs200, "200d")}</span>;
}

function Row({ r, onPick, active }: { r: PhLeader; onPick: (s: string) => void; active: boolean }) {
  return (
    <tr onClick={() => onPick(r.s)} className={`cursor-pointer border-t border-slate-800/70 hover:bg-slate-800/40 ${active ? "bg-slate-800/60" : ""}`}>
      <td className="py-1 pr-2 font-semibold text-slate-100">{r.s}{r.psei ? <span className="ml-1 text-[0.55rem] text-slate-500">PSEi</span> : null}</td>
      <td className="py-1 pr-2 text-right tabular-nums font-semibold" style={{ color: pctColor(r.ret) }}>{pct(r.ret)}</td>
      <td className="py-1 pr-2 text-right tabular-nums text-slate-400">{price(r.c)}</td>
      <td className="py-1 pr-2 text-center"><Trend r={r} /></td>
      <td className="py-1 pr-2 text-right tabular-nums text-slate-500">{peso(r.vt)}</td>
      <td className="py-1 pl-3 text-slate-500">{r.ind ?? ""}</td>
    </tr>
  );
}

function Board({ title, rows, onPick, sel }: { title: string; rows: PhLeader[]; onPick: (s: string) => void; sel: string | null }) {
  return (
    <div>
      <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">{title}</div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[0.58rem] uppercase text-slate-600">
            <th className="pb-1 font-normal">Stock</th><th className="pb-1 text-right font-normal">Return</th><th className="pb-1 text-right font-normal">Last</th>
            <th className="pb-1 text-center font-normal" title="above/below its 50 and 200 day average">50/200d</th>
            <th className="pb-1 text-right font-normal">Traded today</th><th className="pb-1 pl-3 font-normal">Industry</th>
          </tr>
        </thead>
        <tbody>{rows.map((r) => <Row key={r.s} r={r} onPick={onPick} active={sel === r.s} />)}</tbody>
      </table>
    </div>
  );
}

function Segments({ segs, onPick }: { segs: PhSegment[]; onPick: (s: string) => void }) {
  if (!segs.length) return <p className="text-xs text-slate-500">no group has two liquid names with a return at this horizon</p>;
  const max = Math.max(...segs.map((s) => Math.abs(s.median)), 1);
  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="text-left text-[0.58rem] uppercase text-slate-600">
          <th className="pb-1 font-normal">Segment</th><th className="pb-1 text-right font-normal">Median</th><th className="pb-1 pl-2 font-normal" />
          <th className="pb-1 text-right font-normal">% up</th><th className="pb-1 text-right font-normal">n</th><th className="pb-1 pl-2 font-normal">Leader</th>
        </tr>
      </thead>
      <tbody>
        {segs.map((g) => (
          <tr key={g.name} className="border-t border-slate-800/70">
            <td className="py-1 pr-2 text-slate-200" title={g.members.join(", ")}>{g.name}</td>
            <td className="py-1 pr-2 text-right tabular-nums font-semibold" style={{ color: pctColor(g.median) }}>{pct(g.median)}</td>
            <td className="w-24 py-1">
              <div className="h-1.5 rounded bg-slate-800">
                <div className="h-1.5 rounded" style={{ width: `${Math.min(100, (Math.abs(g.median) / max) * 100)}%`, background: pctColor(g.median) }} />
              </div>
            </td>
            <td className="py-1 pr-2 text-right tabular-nums text-slate-400">{g.pct_up}%</td>
            <td className="py-1 pr-2 text-right tabular-nums text-slate-500">{g.n}</td>
            <td className="py-1 pl-2"><button className="font-semibold text-slate-200 hover:underline" onClick={() => onPick(g.top)}>{g.top}</button> <span style={{ color: pctColor(g.top_ret) }}>{pct(g.top_ret)}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Leaderboard and segments over one horizon; click a stock to chart it. Liquid names only. */
export function PhMarket({ horizons, nLiquid, asof }: { horizons: Record<H, PhHorizon>; nLiquid: number; asof: string | null }) {
  const [h, setH] = useState<H>("1M");
  const [by, setBy] = useState<"ind" | "sec">("ind");
  const [sel, setSel] = useState<string | null>(null);
  const d = horizons[h];
  return (
    <section className="mb-4 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-3 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Leaderboard &amp; segments</div>
        <div className="flex gap-1">
          {HORIZONS.map((x) => (
            <button key={x} onClick={() => setH(x)} className={`rounded px-2 py-0.5 text-xs ${h === x ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:bg-slate-800"}`}>{x}</button>
          ))}
        </div>
        <div className="text-[0.68rem] text-slate-500">{d.leaders.n} liquid names (≥ ₱5M a day, 30-session average) · as of {asof ?? "—"}</div>
        <div className="ml-auto flex gap-1 text-xs">
          <button onClick={() => setBy("ind")} className={`rounded px-2 py-0.5 ${by === "ind" ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:bg-slate-800"}`}>PSE subsector</button>
          <button onClick={() => setBy("sec")} className={`rounded px-2 py-0.5 ${by === "sec" ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:bg-slate-800"}`}>PSE sector</button>
        </div>
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
        <div className="space-y-4">
          <Board title={`Leaders · ${h}`} rows={d.leaders.top} onPick={setSel} sel={sel} />
          <Board title={`Laggards · ${h}`} rows={d.leaders.bottom} onPick={setSel} sel={sel} />
        </div>
        <div>
          <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">Where the strength is · median return by segment, {h}</div>
          <Segments segs={by === "ind" ? d.segments_industry : d.segments_sector} onPick={setSel} />
          <p className="mt-2 text-[0.62rem] leading-relaxed text-slate-600">
            A segment is the PSE&apos;s own sector or subsector, counted over the {nLiquid} liquid names. Groups with one liquid name are left out. Median, not average, so one stock
            like a thinly traded mover cannot carry a group. Describes what has happened; it does not say what continues.
          </p>
        </div>
      </div>
      {sel && (
        <div className="mt-4">
          <div className="mb-1 flex items-center gap-3 text-xs text-slate-400">
            <span className="font-bold text-slate-100">{sel}</span>
            <a className="underline hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={`https://www.tradingview.com/chart/?symbol=${tvSymbol(sel)}`}>open in TradingView ↗</a>
            <button className="ml-auto text-slate-500 hover:text-slate-200" onClick={() => setSel(null)}>close ✕</button>
          </div>
          <TradingViewChart symbol={tvSymbol(sel)} />
        </div>
      )}
    </section>
  );
}
