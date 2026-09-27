"use client";

import { useState } from "react";
import type { PricedInResponse } from "@/lib/types";

/**
 * What a multiple implies about growth, read two ways.
 *
 * The two readings disagree on purpose, and the disagreement is the output.
 * The GRID is the user's own 10x10 table of justified multiples by revenue
 * growth and domicile 10Y -- a rough anchor of unknown provenance, kept
 * because it is the number they already reason with. The REVERSE DCF solves
 * for the growth the price actually implies. Where they part company, that is
 * information about the grid.
 *
 * Every assumption is on screen and adjustable, because a reverse DCF can be
 * made to say anything by moving the equity risk premium or the fade. The
 * output is the start of an argument, not a target price.
 */
const num =
  "w-full rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs tabular-nums " +
  "text-slate-100 focus:border-slate-500 focus:outline-none";
const lbl = "mb-1 block text-[0.58rem] font-bold uppercase tracking-[1.2px] text-slate-500";

function Reading({
  head,
  value,
  unit,
  sub,
}: {
  head: string;
  value: string;
  unit?: string;
  sub?: string;
}) {
  return (
    <div className="rounded border border-slate-800 bg-slate-950/60 p-3">
      <div className="text-[0.58rem] font-bold uppercase tracking-[1.2px] text-slate-500">{head}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums text-slate-100">
        {value}
        {unit && <span className="ml-0.5 text-sm text-slate-400">{unit}</span>}
      </div>
      {sub && <div className="mt-1 text-[0.65rem] leading-snug text-slate-500">{sub}</div>}
    </div>
  );
}

export function PricedIn() {
  const [f, setF] = useState({
    growth_pct: "22",
    rate_pct: "",
    multiple: "",
    erp_pct: "4.5",
    fade_years: "10",
    terminal_growth_pct: "2.5",
  });
  const [data, setData] = useState<PricedInResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (k: keyof typeof f) => (e: { target: { value: string } }) =>
    setF((p) => ({ ...p, [k]: e.target.value }));

  async function run(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const qs = new URLSearchParams();
      for (const [k, v] of Object.entries(f)) if (v !== "") qs.set(k, v);
      const res = await fetch(`/api/priced-in?${qs.toString()}`);
      const body = await res.json();
      if (!res.ok || body?.error) throw new Error(body?.error ?? `HTTP ${res.status}`);
      setData(body as PricedInResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setData(null);
    } finally {
      setBusy(false);
    }
  }

  const dcf = data?.reverse_dcf ?? null;
  const gap = data?.priced_in_gap ?? null;

  return (
    <div>
      <form onSubmit={run} className="grid grid-cols-2 gap-3 sm:grid-cols-6">
        <div>
          <label className={lbl} htmlFor="pi-g">Growth %</label>
          <input id="pi-g" className={num} value={f.growth_pct} onChange={set("growth_pct")}
                 inputMode="decimal" required />
        </div>
        <div>
          <label className={lbl} htmlFor="pi-m">Multiple</label>
          <input id="pi-m" className={num} value={f.multiple} onChange={set("multiple")}
                 inputMode="decimal" placeholder="28.1" />
        </div>
        <div>
          <label className={lbl} htmlFor="pi-r">10Y %</label>
          <input id="pi-r" className={num} value={f.rate_pct} onChange={set("rate_pct")}
                 inputMode="decimal" placeholder="live" />
        </div>
        <div>
          <label className={lbl} htmlFor="pi-e">ERP %</label>
          <input id="pi-e" className={num} value={f.erp_pct} onChange={set("erp_pct")}
                 inputMode="decimal" />
        </div>
        <div>
          <label className={lbl} htmlFor="pi-f">Fade yrs</label>
          <input id="pi-f" className={num} value={f.fade_years} onChange={set("fade_years")}
                 inputMode="numeric" />
        </div>
        <div>
          <label className={lbl} htmlFor="pi-t">Terminal %</label>
          <input id="pi-t" className={num} value={f.terminal_growth_pct}
                 onChange={set("terminal_growth_pct")} inputMode="decimal" />
        </div>
        <div className="col-span-2 sm:col-span-6">
          <button type="submit" disabled={busy}
                  className="rounded bg-slate-200 px-3 py-1 text-[0.7rem] font-semibold text-slate-900 disabled:opacity-50">
            {busy ? "Solving…" : "Read it both ways"}
          </button>
          <span className="ml-3 text-[0.62rem] text-slate-600">
            Leave <strong>Multiple</strong> blank and only the grid can answer &mdash; individual
            equities are not in the price history, so the actual multiple has to be typed in.
          </span>
        </div>
      </form>

      {error && <p className="mt-3 text-[0.7rem] text-rose-400">{error}</p>}

      {data && (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Reading
              head="Grid says"
              value={data.grid.justified_multiple.toFixed(1)}
              unit="×"
              sub={
                data.grid.extrapolated
                  ? (data.grid.extrapolation_note ?? "outside the table — extrapolated")
                  : "justified multiple at this growth and rate"
              }
            />
            <Reading
              head="Actual"
              value={data.actual_multiple !== null ? data.actual_multiple.toFixed(1) : "—"}
              unit={data.actual_multiple !== null ? "×" : undefined}
              sub={data.actual_multiple === null ? data.actual_multiple_note : "what the market pays"}
            />
            <Reading
              head="DCF implies"
              value={dcf?.implied_growth_pct !== undefined ? dcf.implied_growth_pct.toFixed(1) : "—"}
              unit={dcf?.implied_growth_pct !== undefined ? "%" : undefined}
              sub={dcf?.error ?? "the growth that multiple requires"}
            />
          </div>

          {gap && (
            <p className="rounded border border-slate-800 bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-300">
              <span
                className={
                  gap.implied_minus_actual_pp > 0
                    ? "font-semibold text-rose-400"
                    : "font-semibold text-emerald-400"
                }
              >
                {gap.implied_minus_actual_pp > 0 ? "+" : ""}
                {gap.implied_minus_actual_pp.toFixed(1)}pp
              </span>{" "}
              &mdash; {gap.reads_as}. Reported growth {f.growth_pct}%, the price implies{" "}
              {dcf?.implied_growth_pct?.toFixed(1)}%.
            </p>
          )}

          {data.grid_vs_dcf && (
            <p className="text-[0.66rem] leading-relaxed text-slate-500">
              Grid {data.grid_vs_dcf.grid_multiple.toFixed(1)}× against an actual{" "}
              {data.grid_vs_dcf.actual_multiple.toFixed(1)}×. {data.grid_vs_dcf.note}
            </p>
          )}

          {dcf?.assumptions && (
            <p className="text-[0.62rem] leading-relaxed text-slate-600">
              Discount rate {dcf.assumptions.discount_rate_pct.toFixed(2)}% ={" "}
              {dcf.assumptions.risk_free_pct.toFixed(2)}% risk-free +{" "}
              {dcf.assumptions.equity_risk_premium_pct.toFixed(2)}% ERP. Growth fades linearly over{" "}
              {dcf.assumptions.fade_years} years to a {dcf.assumptions.terminal_growth_pct.toFixed(2)}%
              terminal rate. Move any of those and the implied growth moves with them &mdash; which
              is the point of having them on screen rather than buried.
            </p>
          )}

          <p className="text-[0.62rem] leading-relaxed text-slate-600">{data.grid.provenance}</p>
        </div>
      )}
    </div>
  );
}
