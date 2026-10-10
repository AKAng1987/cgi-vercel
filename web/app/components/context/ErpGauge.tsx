import type { ErpBlock } from "@/lib/types";

/**
 * Valuation cushion: Damodaran's implied equity risk premium against the 10-year T-bond rate he subtracts.
 * Descriptive. It says how stocks are priced against bonds, not what they will earn, and it moves with
 * price, the bond rate and analysts' cash-flow forecasts, so part of it is the same information as price.
 *
 * Inline SVG, no chart library, colours from the theme variables so it follows light and dark.
 */
const W = 880;
const H = 330;
const L = 44;
const R = 12;
const X0 = 1960;
const X1 = 2027;
const TOP = { a: 14, b: 168 }; // ERP + T-bond panel
const BOT = { a: 200, b: 316 }; // gap panel

function yearFrac(d: string): number {
  const y = Number(d.slice(0, 4));
  const m = Number(d.slice(5, 7));
  return y + (m - 1) / 12 + (d.slice(5) === "12-31" ? 11 / 12 : 0);
}
const pct = (v: number | null | undefined, dp = 2) => (v === null || v === undefined ? "n/a" : `${v.toFixed(dp)}%`);
const pts = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(2)} pts`;

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
      <div className="text-[0.62rem] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-2xl font-bold tabular-nums text-slate-100">{value}</div>
      {sub && <div className="text-[0.65rem] text-slate-500">{sub}</div>}
    </div>
  );
}

function Chart({ e }: { e: ErpBlock }) {
  const pointsOf = (k: "erp" | "tbond") => [
    ...e.history.annual.filter((p) => p[k] !== null).map((p) => ({ x: yearFrac(p.d), v: p[k] as number })),
    ...e.history.monthly.map((p) => ({ x: yearFrac(p.d), v: p[k] })),
  ];
  const erp = pointsOf("erp");
  const tb = pointsOf("tbond");
  const tbByX = new Map(tb.map((p) => [p.x, p.v]));
  const gap = erp.filter((p) => tbByX.has(p.x)).map((p) => ({ x: p.x, v: p.v - (tbByX.get(p.x) as number) }));

  const sx = (x: number) => L + ((x - X0) / (X1 - X0)) * (W - L - R);
  const sy1 = (v: number) => TOP.b - (v / 15) * (TOP.b - TOP.a);
  const sy2 = (v: number) => BOT.b - ((v + 9) / 14) * (BOT.b - BOT.a);
  const line = (ps: { x: number; v: number }[], sy: (v: number) => number) =>
    ps.map((p, i) => `${i ? "L" : "M"}${sx(p.x).toFixed(1)},${sy(p.v).toFixed(1)}`).join("");
  const area = gap
    .slice(1)
    .map((p, i) => {
      const a = gap[i];
      const z = sy2(0);
      return { d: `M${sx(a.x).toFixed(1)},${z} L${sx(a.x).toFixed(1)},${sy2(a.v).toFixed(1)} L${sx(p.x).toFixed(1)},${sy2(p.v).toFixed(1)} L${sx(p.x).toFixed(1)},${z}Z`, neg: (a.v + p.v) / 2 < 0, k: p.x };
    });
  const events: [number, string][] = [[1999.9, "1999"], [2008.95, "2008"], [2020.25, "2020"], [2022.75, "2022"]];
  const last = erp[erp.length - 1];
  const t = { color: "var(--cgi-neutral)" } as const;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label="Implied equity risk premium and the 10-year T-bond rate since 1961, with their gap">
      {[0, 3, 6, 9, 12, 15].map((v) => (
        <g key={`g1-${v}`}>
          <line x1={L} x2={W - R} y1={sy1(v)} y2={sy1(v)} style={{ stroke: "var(--cgi-rule)" }} />
          <text x={L - 6} y={sy1(v) + 4} textAnchor="end" fontSize={10} style={{ fill: t.color }}>{v}%</text>
        </g>
      ))}
      {[-8, -4, 0, 4].map((v) => (
        <g key={`g2-${v}`}>
          <line x1={L} x2={W - R} y1={sy2(v)} y2={sy2(v)} style={{ stroke: v === 0 ? "var(--cgi-neutral)" : "var(--cgi-rule)" }} />
          <text x={L - 6} y={sy2(v) + 4} textAnchor="end" fontSize={10} style={{ fill: t.color }}>{v > 0 ? `+${v}` : v}</text>
        </g>
      ))}
      {[1960, 1970, 1980, 1990, 2000, 2010, 2020].map((y) => (
        <text key={y} x={sx(y)} y={H - 2} textAnchor="middle" fontSize={10} style={{ fill: t.color }}>{y}</text>
      ))}
      {events.map(([x, label]) => (
        <g key={label}>
          <line x1={sx(x)} x2={sx(x)} y1={TOP.a} y2={BOT.b} strokeDasharray="4 4" style={{ stroke: "var(--cgi-gold)", opacity: 0.55 }} />
          <text x={sx(x)} y={9} textAnchor="middle" fontSize={9} style={{ fill: "var(--cgi-gold)" }}>{label}</text>
        </g>
      ))}
      {area.map((a) => (
        <path key={a.k} d={a.d} style={{ fill: a.neg ? "var(--cgi-down)" : "var(--cgi-up)", opacity: 0.35 }} />
      ))}
      <path d={line(gap, sy2)} fill="none" strokeWidth={1.2} style={{ stroke: "var(--cgi-neutral)" }} />
      <path d={line(tb, sy1)} fill="none" strokeWidth={2} style={{ stroke: "var(--cgi-warn)" }} />
      <path d={line(erp, sy1)} fill="none" strokeWidth={2.4} style={{ stroke: "var(--cgi-accent)" }} />
      <circle cx={sx(last.x)} cy={sy1(last.v)} r={3.5} style={{ fill: "var(--cgi-accent)" }} />
      <text x={L + 4} y={TOP.a + 12} fontSize={10} style={{ fill: "var(--cgi-accent)" }}>— implied ERP</text>
      <text x={L + 90} y={TOP.a + 12} fontSize={10} style={{ fill: "var(--cgi-warn)" }}>— 10-year T-bond rate</text>
      <text x={L + 4} y={BOT.a - 6} fontSize={10} style={{ fill: t.color }}>ERP minus T-bond, percentage points (green: premium above the bond rate; red: below)</text>
    </svg>
  );
}

export function ErpGauge({ e }: { e?: ErpBlock }) {
  if (!e) return null;
  if (!e.available) {
    return (
      <div>
        <div className="mb-2 text-[0.72rem] uppercase tracking-wide text-slate-400">Valuation cushion (equity risk premium)</div>
        <p className="text-xs text-slate-500">Not available: {e.why ?? "no data"}.</p>
      </div>
    );
  }
  const c = e.current;
  const s = e.since_2008;
  const rankText =
    s.erp_rank_lowest === 1 ? `lowest of ${s.n_months} months since Sep 2008` : `${s.erp_rank_lowest}th lowest of ${s.n_months} months since Sep 2008`;
  const bandText = s.band === "bottom10" ? "bottom 10% of months since 2008" : s.band === "top10" ? "top 10% of months since 2008" : "middle of the range since 2008";
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.72rem] uppercase tracking-wide text-slate-400">Valuation cushion (equity risk premium)</div>
        <div className="text-[0.66rem] text-slate-500">{e.label} · as of {e.as_of}</div>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile label="Implied ERP" value={pct(c.erp)} sub={`${rankText} · ${bandText}`} />
        <Tile label="10-year T-bond rate" value={pct(c.tbond)} sub="the safe return he subtracts" />
        <Tile label="ERP minus T-bond" value={pts(c.gap)} sub={e.dotcom_1999 && e.dotcom_1999.gap !== null ? `1999: ${pts(e.dotcom_1999.gap)}` : undefined} />
        <Tile
          label="High-yield spread"
          value={e.hy_spread ? `${Math.round(e.hy_spread.bp)} bp` : "n/a"}
          sub={e.hy_spread ? `${e.hy_spread.percentile_since_2008}th percentile since 2008 · the bond market's own premium` : "credit-market premium, not available"}
        />
      </div>
      <p className="mt-2 max-w-4xl text-[0.72rem] leading-relaxed text-slate-400">
        {e.last_this_low ? <>The premium was last this thin at the end of {e.last_this_low.date.slice(0, 4)} ({pct(e.last_this_low.erp)}). </> : null}
        {e.dotcom_1999 ? <>At the 1999 low it was {pct(e.dotcom_1999.erp)} against a {pct(e.dotcom_1999.tbond)} T-bond. </> : null}
        Since 2008 it has ranged from {pct(s.low.erp)} ({s.low.date.slice(0, 7)}) to {pct(s.high.erp)} ({s.high.date.slice(0, 7)}), median {pct(s.median_erp)}.
        {c.expected_return !== null && c.expected_return !== undefined ? <> Expected return on stocks implied by the same model: {pct(c.expected_return)}.</> : null}
      </p>
      <Chart e={e} />
      {e.freshness.behind && (
        <p className="mt-1 text-[0.66rem] text-amber-400">
          Waiting for this month&apos;s update: newest month held is {e.freshness.newest_month}, expected {e.freshness.expected_month}.
        </p>
      )}
      <p className="mt-2 max-w-4xl text-[0.66rem] leading-relaxed text-slate-600">
        Source: {e.source}. {e.caveats.join(" ")}
      </p>
    </div>
  );
}
