"use client";

import { useState } from "react";
import type { ErpBlock } from "@/lib/types";

/**
 * The ERP history chart with three switches: the S&P 500 (log scale, right axis), the T-bond rate, and the gap panel.
 * Inline SVG, theme colours from CSS variables so it follows light and dark. The only client state is which lines show.
 */
const W = 880;
const L = 44;
const R = 44; // room for the S&P 500 axis labels
const X0 = 1960;
const X1 = 2027;
const SPX_LO = 40; // log-scale bounds for the overlay
const SPX_HI = 12000;
const SPX_TICKS = [100, 300, 1000, 3000, 10000];

function yearFrac(d: string): number {
  const y = Number(d.slice(0, 4));
  const m = Number(d.slice(5, 7));
  return y + (m - 1) / 12 + (d.slice(5) === "12-31" ? 11 / 12 : 0);
}

function Switch({ on, label, onClick }: { on: boolean; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      onClick={onClick}
      className={`rounded border px-2 py-0.5 text-[0.68rem] ${
        on ? "border-slate-500 bg-slate-800 text-slate-100" : "border-slate-800 text-slate-500 hover:text-slate-300"
      }`}
    >
      <span aria-hidden="true">{on ? "● " : "○ "}</span>
      {label}
    </button>
  );
}

export function ErpChart({ e }: { e: ErpBlock }) {
  const [spx, setSpx] = useState(false);
  const [bond, setBond] = useState(true);
  const [gapPanel, setGapPanel] = useState(true);

  const H = gapPanel ? 330 : 190;
  const TOP = { a: 18, b: 168 };
  const BOT = { a: 200, b: 316 };

  const pointsOf = (k: "erp" | "tbond") => [
    ...e.history.annual.filter((p) => p[k] !== null).map((p) => ({ x: yearFrac(p.d), v: p[k] as number })),
    ...e.history.monthly.map((p) => ({ x: yearFrac(p.d), v: p[k] })),
  ];
  const erp = pointsOf("erp");
  const tb = pointsOf("tbond");
  const tbByX = new Map(tb.map((p) => [p.x, p.v]));
  const gap = erp.filter((p) => tbByX.has(p.x)).map((p) => ({ x: p.x, v: p.v - (tbByX.get(p.x) as number) }));
  const spxPts = (e.history.spx ?? []).map((p) => ({ x: yearFrac(p.d), v: p.c }));

  const sx = (x: number) => L + ((x - X0) / (X1 - X0)) * (W - L - R);
  const sy1 = (v: number) => TOP.b - (v / 16) * (TOP.b - TOP.a);
  const sy2 = (v: number) => BOT.b - ((v + 9) / 14) * (BOT.b - BOT.a);
  const sySpx = (v: number) =>
    TOP.b - ((Math.log10(v) - Math.log10(SPX_LO)) / (Math.log10(SPX_HI) - Math.log10(SPX_LO))) * (TOP.b - TOP.a);
  const line = (ps: { x: number; v: number }[], sy: (v: number) => number) =>
    ps.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.v).toFixed(1)}`).join("");
  const area = gap.slice(1).map((p, i) => {
    const a = gap[i];
    const z = sy2(0);
    return {
      d: `M${sx(a.x).toFixed(1)},${z} L${sx(a.x).toFixed(1)},${sy2(a.v).toFixed(1)} L${sx(p.x).toFixed(1)},${sy2(p.v).toFixed(1)} L${sx(p.x).toFixed(1)},${z}Z`,
      neg: (a.v + p.v) / 2 < 0,
      k: p.x,
    };
  });
  const events: [number, string][] = [[1971.62, "1971"], [1999.9, "1999"], [2008.95, "2008"], [2020.25, "2020"], [2022.75, "2022"]];
  const last = erp[erp.length - 1];
  const neutral = { fill: "var(--cgi-neutral)" };
  const bottom = gapPanel ? BOT.b : TOP.b;

  return (
    <div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-[0.62rem] uppercase tracking-wide text-slate-500">Show</span>
        <Switch on={spx} label="S&P 500 (log scale, right axis)" onClick={() => setSpx(!spx)} />
        <Switch on={bond} label="10-year T-bond rate" onClick={() => setBond(!bond)} />
        <Switch on={gapPanel} label="ERP minus T-bond panel" onClick={() => setGapPanel(!gapPanel)} />
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="mt-2 w-full" role="img" aria-label="Implied equity risk premium since 1961 with optional T-bond rate, gap and S&P 500">
        {[0, 4, 8, 12, 16].map((v) => (
          <g key={`g1-${v}`}>
            <line x1={L} x2={W - R} y1={sy1(v)} y2={sy1(v)} style={{ stroke: "var(--cgi-rule)" }} />
            <text x={L - 6} y={sy1(v) + 4} textAnchor="end" fontSize={10} style={neutral}>{v}%</text>
          </g>
        ))}
        {gapPanel &&
          [-8, -4, 0, 4].map((v) => (
            <g key={`g2-${v}`}>
              <line x1={L} x2={W - R} y1={sy2(v)} y2={sy2(v)} style={{ stroke: v === 0 ? "var(--cgi-neutral)" : "var(--cgi-rule)" }} />
              <text x={L - 6} y={sy2(v) + 4} textAnchor="end" fontSize={10} style={neutral}>{v > 0 ? `+${v}` : v}</text>
            </g>
          ))}
        {[1960, 1970, 1980, 1990, 2000, 2010, 2020].map((y) => (
          <text key={y} x={sx(y)} y={H - 2} textAnchor="middle" fontSize={10} style={neutral}>{y}</text>
        ))}
        {events.map(([x, label]) => (
          <g key={label}>
            <line x1={sx(x)} x2={sx(x)} y1={TOP.a} y2={bottom} strokeDasharray="4 4" style={{ stroke: "var(--cgi-gold)", opacity: 0.55 }} />
            <text x={sx(x)} y={11} textAnchor="middle" fontSize={9} style={{ fill: "var(--cgi-gold)" }}>{label}</text>
          </g>
        ))}
        {spx && (
          <g>
            {SPX_TICKS.map((v) => (
              <text key={`s-${v}`} x={W - R + 6} y={sySpx(v) + 4} fontSize={10} style={{ fill: "var(--cgi-muted-blue)" }}>{v.toLocaleString("en-US")}</text>
            ))}
            <path d={line(spxPts, sySpx)} fill="none" strokeWidth={1.4} strokeDasharray="5 3" style={{ stroke: "var(--cgi-muted-blue)", opacity: 0.95 }} />
          </g>
        )}
        {gapPanel && area.map((a) => <path key={a.k} d={a.d} style={{ fill: a.neg ? "var(--cgi-down)" : "var(--cgi-up)", opacity: 0.35 }} />)}
        {gapPanel && <path d={line(gap, sy2)} fill="none" strokeWidth={1.2} style={{ stroke: "var(--cgi-neutral)" }} />}
        {bond && <path d={line(tb, sy1)} fill="none" strokeWidth={2} style={{ stroke: "var(--cgi-warn)" }} />}
        <path d={line(erp, sy1)} fill="none" strokeWidth={2.4} style={{ stroke: "var(--cgi-accent)" }} />
        <circle cx={sx(last.x)} cy={sy1(last.v)} r={3.5} style={{ fill: "var(--cgi-accent)" }} />
        <text x={L + 4} y={TOP.a + 12} fontSize={10} style={{ fill: "var(--cgi-accent)" }}>— implied ERP</text>
        {bond && <text x={L + 90} y={TOP.a + 12} fontSize={10} style={{ fill: "var(--cgi-warn)" }}>— 10-year T-bond rate</text>}
        {spx && <text x={L + (bond ? 224 : 90)} y={TOP.a + 12} fontSize={10} style={{ fill: "var(--cgi-muted-blue)" }}>- - S&amp;P 500 (log)</text>}
        {gapPanel && (
          <text x={L + 4} y={BOT.a - 6} fontSize={10} style={neutral}>ERP minus T-bond, percentage points (green: premium above the bond rate; red: below)</text>
        )}
      </svg>
    </div>
  );
}
