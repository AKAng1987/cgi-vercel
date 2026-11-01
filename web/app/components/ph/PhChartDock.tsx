"use client";

import { useEffect, useMemo, useState } from "react";
import { PhBar, PhSymbolView } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { usePhSelect } from "./PhSelect";
import { dayLabel, edgeLink, num, peso, pct, price } from "./phFormat";

const EMA_STYLE: { n: string; cls: string }[] = [
  { n: "5", cls: "text-amber-300" }, { n: "10", cls: "text-red-300" }, { n: "20", cls: "text-blue-400" },
  { n: "50", cls: "text-violet-400" }, { n: "100", cls: "text-emerald-300" }, { n: "200", cls: "text-slate-300" },
];
const W = 1000, H = 330, VH = 70, PAD_L = 6, PAD_R = 52, LANE = 20;
type Ev = NonNullable<PhSymbolView["events"]>[number];
const EV_STYLE: Record<Ev["type"], { cls: string; name: string }> = {
  R: { cls: "text-blue-400", name: "results filed" }, B: { cls: "text-emerald-300", name: "buy-back report" },
  I: { cls: "text-sky-300", name: "insider buy / sell" }, D: { cls: "text-violet-400", name: "dividend declared" },
  M: { cls: "text-amber-300", name: "material information" }, C: { cls: "text-red-300", name: "corporate action" }, O: { cls: "text-slate-300", name: "ownership / tender report" },
};

function Chart({ v, hover, setHover, events }: { v: PhSymbolView; hover: number | null; setHover: (i: number | null) => void; events: Ev[] }) {
  const bars: PhBar[] = v.bars ?? [];
  const line = v.line ?? [];
  const n = v.kind === "index" ? line.length : bars.length;
  const lo = useMemo(() => (v.kind === "index" ? Math.min(...line.map((p) => p[1])) : Math.min(...bars.map((b) => b[3]))), [v, bars, line]);
  const hi = useMemo(() => (v.kind === "index" ? Math.max(...line.map((p) => p[1])) : Math.max(...bars.map((b) => b[2]))), [v, bars, line]);
  if (n < 2) return <div className="flex h-48 items-center justify-center text-xs text-slate-500">no bars stored for this name</div>;
  const span = hi - lo || 1;
  const step = (W - PAD_L - PAD_R) / n;
  const x = (i: number) => PAD_L + step * (i + 0.5);
  const y = (p: number) => 8 + (H - 16) * (1 - (p - lo) / span);
  const maxV = Math.max(...bars.map((b) => b[5]), 1);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => lo + span * f);
  const months: { i: number; label: string }[] = [];
  const dates = v.kind === "index" ? line.map((p) => p[0]) : bars.map((b) => b[0]);
  dates.forEach((d, i) => { if (i === 0 || d.slice(5, 7) !== dates[i - 1].slice(5, 7)) months.push({ i, label: dayLabel(d).split(" ")[0] }); });
  return (
    <svg viewBox={`0 0 ${W} ${H + LANE + VH + 18}`} className="w-full" onMouseLeave={() => setHover(null)}
         onMouseMove={(e) => { const r = e.currentTarget.getBoundingClientRect(); const i = Math.floor(((e.clientX - r.left) / r.width * W - PAD_L) / step); setHover(i >= 0 && i < n ? i : null); }}>
      {ticks.map((t, k) => (
        <g key={k}>
          <line x1={PAD_L} x2={W - PAD_R} y1={y(t)} y2={y(t)} stroke="currentColor" className="text-slate-800" strokeWidth={0.6} />
          <text x={W - PAD_R + 4} y={y(t) + 3} fontSize={10} fill="currentColor" className="text-slate-500">{price(t)}</text>
        </g>
      ))}
      {v.kind === "index" ? (
        <polyline fill="none" stroke="currentColor" className="text-slate-200" strokeWidth={1.6} points={line.map((p, i) => `${x(i)},${y(p[1])}`).join(" ")} />
      ) : (
        <>
          {bars.map((b, i) => {
            const up = b[4] >= b[1];
            const col = up ? "var(--cgi-up)" : "var(--cgi-down)";
            return (
              <g key={`${b[0]}-${i}`}>
                <line x1={x(i)} x2={x(i)} y1={y(b[2])} y2={y(b[3])} stroke={col} strokeWidth={1} />
                <rect x={x(i) - step * 0.34} width={step * 0.68} y={y(Math.max(b[1], b[4]))} height={Math.max(1, Math.abs(y(b[1]) - y(b[4])))} fill={col} />
                <rect x={x(i) - step * 0.34} width={step * 0.68} y={H + LANE + 6 + VH * (1 - b[5] / maxV)} height={Math.max(0.5, (VH * b[5]) / maxV)} fill={col} opacity={0.45} />
              </g>
            );
          })}
          {EMA_STYLE.map(({ n: sp, cls }) => {
            const e = v.ema?.[sp];
            if (!e || e.length !== n) return null;
            return <polyline key={sp} fill="none" stroke="currentColor" className={cls} strokeWidth={1.1} points={e.map((p, i) => `${x(i)},${y(p)}`).join(" ")} />;
          })}
        </>
      )}
      {v.kind === "stock" && (() => {
        // one marker per event, on the first session on or after its date; events on the same session sit side by side
        const slot: Record<number, number> = {};
        return events.map((e, k) => {
          let i = bars.findIndex((b) => b[0] >= e.date);
          if (i < 0) i = n - 1;
          const j = (slot[i] = (slot[i] ?? -1) + 1);
          const st = EV_STYLE[e.type];
          const glyph = e.type === "I" ? (e.side === "sold" ? "▼" : "▲") : e.type;
          const cx = Math.min(W - PAD_R - 6, x(i) + j * 11);
          return (
            <g key={`${e.edge_no}-${k}`} className={`${st.cls} cursor-pointer`} onClick={() => window.open(`https://edge.pse.com.ph/openDiscViewer.do?edge_no=${e.edge_no}`, "_blank", "noopener")}>
              <title>{`${e.date}  ${st.name}: ${e.label}`}</title>
              <line x1={cx} x2={cx} y1={H + 2} y2={H + 6} stroke="currentColor" strokeWidth={0.7} />
              <circle cx={cx} cy={H + 13} r={5.5} fill="currentColor" opacity={0.18} stroke="currentColor" strokeWidth={0.8} />
              <text x={cx} y={H + 16} fontSize={8} textAnchor="middle" fill="currentColor" fontWeight={700}>{glyph}</text>
            </g>
          );
        });
      })()}
      {months.map((m) => <text key={m.i} x={x(m.i)} y={H + LANE + VH + 14} fontSize={10} fill="currentColor" className="text-slate-500">{m.label}</text>)}
      {hover !== null && hover < n && <line x1={x(hover)} x2={x(hover)} y1={4} y2={H + LANE + VH} stroke="currentColor" className="text-slate-500" strokeWidth={0.6} strokeDasharray="3 3" />}
    </svg>
  );
}

function Facts({ v }: { v: PhSymbolView }) {
  const nm = v.numbers as Record<string, number | null | boolean | string> | null;
  const g = (k: string) => (nm ? (nm[k] as number | null) : null);
  return (
    <div className="space-y-3 text-xs">
      {nm && v.kind === "stock" && (
        <div>
          <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">Numbers{nm.liquid === false ? " · below ₱5M a day, in the list by request" : ""}</div>
          <div className="grid grid-cols-5 gap-x-3 gap-y-1 tabular-nums">
            {([["1D", "d"], ["1W", "w"], ["1M", "m"], ["3M", "q"], ["YTD", "y"]] as const).map(([l, k]) => (
              <div key={k}><div className="text-[0.58rem] text-slate-600">{l}</div><div style={{ color: pctColor(g(k)) }}>{pct(g(k))}</div></div>
            ))}
            <div><div className="text-[0.58rem] text-slate-600">vs 50d</div><div style={{ color: pctColor(g("vs50")) }}>{pct(g("vs50"))}</div></div>
            <div><div className="text-[0.58rem] text-slate-600">vs 200d</div><div style={{ color: pctColor(g("vs200")) }}>{pct(g("vs200"))}</div></div>
            <div><div className="text-[0.58rem] text-slate-600">3M range</div><div className="text-slate-300">{price(g("l3"))}–{price(g("h3"))}</div></div>
            <div><div className="text-[0.58rem] text-slate-600">Float</div><div className="text-slate-300">{g("fl") != null ? `${Math.round(g("fl") as number)}%` : "—"}</div></div>
            <div><div className="text-[0.58rem] text-slate-600">Mkt cap</div><div className="text-slate-300">{peso(g("mc"))}</div></div>
            <div><div className="text-[0.58rem] text-slate-600">Avg ₱/day</div><div className="text-slate-300">{peso(g("v30"))}</div></div>
          </div>
        </div>
      )}
      {nm && v.kind === "index" && (
        <div className="grid grid-cols-4 gap-x-3 tabular-nums">
          {([["1W", "w"], ["1M", "m"], ["3M", "q"], ["YTD", "y"]] as const).map(([l, k]) => (
            <div key={k}><div className="text-[0.58rem] text-slate-600">{l}</div><div style={{ color: pctColor(g(k)) }}>{pct(g(k))}</div></div>
          ))}
        </div>
      )}
      {v.expected_report && <div className="text-slate-400">Expected to report ~{dayLabel(v.expected_report.date)} <span className="text-slate-600">({v.expected_report.basis})</span></div>}
      {v.results.length > 0 && (
        <div>
          <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">Latest results</div>
          {v.results.map((r) => (
            <div key={r.edge_no} className="flex items-baseline gap-2 tabular-nums">
              <span className="w-14 text-slate-500">{r.kind === "A" ? "FY" : `Q ${r.period.slice(5, 7)}/${r.period.slice(2, 4)}`}</span>
              <span className="text-slate-300">{r.revenue ? peso(r.revenue) : "—"}</span><span style={{ color: pctColor(r.rev_yoy) }}>{pct(r.rev_yoy)}</span>
              <span className="text-slate-500">NI</span><span className="text-slate-300">{peso(r.ni)}</span>
              <span style={{ color: pctColor(r.ni_yoy) }}>{r.ni_loss ? "loss" : r.ni_swing ? "swing" : pct(r.ni_yoy)}</span>
              <a className="ml-auto text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={edgeLink(r.edge_no)}>↗</a>
            </div>
          ))}
        </div>
      )}
      {v.buybacks.length > 0 && (
        <div>
          <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">Buy-backs</div>
          {v.buybacks.map((b) => (
            <div key={b.edge_no} className="flex gap-2 tabular-nums"><span className="w-14 text-slate-500">{dayLabel(b.report_date)}</span>
              <span className="text-emerald-300">{num(b.shares)} sh @ {price(b.avg_price)}</span><span className="text-slate-500">{peso(b.value)}</span>
              <a className="ml-auto text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={edgeLink(b.edge_no)}>↗</a></div>
          ))}
        </div>
      )}
      {v.disclosures.length > 0 && (
        <div>
          <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">Recent disclosures</div>
          <ul className="max-h-48 space-y-1 overflow-y-auto pr-1">
            {v.disclosures.map((d) => (
              <li key={d.edge_no} className="flex gap-2"><span className="w-12 shrink-0 tabular-nums text-slate-500">{dayLabel(d.announced)}</span>
                <span className="text-slate-300">{d.subject ?? d.title}
                  {d.dividend && <span className="ml-1 text-violet-300">₱{d.dividend.per_share}/sh</span>}
                  {d.insider && <span className={`ml-1 ${d.insider.side === "bought" ? "text-emerald-300" : "text-red-300"}`}>{d.insider.side} {num(Math.abs(d.insider.net_shares))}</span>}</span>
                <a className="ml-auto shrink-0 text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={edgeLink(d.edge_no)}>↗</a></li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/** The chart dock at the bottom of the page: daily bars from PSE EDGE with the same six EMAs as Pulse, the name's numbers and filings,
 *  and previous / next through the list it was opened from. (TradingView's free embed does not carry PSE symbols, so the chart is drawn
 *  here and TradingView opens in a new tab.) */
export function PhChartDock() {
  const { selected, list, select } = usePhSelect();
  const [v, setV] = useState<PhSymbolView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const idx = list.indexOf(selected);
  const [off, setOff] = useState<string[]>([]);

  useEffect(() => {
    let off = false;
    setV(null); setErr(null); setHover(null);
    fetch(`/api/ph/symbol?s=${encodeURIComponent(selected)}`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((j) => { if (!off) setV(j); }).catch((e) => { if (!off) setErr(String(e.message ?? e)); });
    return () => { off = true; };
  }, [selected]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.tagName === "INPUT" || (e.target as HTMLElement)?.tagName === "SELECT" || !list.length) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        const i = list.indexOf(selected);
        const j = (i < 0 ? 0 : i + (e.key === "ArrowRight" ? 1 : -1) + list.length) % list.length;
        select(list[j]); e.preventDefault();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [list, selected, select]);

  const hb = hover !== null && v?.bars ? v.bars[hover] : null;
  const step = (d: number) => { if (list.length) select(list[(((idx < 0 ? 0 : idx + d) % list.length) + list.length) % list.length]); };
  return (
    <section id="ph-dock" className="mb-4 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Chart review</div>
        <div className="text-lg font-bold text-slate-100">{v?.symbol ?? selected}</div>
        <div className="text-xs text-slate-400">{v?.name ?? ""}{v?.subsector ? ` · ${v.subsector}` : ""}</div>
        <a className="text-xs text-slate-400 underline hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={`https://www.tradingview.com/chart/?symbol=${selected === "PSEI" ? "PSE:PSEI" : `PSE:${selected}`}`}>open in TradingView ↗</a>
        <a className="text-xs text-slate-500 underline hover:text-slate-200" href="#ph-top">↑ lists</a>
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-400">
          <button onClick={() => step(-1)} disabled={!list.length} className="rounded border border-slate-700 px-2 py-0.5 hover:bg-slate-800 disabled:opacity-30">← prev</button>
          <span className="tabular-nums">{list.length ? `${idx >= 0 ? idx + 1 : "–"} of ${list.length}` : "click a ticker to start a review list"}</span>
          <button onClick={() => step(1)} disabled={!list.length} className="rounded border border-slate-700 px-2 py-0.5 hover:bg-slate-800 disabled:opacity-30">next →</button>
        </div>
      </div>
      {err && <p className="text-xs text-amber-300">could not load {selected}: {err}</p>}
      {!v && !err && <p className="text-xs text-slate-500">loading…</p>}
      {v && (
        <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
          <div>
            <div className="mb-1 h-4 text-[0.68rem] tabular-nums text-slate-400">
              {hb ? `${hb[0]}  O ${price(hb[1])}  H ${price(hb[2])}  L ${price(hb[3])}  C ${price(hb[4])}  ₱ ${peso(hb[5]).slice(1)}` : v.kind === "index" && hover !== null && v.line?.[hover] ? `${v.line[hover][0]}  ${v.line[hover][1].toLocaleString()}` : ""}
            </div>
            <Chart v={v} hover={hover} setHover={setHover} events={(v.events ?? []).filter((e) => !off.includes(e.type))} />
            {v.kind === "stock" && (v.events ?? []).length > 0 && (
              <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-[0.62rem] text-slate-500">
                <span>filings on the chart (click a marker to open it on EDGE):</span>
                {(Object.keys(EV_STYLE) as Ev["type"][]).filter((t) => (v.events ?? []).some((e) => e.type === t)).map((t) => (
                  <label key={t} className="flex cursor-pointer items-center gap-1">
                    <input type="checkbox" checked={!off.includes(t)} onChange={() => setOff(off.includes(t) ? off.filter((x) => x !== t) : [...off, t])} />
                    <span className={EV_STYLE[t].cls}>{t === "I" ? "▲▼" : t}</span> {EV_STYLE[t].name} {(v.events ?? []).filter((e) => e.type === t).length}
                  </label>
                ))}
              </div>
            )}
            {v.kind === "stock" && (
              <div className="mt-1 flex gap-3 text-[0.6rem] text-slate-500">
                {EMA_STYLE.map((e) => <span key={e.n}><span className={e.cls}>—</span> {e.n}</span>)}<span>daily bars from PSE EDGE · {v.bars?.length ?? 0} sessions · volume bars = pesos traded</span>
              </div>
            )}
          </div>
          <Facts v={v} />
        </div>
      )}
    </section>
  );
}
