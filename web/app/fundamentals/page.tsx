import { apiFetch } from "@/lib/api";
import { FundamentalsResponse, FundCompany, FundRollup } from "@/lib/types";

const VERDICT_COLOR: Record<string, string> = {
  capturing: "text-emerald-400",
  accelerating: "text-emerald-300",
  "buying growth": "text-amber-300",
  holding: "text-slate-400",
  slowing: "text-orange-400",
  "rolling over": "text-rose-400",
  unknown: "text-slate-600",
};

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

function bn(v: number | null | undefined) {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return `$${(v / 1e9).toFixed(1)}bn`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(0)}m`;
  return `$${v.toFixed(0)}`;
}

/** Sparkline of the YoY series — the shape of the acceleration, which is the
 *  whole point: a falling line at a high level is still decelerating. */
function Spark({ pts }: { pts: number[] }) {
  if (pts.length < 3) return null;
  const w = 64;
  const h = 16;
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const span = hi - lo || 1;
  const d = pts
    .map((v, i) => `${(i / (pts.length - 1)) * w},${h - ((v - lo) / span) * h}`)
    .join(" ");
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

function RollupRow({ label, r, wide, fallback }: { label: string; r: FundRollup & { constituents: string[] }; wide?: boolean; fallback?: boolean }) {
  if (r.status !== "ok") {
    return (
      <div className="flex items-baseline gap-3 border-b border-slate-900 py-1.5 text-[0.72rem]">
        <span className={`${wide ? "w-32" : "w-40"} shrink-0 text-slate-300`}>{label}</span>
        <span className="text-slate-600">
          {r.constituents.length === 0 ? "nothing listable yet" : "no data"}
        </span>
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-slate-900 py-1.5 text-[0.72rem]">
      <span className={`${wide ? "w-32" : "w-40"} shrink-0 text-slate-200`}>{label}</span>
      <span className="w-20 shrink-0 tabular-nums">{sign(r.median_revenue_acceleration_pp)}</span>
      <span className="w-8 shrink-0 text-slate-600">n={r.n}</span>
      <span className="flex flex-wrap gap-1">
        {Object.entries(r.verdicts ?? {}).map(([v, c]) => (
          <span key={v} className={`rounded bg-slate-900 px-1.5 text-[0.6rem] ${VERDICT_COLOR[v] ?? "text-slate-400"}`}>
            {c} {v}
          </span>
        ))}
      </span>
      {r.leaders && r.leaders.length > 0 && (
        <span className="text-[0.65rem] text-slate-500">lead {r.leaders.join(" ")}</span>
      )}
      {r.constituents.length > 0 && (
        <span className="text-[0.62rem] text-slate-600" title={r.constituents.join(" ")}>
          {r.constituents.slice(0, 5).join(" ")}
        </span>
      )}
      {fallback && (
        <span className="rounded bg-amber-950 px-1.5 text-[0.6rem] text-amber-300">
          hand-seeded
        </span>
      )}
    </div>
  );
}

function CompanyRow({ c }: { c: FundCompany }) {
  const r = c.revenue;
  const m = c.margin;
  const ruin = c.risk_of_ruin;
  const hist = (r.history ?? []).map((h) => h.yoy_pct).filter((v): v is number => v !== null);
  return (
    <tr className="border-b border-slate-900/70 hover:bg-slate-900/40">
      <td className="py-1 pr-2 font-mono text-slate-200">{c.symbol}</td>
      <td className={`py-1 pr-3 text-[0.68rem] ${VERDICT_COLOR[c.read.verdict] ?? "text-slate-400"}`}>
        {c.read.verdict}
      </td>
      <td className="py-1 pr-2 text-right tabular-nums text-slate-300">
        {r.yoy_pct !== null && r.yoy_pct !== undefined ? `${r.yoy_pct.toFixed(1)}%` : "—"}
      </td>
      <td className="py-1 pr-2 text-right tabular-nums">{sign(r.acceleration_pp)}</td>
      <td className="py-1 pr-3">
        <Spark pts={[...hist].reverse()} />
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
      <td className="py-1 text-right tabular-nums">
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
    </tr>
  );
}

export default async function FundamentalsPage() {
  const d = await apiFetch<FundamentalsResponse>("/api/fundamentals");
  const live = d.themes.filter((t) => t.is_live);
  const rest = d.themes.filter((t) => !t.is_live);
  const byAccel = [...d.companies].sort(
    (a, b) => (b.revenue.acceleration_pp ?? -1e9) - (a.revenue.acceleration_pp ?? -1e9)
  );

  return (
    <main className="mx-auto max-w-5xl p-6">
      <h1 className="mb-1 text-2xl font-bold">FUNDAMENTALS</h1>
      <p className="mb-5 text-xs leading-relaxed text-slate-400">
        Layer 3: themes say the trade is working — this says{" "}
        <span className="text-slate-200">who inside it is capturing the money</span>. Damodaran&apos;s
        five, all as rate of change, because the level is priced and the change in the level
        re-rates. Constituents are the top 5 by weight of what each theme&apos;s ETFs{" "}
        <span className="text-slate-200">actually hold</span> — State Street&apos;s daily files
        where they exist, SEC N-PORT everywhere else — not a list anyone typed. Every figure is
        the{" "}
        <span className="text-slate-200">second derivative</span>: a company going from +30% to +20%
        revenue growth is decelerating while still growing fast.
      </p>

      {d.changes && d.changes.length > 0 && (
        <section className="mb-7">
          <div className="mb-2 flex items-baseline gap-3">
            <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
              Changed on the latest filings · {d.changes.length}
            </div>
            {d.surprise_thresholds && (
              <div className="text-[0.65rem] text-slate-500">
                &ldquo;sudden&rdquo; is {d.surprise_thresholds.up_pp}pp / {d.surprise_thresholds.down_pp}pp
                — the p95 and p5 of {d.surprise_thresholds.measured.n.toLocaleString()} measured
                company-quarters, not a round number
              </div>
            )}
          </div>
          <div className="space-y-1">
            {d.changes.map((c, i) => (
              <div
                key={i}
                className={`flex flex-wrap items-baseline gap-2 border-l-2 pl-2 text-[0.72rem] ${
                  c.kind === "fundamentals_surprise"
                    ? c.direction === "up"
                      ? "border-emerald-700"
                      : "border-rose-700"
                    : "border-slate-700"
                }`}
              >
                <span className="font-mono text-slate-200">{c.symbol}</span>
                <span className="text-slate-600">{c.as_of}</span>
                <span className="text-slate-300">{c.detail}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mb-7">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
          The AI layer cake · are the layers moving together?
        </div>
        <p className="mb-2 text-[0.7rem] text-slate-500">
          The standing thesis says they are not. Median revenue acceleration per layer:
        </p>
        {d.ai_layers.map((l) => (
          <RollupRow key={l.layer} label={l.layer} r={l} wide />
        ))}
      </section>

      {live.length > 0 && (
        <section className="mb-7">
          <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
            Themes running on RS · {live.length}
          </div>
          {live.map((t) => (
            <RollupRow key={t.theme} label={t.theme} r={t} fallback={t.source?.startsWith("hand")} />
          ))}
        </section>
      )}

      <section className="mb-7">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-slate-600">
          Themes not currently running · {rest.length}
        </div>
        {rest.map((t) => (
          <RollupRow key={t.theme} label={t.theme} r={t} fallback={t.source?.startsWith("hand")} />
        ))}
      </section>

      <section className="mb-7">
        <div className="mb-2 flex items-baseline gap-3">
          <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
            Every name · by revenue acceleration
          </div>
          <div className="text-[0.65rem] text-slate-500">
            {d.coverage.with_data} of {d.coverage.universe} filers
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-[0.72rem]">
            <thead>
              <tr className="border-b border-slate-800 text-[0.6rem] uppercase tracking-wider text-slate-500">
                <th className="pb-1 pr-2 text-left font-medium">sym</th>
                <th className="pb-1 pr-3 text-left font-medium">read</th>
                <th className="pb-1 pr-2 text-right font-medium">rev yoy</th>
                <th className="pb-1 pr-2 text-right font-medium">accel</th>
                <th className="pb-1 pr-3 text-left font-medium">yoy shape</th>
                <th className="pb-1 pr-2 text-right font-medium">margin Δ</th>
                <th className="pb-1 pr-2 text-right font-medium">payout</th>
                <th className="pb-1 pr-2 text-right font-medium">int burden</th>
                <th className="pb-1 text-right font-medium">Z&apos;&apos;</th>
              </tr>
            </thead>
            <tbody>
              {byAccel.map((c) => (
                <CompanyRow key={c.symbol} c={c} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-[0.65rem] text-slate-600">
          * accumulated deficit — Z&apos;&apos; is dragged negative by retained earnings regardless of
          solvency, so the band is withheld. Read FCF and cash instead.
        </p>
      </section>

      <section className="mb-7">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
          Who pays whom · {d.links.length}
        </div>
        <p className="mb-2 text-[0.7rem] text-slate-500">
          The half no vendor sells. Built by hand because the only hard number is the SEC
          10%-customer disclosure — so each link carries its source and confidence, and nothing is
          assumed. Read one company&apos;s result through to a name that has not reported yet.
        </p>
        <div className="space-y-1">
          {d.links.map((l, i) => (
            <div
              key={i}
              className="flex flex-wrap items-baseline gap-2 border-l-2 border-slate-800 pl-2 text-[0.72rem]"
            >
              <span className="font-mono text-slate-200">{l.payer}</span>
              <span className="text-slate-600">pays</span>
              <span className="font-mono text-slate-200">{l.payee ?? "—"}</span>
              <span className="text-slate-400">{l.for}</span>
              <span className="rounded bg-slate-900 px-1.5 text-[0.6rem] text-slate-500">
                {l.importance}
              </span>
              <span
                className={`rounded px-1.5 text-[0.6rem] ${
                  l.confidence === "confirmed"
                    ? "bg-emerald-950 text-emerald-400"
                    : l.confidence === "likely"
                    ? "bg-amber-950 text-amber-300"
                    : "bg-slate-900 text-slate-500"
                }`}
              >
                {l.confidence}
              </span>
              <span className="text-[0.65rem] text-slate-600">{l.source}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="text-[0.65rem] leading-relaxed text-slate-600">
        <div className="mb-1 font-bold uppercase tracking-[2px]">Limits, carried deliberately</div>
        <ul className="list-inside list-disc space-y-0.5">
          {d.limits.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
        <p className="mt-2">
          {d.source} · {d.method}
        </p>
      </section>
    </main>
  );
}
