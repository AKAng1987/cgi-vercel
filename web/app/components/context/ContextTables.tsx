import { ContextResponse, DrawdownWindow, InversionRow } from "@/lib/types";

/**
 * Historical context at the bottom of CGI.
 *
 * The drawdown block leads with WHERE WE ARE NOW rather than with the
 * distribution, because the stated purpose is to see the base rates often
 * enough to stay even keel — a probability without your current position
 * against it is trivia.
 *
 * Every figure carries its n and its window. On five inversion cycles per
 * curve, anything presented without them would be false precision.
 */

function pct(v: number | null | undefined, digits = 1) {
  if (v === null || v === undefined) return <span className="text-slate-600">—</span>;
  const c = v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-slate-400";
  return <span className={`tabular-nums ${c}`}>{v > 0 ? "+" : ""}{v.toFixed(digits)}%</span>;
}

/** A series that does not reach back to an episode's start must say so.
 *  A blank cell reads as zero, and a zero Fed balance sheet is a fact claim. */
function val(v: number | null, fmt: (n: number) => string) {
  return v === null ? <span className="text-slate-600" title="series does not reach back this far">unavailable</span>
                    : <span className="tabular-nums text-slate-300">{fmt(v)}</span>;
}

function Now({ now }: { now: ContextResponse["drawdowns"]["now"] }) {
  const d = now.drawdown_pct;
  const tone = d <= -20 ? "border-rose-800 bg-rose-950/30" : d <= -10 ? "border-amber-800 bg-amber-950/30" : "border-slate-800 bg-slate-900/50";
  return (
    <div className={`mb-3 rounded border px-3 py-2 text-sm ${tone}`}>
      <span className="text-slate-400">SPX </span>
      <span className="tabular-nums text-slate-100">{now.spx.toLocaleString()}</span>
      <span className="text-slate-400"> is </span>
      {pct(d, 2)}
      <span className="text-slate-400"> from its running high of </span>
      <span className="tabular-nums text-slate-300">{now.running_high.toLocaleString()}</span>
      <span className="text-slate-500"> ({now.running_high_date})</span>
      <span className="text-slate-400"> — currently </span>
      <span className="text-slate-200">{now.band}</span>
      <span className="text-slate-500">.</span>
    </div>
  );
}

function Window({ w }: { w: DrawdownWindow }) {
  return (
    <div>
      <div className="mb-1 text-[0.7rem] uppercase tracking-wide text-slate-500">
        {w.label} · {w.start.slice(0, 4)}–{w.end.slice(0, 4)} · {w.years} years
      </div>
      <table className="w-full border-collapse text-[0.78rem]">
        <thead>
          <tr className="border-b border-slate-800 text-left text-[0.68rem] uppercase text-slate-500">
            <th className="py-1 pr-2 font-medium">drawdown</th>
            <th className="py-1 pr-2 font-medium">n</th>
            <th className="py-1 pr-2 font-medium">per yr</th>
            <th className="py-1 pr-2 font-medium">chance in a year</th>
            <th className="py-1 pr-2 font-medium">median days</th>
            <th className="py-1 pr-2 font-medium">most recent</th>
          </tr>
        </thead>
        <tbody>
          {w.buckets.map((b) => (
            <tr key={b.bucket} className="border-b border-slate-900">
              <td className="py-1 pr-2">
                <div className="text-slate-200">{b.bucket}</div>
                <div className="text-[0.66rem] text-slate-500">{b.definition}</div>
              </td>
              <td className="py-1 pr-2 tabular-nums text-slate-400">{b.n}</td>
              <td className="py-1 pr-2 tabular-nums text-slate-300">{b.per_year.toFixed(2)}</td>
              <td className="py-1 pr-2 tabular-nums text-slate-100">{b.prob_1plus_per_year}%</td>
              <td className="py-1 pr-2 tabular-nums text-slate-400">{b.median_days_to_trough ?? "—"}</td>
              <td className="py-1 pr-2 text-[0.7rem] text-slate-500">
                {b.recent.map((r) => `${r.trough.slice(0, 7)} ${r.depth_pct.toFixed(0)}%`).join(" · ") || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Inversions({ rows, label }: { rows: InversionRow[]; label: string }) {
  return (
    <div>
      <div className="mb-1 text-[0.7rem] uppercase tracking-wide text-slate-500">{label}</div>
      <table className="w-full border-collapse text-[0.78rem]">
        <thead>
          <tr className="border-b border-slate-800 text-left text-[0.68rem] uppercase text-slate-500">
            <th className="py-1 pr-2 font-medium">inverts</th>
            <th className="py-1 pr-2 font-medium">de-inverts</th>
            <th className="py-1 pr-2 font-medium">SPX peak</th>
            <th className="py-1 pr-2 font-medium">lead</th>
            <th className="py-1 pr-2 font-medium">drawdown</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.inverts} className="border-b border-slate-900">
              <td className="py-1 pr-2 tabular-nums text-slate-200">
                {r.inverts}
                {r.re_inverted && (
                  <span className="ml-1 text-[0.62rem] text-slate-500" title="un-inverted briefly and re-inverted; counted as one cycle">↻</span>
                )}
              </td>
              <td className="py-1 pr-2 tabular-nums text-slate-400">{r.deinverts ?? <span className="text-amber-300">still inverted</span>}</td>
              <td className="py-1 pr-2 tabular-nums text-slate-400">{r.spx_peak_date ?? "—"}</td>
              <td className="py-1 pr-2">
                {r.months_inversion_to_peak === null ? (
                  <span className="text-slate-600">—</span>
                ) : r.led_the_peak ? (
                  <span className="tabular-nums text-emerald-400">{r.months_inversion_to_peak.toFixed(1)} mo before</span>
                ) : (
                  <span className="tabular-nums text-amber-300" title="the market had already topped when the curve inverted">
                    {Math.abs(r.months_inversion_to_peak).toFixed(1)} mo AFTER the top
                  </span>
                )}
              </td>
              <td className="py-1 pr-2">{pct(r.drawdown_pct)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ContextTables({ ctx }: { ctx: ContextResponse }) {
  const j = ctx.joins.inversion_to_drawdown;
  const bn = (n: number) => `$${(n / 1_000_000).toFixed(1)}tn`; // WALCL is in $mn
  return (
    <section className="mt-8 space-y-6 border-t border-slate-800 pt-6">
      <div>
        <h2 className="mb-1 text-[0.8rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
          Context — how often this happens
        </h2>
        <p className="text-[0.72rem] text-slate-500">
          Computed from held history, not typed in, so these stay current. Every figure carries its n.
        </p>
      </div>

      <div>
        <div className="mb-2 text-[0.72rem] uppercase tracking-wide text-slate-400">S&amp;P drawdowns</div>
        <Now now={ctx.drawdowns.now} />
        <div className="grid gap-5 lg:grid-cols-2">
          {ctx.drawdowns.windows.map((w) => <Window key={w.label} w={w} />)}
        </div>
        <p className="mt-2 text-[0.68rem] text-slate-500">{ctx.drawdowns.method}</p>
        <div className="mt-2 text-[0.7rem] text-slate-500">
          Deepest on record:{" "}
          {ctx.drawdowns.windows[0].deepest.slice(0, 5).map((d) => `${d.peak_date.slice(0, 7)} ${d.depth_pct.toFixed(0)}%`).join(" · ")}
        </div>
      </div>

      <div>
        <div className="mb-2 text-[0.72rem] uppercase tracking-wide text-slate-400">Yield-curve inversions</div>
        <div className="grid gap-5 lg:grid-cols-2">
          {Object.entries(ctx.inversions).map(([label, rows]) => <Inversions key={label} rows={rows} label={label} />)}
        </div>
        <div className="mt-2 space-y-1 text-[0.7rem] text-slate-500">
          {Object.entries(j).map(([label, s]) => (
            <div key={label}>
              <span className="text-slate-400">{label}:</span> {s.n_cycles} cycles, {s.n_led_the_peak} led the top
              {s.median_months_lead !== null && <> · median lead <span className="tabular-nums text-slate-300">{s.median_months_lead} mo</span>
                {s.range_months_lead && <span className="tabular-nums"> (range {s.range_months_lead[0]}–{s.range_months_lead[1]})</span>}</>}
              {s.median_drawdown_pct !== null && <> · median drawdown {pct(s.median_drawdown_pct)}</>}
            </div>
          ))}
          <p className="text-slate-600">{ctx.joins.caveat}</p>
        </div>
      </div>

      <div>
        <div className="mb-2 text-[0.72rem] uppercase tracking-wide text-slate-400">Fed policy episodes</div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] border-collapse text-[0.78rem]">
            <thead>
              <tr className="border-b border-slate-800 text-left text-[0.68rem] uppercase text-slate-500">
                <th className="py-1 pr-2 font-medium">period</th>
                <th className="py-1 pr-2 font-medium">action</th>
                <th className="py-1 pr-2 font-medium">chair</th>
                <th className="py-1 pr-2 font-medium">DXY</th>
                <th className="py-1 pr-2 font-medium">10Y</th>
                <th className="py-1 pr-2 font-medium">balance sheet</th>
                <th className="py-1 pr-2 font-medium">unemp.</th>
                <th className="py-1 pr-2 font-medium">SPX peak → trough</th>
              </tr>
            </thead>
            <tbody>
              {ctx.fed_episodes.episodes.map((e) => (
                <tr key={`${e.start}-${e.action}`} className="border-b border-slate-900 align-top">
                  <td className="py-1 pr-2 whitespace-nowrap">
                    <div className="tabular-nums text-slate-200">{e.start}</div>
                    <div className="tabular-nums text-slate-500">{e.end ?? <span className="text-emerald-400">ongoing</span>}</div>
                  </td>
                  <td className="py-1 pr-2 text-slate-300">
                    {e.action}
                    <span className={`ml-1 text-[0.62rem] uppercase ${e.kind === "easing" ? "text-emerald-400" : "text-rose-400"}`}>{e.kind}</span>
                  </td>
                  <td className="py-1 pr-2 text-slate-400">{e.chair}</td>
                  <td className="py-1 pr-2">{val(e.dxy_at_start, (n) => n.toFixed(1))}</td>
                  <td className="py-1 pr-2">{val(e.us10y_at_start, (n) => `${n.toFixed(2)}%`)}</td>
                  <td className="py-1 pr-2">{val(e.fed_balance_sheet_at_start, bn)}</td>
                  <td className="py-1 pr-2">{val(e.unemployment_at_start, (n) => `${n.toFixed(1)}%`)}</td>
                  <td className="py-1 pr-2 tabular-nums text-slate-400">
                    {e.spx_peak && e.spx_trough ? `${e.spx_peak.value.toLocaleString()} → ${e.spx_trough.value.toLocaleString()}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[0.68rem] text-slate-500">
          Episode boundaries and descriptions are curated; every market column is computed at the episode&rsquo;s start date from{" "}
          {ctx.fed_episodes.computed_columns.join(", ")}.
        </p>
      </div>
    </section>
  );
}
