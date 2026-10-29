"use client";

import { useMemo } from "react";
import { HudGroup, HudTicker } from "@/lib/types";
import { benchmarkRow, isPriceGroup, isStale, mean, num, quadrant, Quadrant, relStrength } from "@/lib/tapeMath";
import { fmtSigned } from "./format";

type Dot = { id: string; label: string; x: number; y: number; q: Quadrant; sym?: string; n?: number };

const W = 640, H = 420, PAD = 36;
const Q_ORDER: Quadrant[] = ["leading", "weakening", "improving", "lagging"];
const Q_NOTE: Record<Quadrant, string> = {
  leading: "ahead over 3M and 1M",
  weakening: "ahead over 3M, behind over 1M",
  improving: "behind over 3M, ahead over 1M",
  lagging: "behind over 3M and 1M",
};

const DEFAULT_GROUP = "SECTOR ETF";

export function TapeRotation({
  groups,
  latest,
  onSelect,
  group,
  onGroup,
}: {
  groups: HudGroup[];
  latest: string;
  onSelect: (symbol: string) => void;
  group: string | null;
  onGroup: (g: string) => void;
}) {
  const priceGroups = groups.filter((g) => isPriceGroup(g) && g.tickers.length > 0);
  // Opens on the sectors; "__groups__" is the overview of every group against SPX. An unknown name falls back the same way.
  const known = (n: string | null) => n === "__groups__" || priceGroups.some((g) => g.name === n);
  const mode = known(group) ? (group as string) : priceGroups.some((g) => g.name === DEFAULT_GROUP) ? DEFAULT_GROUP : "__groups__";
  const setMode = onGroup;
  const spx = benchmarkRow(groups, "SPX");

  const { dots, benchName, excluded } = useMemo(() => {
    const out: Dot[] = [];
    let ex = 0;
    if (mode === "__groups__") {
      for (const g of priceGroups) {
        if (g.default_rs_denom !== "SPX") continue;
        const live = g.tickers.filter((t) => !isStale(t, latest));
        const x = mean(live.map((t) => relStrength(t, spx, "pct_3m")));
        const y = mean(live.map((t) => relStrength(t, spx, "pct_1m")));
        ex += g.tickers.length - live.length;
        if (num(x) && num(y)) out.push({ id: g.name, label: g.name, x, y, q: quadrant(x, y), n: live.length });
      }
      return { dots: out, benchName: "SPX", excluded: ex };
    }
    const g = priceGroups.find((x) => x.name === mode);
    const bench = g ? benchmarkRow(groups, g.default_rs_denom) : undefined;
    for (const t of g?.tickers ?? []) {
      if (isStale(t, latest) || t.symbol === g?.default_rs_denom) {
        ex += isStale(t, latest) ? 1 : 0;
        continue;
      }
      const x = relStrength(t, bench, "pct_3m"), y = relStrength(t, bench, "pct_1m");
      if (num(x) && num(y)) out.push({ id: t.symbol, label: t.symbol, sym: t.symbol, x, y, q: quadrant(x, y) });
      else ex += 1;
    }
    return { dots: out, benchName: g?.default_rs_denom ?? "—", excluded: ex };
  }, [mode, groups, latest]); // eslint-disable-line react-hooks/exhaustive-deps

  const lim = Math.max(5, Math.ceil(Math.max(0, ...dots.flatMap((d) => [Math.abs(d.x), Math.abs(d.y)])) * 1.1));
  const sx = (v: number) => PAD + ((v + lim) / (2 * lim)) * (W - 2 * PAD);
  const sy = (v: number) => H - PAD - ((v + lim) / (2 * lim)) * (H - 2 * PAD);
  // Label only the dots farthest from the centre; the rest are readable from the lists and the hover text.
  const labelled = new Set([...dots].sort((a, b) => Math.hypot(b.x, b.y) - Math.hypot(a.x, a.y)).slice(0, 14).map((d) => d.id));
  const byQ = (q: Quadrant) => dots.filter((d) => d.q === q).sort((a, b) => b.x + b.y - (a.x + a.y));

  const click = (d: Dot) => (d.sym ? onSelect(d.sym) : setMode(d.id));

  return (
    <section aria-label="Rotation">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <label className="text-[0.65rem] uppercase tracking-wide text-slate-500" htmlFor="rot-mode">Show</label>
        <select
          id="rot-mode"
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="rounded border border-[var(--cgi-rule)] bg-[var(--cgi-surface)] px-2 py-1 text-[0.72rem] text-slate-200"
        >
          <option value="__groups__">Groups against SPX</option>
          {priceGroups.map((g) => (
            <option key={g.name} value={g.name}>{g.name} (against {g.default_rs_denom})</option>
          ))}
        </select>
        <span className="text-[0.62rem] text-slate-500">
          across: 3M return minus {benchName}'s · up: 1M return minus {benchName}'s{excluded ? ` · ${excluded} stale row${excluded === 1 ? "" : "s"} left out` : ""}
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-3xl" role="img" aria-label="Rotation quadrants">
        <rect x={PAD} y={PAD} width={W - 2 * PAD} height={H - 2 * PAD} fill="var(--cgi-surface-alt)" stroke="var(--cgi-rule)" />
        <line x1={sx(0)} x2={sx(0)} y1={PAD} y2={H - PAD} stroke="var(--cgi-null)" strokeDasharray="3 3" />
        <line x1={PAD} x2={W - PAD} y1={sy(0)} y2={sy(0)} stroke="var(--cgi-null)" strokeDasharray="3 3" />
        <text x={W - PAD - 6} y={PAD + 14} textAnchor="end" fontSize={11} fill="var(--cgi-up)">Leading</text>
        <text x={W - PAD - 6} y={H - PAD - 6} textAnchor="end" fontSize={11} fill="var(--cgi-warn)">Weakening</text>
        <text x={PAD + 6} y={PAD + 14} fontSize={11} fill="var(--cgi-accent)">Improving</text>
        <text x={PAD + 6} y={H - PAD - 6} fontSize={11} fill="var(--cgi-down)">Lagging</text>
        <text x={W / 2} y={H - 8} textAnchor="middle" fontSize={10} fill="var(--cgi-neutral)">3M vs {benchName} (points)</text>
        <text x={12} y={H / 2} textAnchor="middle" fontSize={10} fill="var(--cgi-neutral)" transform={`rotate(-90 12 ${H / 2})`}>1M vs {benchName}</text>
        <text x={W - PAD} y={sy(0) - 4} textAnchor="end" fontSize={9} fill="var(--cgi-null)">+{lim}</text>
        <text x={PAD} y={sy(0) - 4} fontSize={9} fill="var(--cgi-null)">−{lim}</text>
        {dots.map((d) => (
          <g key={d.id} onClick={() => click(d)} style={{ cursor: "pointer" }}>
            <title>{`${d.label}: 3M ${fmtSigned(d.x)} pts, 1M ${fmtSigned(d.y)} pts vs ${benchName} (${d.q})${d.n ? ` · ${d.n} rows` : ""}`}</title>
            <circle cx={sx(d.x)} cy={sy(d.y)} r={d.n ? 6 : 4} fill={d.q === "leading" ? "var(--cgi-up)" : d.q === "lagging" ? "var(--cgi-down)" : d.q === "weakening" ? "var(--cgi-warn)" : "var(--cgi-accent)"} fillOpacity={0.8} />
            {labelled.has(d.id) && (
              <text x={sx(d.x) + 7} y={sy(d.y) + 3} fontSize={9} fill="var(--cgi-neutral)">{d.label}</text>
            )}
          </g>
        ))}
      </svg>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {Q_ORDER.map((q) => (
          <div key={q} className="rounded border border-[var(--cgi-rule)] p-2">
            <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">{q} · {byQ(q).length}</div>
            <div className="mb-1 text-[0.6rem] text-slate-500">{Q_NOTE[q]}</div>
            <div className="flex flex-wrap gap-1 text-[0.7rem]">
              {byQ(q).map((d) => (
                <button key={d.id} type="button" onClick={() => click(d)} className="rounded bg-[var(--cgi-surface)] px-1.5 py-0.5 text-slate-200 hover:ring-1 hover:ring-[var(--cgi-accent)]">
                  {d.label}
                </button>
              ))}
              {byQ(q).length === 0 && <span className="text-slate-500">none</span>}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[0.62rem] text-slate-500">
        Describes what has already happened against the benchmark; it is not a forecast. {mode === "__groups__" ? "Click a group to open its dots." : "Click a dot or a name to load its chart."}
      </p>
    </section>
  );
}
