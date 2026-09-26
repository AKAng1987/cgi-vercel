import { apiFetch } from "@/lib/api";
import { COMPASS_Q_MAP, GRID_Q_MAP } from "@/lib/regimeConstants";
import { RegimeCell, RegimeCountry, RegimeFxCell, RegimeMatrixResponse } from "@/lib/types";

/**
 * COUNTRIES — what a regime means for each country and currency.
 *
 * This page shows the regime leg only. The policy rate, the curve and the
 * currency trend per country are a later step; the matrix ships first because
 * it needed no new data at all — the backtest already holds 24 country ETFs
 * and 17 USD pairs.
 *
 * Regime switching is done with a query string rather than client state, so
 * the whole page stays a server component and each cell is a shareable URL.
 */

export const dynamic = "force-dynamic";

const QS = [1, 2, 3, 4] as const;

function n(v: number | null | undefined, digits = 1, unit = "%") {
  if (v === null || v === undefined) return <span className="text-slate-600">—</span>;
  const c = v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-slate-400";
  return (
    <span className={`tabular-nums ${c}`}>
      {v > 0 ? "+" : ""}
      {v.toFixed(digits)}
      {unit}
    </span>
  );
}

/** Hit rate against the 50% coin-flip baseline, which is the only meaningful
 *  reference for it. */
function hit(v: number | undefined) {
  if (v === undefined) return <span className="text-slate-600">—</span>;
  const c = v >= 62.5 ? "text-emerald-400" : v <= 37.5 ? "text-rose-400" : "text-slate-400";
  return <span className={`tabular-nums ${c}`}>{v.toFixed(1)}%</span>;
}

/** n is never optional here. A thin sample is shown AS thin rather than
 *  quietly ranked alongside a full one. */
function N({ cell }: { cell: RegimeCell }) {
  return (
    <span
      className={`tabular-nums text-[0.7rem] ${cell.thin ? "text-amber-300" : "text-slate-500"}`}
      title={cell.thin ? "thin sample — too few occurrences to rank" : "occurrences of this regime"}
    >
      n={cell.occurrences}
      {cell.thin ? " thin" : ""}
    </span>
  );
}

function Equity({ cell }: { cell: RegimeCell | null }) {
  if (!cell) return <span className="text-slate-600">—</span>;
  if (!cell.occurrences)
    return (
      <span className="text-slate-600" title={cell.reason}>
        {cell.symbol} — no occurrences
      </span>
    );
  return (
    <span className="flex flex-wrap items-baseline gap-x-2">
      <span className="font-medium text-slate-200">{cell.symbol}</span>
      {hit(cell.hit_rate)}
      {n(cell.avg_return_pct)}
      <N cell={cell} />
    </span>
  );
}

/** The FX leg states the direction in words, taken from the server. Deriving
 *  it here from the sign would be one more place for the inversion to happen. */
function Fx({ cell, note }: { cell: RegimeFxCell | null; note: string | null }) {
  if (!cell)
    return (
      <span className="text-slate-600" title={note ?? undefined}>
        {note ? "no pair" : "—"}
      </span>
    );
  const strong = cell.local === "stronger";
  return (
    <span className="flex flex-wrap items-baseline gap-x-2">
      <span className="font-medium text-slate-200">{cell.symbol}</span>
      <span className={strong ? "text-emerald-400" : "text-rose-400"} title={cell.note}>
        {strong ? "local ↑" : cell.local === "weaker" ? "local ↓" : "flat"}
      </span>
      {n(cell.avg_return_pct, 2)}
      <N cell={cell} />
    </span>
  );
}

/** Exporter vs importer decides whether a strong local currency helps or
 *  hurts — so the two legs above can only be combined once this is known.
 *  It is hand-set, and labelled that way. */
function Trade({ c }: { c: RegimeCountry }) {
  const colour =
    c.trade === "exporter" ? "text-sky-300" : c.trade === "importer" ? "text-violet-300" : "text-slate-400";
  return (
    <span className={`text-[0.7rem] uppercase ${colour}`} title={`${c.trade_why} — ${c.trade_basis}`}>
      {c.trade}
    </span>
  );
}

function Row({ c }: { c: RegimeCountry }) {
  const rk = c.regime_ranking;
  return (
    <tr className="border-b border-slate-900 align-top hover:bg-slate-900/40">
      <td className="py-2 pr-3">
        <div className="font-medium text-slate-200">{c.code}</div>
        <div className="text-[0.7rem] text-slate-500">{c.name}</div>
      </td>
      <td className="py-2 pr-3">
        <Trade c={c} />
      </td>
      <td className="py-2 pr-3">
        <Equity cell={c.equity} />
        {c.equity_alternates.length > 0 && (
          <div className="mt-1 space-y-0.5 text-[0.72rem] opacity-70">
            {c.equity_alternates.map((a) => (
              <div key={a.symbol}>
                <Equity cell={a} />
              </div>
            ))}
          </div>
        )}
        {c.equity_absent && (
          <div className="mt-1 text-[0.68rem] text-amber-300/80" title="in the ticker list but not in the backtest blob">
            not backtested: {c.equity_absent.join(", ")}
          </div>
        )}
      </td>
      <td className="py-2 pr-3">
        <Fx cell={c.currency} note={c.currency_note} />
      </td>
      <td className="py-2 pr-3 text-[0.72rem]">
        {rk ? (
          <>
            <div>
              <span className="text-slate-500">best </span>
              <span className="text-slate-200">{rk.best.regime}</span> {n(rk.best.avg_return_pct)}{" "}
              <span className="tabular-nums text-slate-500">n={rk.best.occurrences}</span>
            </div>
            <div>
              <span className="text-slate-500">worst </span>
              <span className="text-slate-200">{rk.worst.regime}</span> {n(rk.worst.avg_return_pct)}{" "}
              <span className="tabular-nums text-slate-500">n={rk.worst.occurrences}</span>
            </div>
          </>
        ) : (
          <span className="text-slate-600">—</span>
        )}
      </td>
    </tr>
  );
}

function Table({ rows, caption }: { rows: RegimeCountry[]; caption: string }) {
  if (rows.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[46rem] border-collapse text-sm">
        <caption className="pb-2 text-left text-[0.72rem] uppercase tracking-wide text-slate-500">{caption}</caption>
        <thead>
          <tr className="border-b border-slate-800 text-left text-[0.7rem] uppercase tracking-wide text-slate-500">
            <th className="py-1.5 pr-3 font-medium">country</th>
            <th className="py-1.5 pr-3 font-medium">trade</th>
            <th className="py-1.5 pr-3 font-medium">equity — hit / avg</th>
            <th className="py-1.5 pr-3 font-medium">currency</th>
            <th className="py-1.5 pr-3 font-medium">pays best / worst in</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <Row key={c.code} c={c} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The 16 cells, as links. The current cell is marked, and each button shows
 *  the axis arrows so the regime code is readable without a lookup. */
function Picker({ compass, grid }: { compass: number; grid: number }) {
  return (
    <div className="inline-grid grid-cols-4 gap-1">
      {QS.map((g) =>
        QS.map((c) => {
          const here = c === compass && g === grid;
          const [liq, cr] = COMPASS_Q_MAP[c];
          const [gr, inf] = GRID_Q_MAP[g];
          return (
            <a
              key={`${c}-${g}`}
              href={`/countries?compass=${c}&grid=${g}`}
              title={`Compass: liquidity ${liq} credit ${cr} · Grid: growth ${gr} inflation ${inf}`}
              className={`rounded px-2 py-1 text-center text-[0.72rem] tabular-nums transition ${
                here
                  ? "bg-slate-700 font-medium text-slate-100"
                  : "bg-slate-900 text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              }`}
            >
              C{c}G{g}
            </a>
          );
        })
      )}
    </div>
  );
}

export default async function ForeignPage({
  searchParams,
}: {
  searchParams: Promise<{ compass?: string; grid?: string }>;
}) {
  const sp = await searchParams;
  const q = new URLSearchParams();
  if (sp.compass) q.set("compass_q", sp.compass);
  if (sp.grid) q.set("grid_q", sp.grid);
  const qs = q.toString();

  const m = await apiFetch<RegimeMatrixResponse>(`/api/regime-matrix${qs ? `?${qs}` : ""}`);

  if (m.error) {
    return (
      <main className="p-6">
        <h1 className="text-lg font-medium text-slate-200">COUNTRIES</h1>
        <p className="mt-2 text-sm text-rose-400">{m.error}</p>
      </main>
    );
  }

  const focus = m.countries.filter((c) => c.focus);
  const rest = m.countries.filter((c) => !c.focus);
  const [liq, cr] = COMPASS_Q_MAP[m.compass_q];
  const [gr, inf] = GRID_Q_MAP[m.grid_q];

  return (
    <main className="space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-lg font-medium text-slate-200">
          COUNTRIES <span className="text-slate-500">— regime → country / currency</span>
        </h1>
        <p className="text-[0.78rem] text-slate-500">
          Showing <span className="text-slate-300">{m.regime}</span>: liquidity {liq} credit {cr} · growth {gr}{" "}
          inflation {inf}. Backtest refreshed{" "}
          <span className="tabular-nums">{m.last_refreshed_at?.slice(0, 10) ?? "—"}</span>.
        </p>
      </header>

      <section className="flex flex-wrap items-start gap-6">
        <div className="space-y-1">
          <div className="text-[0.7rem] uppercase tracking-wide text-slate-500">pick a regime</div>
          <Picker compass={m.compass_q} grid={m.grid_q} />
        </div>
        {m.next_regimes && m.next_regimes.length > 0 && (
          <div className="space-y-1">
            <div className="text-[0.7rem] uppercase tracking-wide text-slate-500">
              where the next releases could take us
            </div>
            <ul className="space-y-0.5 text-[0.75rem]">
              {m.next_regimes.map((r, i) => (
                <li key={`${r.date}-${r.type}-${i}`}>
                  <span className="tabular-nums text-slate-500">{r.date}</span>{" "}
                  <span className="text-slate-400">{r.type}</span>{" "}
                  <a
                    className="text-[color:var(--cgi-accent)] hover:underline"
                    href={`/countries?compass=${r.compass_q}&grid=${r.grid_q}`}
                  >
                    → {r.regime_if_flip}
                  </a>{" "}
                  <span className="tabular-nums text-slate-500">p={(r.p_flip * 100).toFixed(0)}%</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <Table rows={focus} caption="in the order you asked for" />
      <Table rows={rest} caption="the rest of what the backtest already covers" />

      {m.extra_pairs.length > 0 && (
        <section className="space-y-1">
          <div className="text-[0.7rem] uppercase tracking-wide text-slate-500">other currencies</div>
          <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
            {m.extra_pairs.map((p) => (
              <li key={p.symbol}>
                <Fx cell={p} note={null} />
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="space-y-1 border-t border-slate-800 pt-3 text-[0.72rem] text-slate-500">
        <p>{m.fx_convention}</p>
        <p>{m.caveat}</p>
        <p>
          Exporter / importer is a hand-set economic judgement, not a measurement — it decides the sign of the currency
          read, so correct it where it is wrong.
        </p>
      </footer>
    </main>
  );
}
