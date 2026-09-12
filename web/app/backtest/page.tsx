import { apiFetch } from "@/lib/api";
import { BacktestTableResponse } from "@/lib/types";
import { BacktestClient } from "../components/backtest/BacktestClient";
import { BacktestTable } from "../components/backtest/BacktestTable";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

/**
 * BACKTEST tab, ported from app.py:1096-1310. Controls (compass_q,
 * grid_q, min_occ, lookback) live in URL search params so the page is
 * server-rendered per view and links are shareable. The table itself is
 * fetched server-side from /api/backtest/{cq}/{gq} which reads the
 * single blob written daily by cmon-stage-backend-backtest-refresher
 * (03:30 UTC ap-southeast-1).
 */
type Lookback = "all" | "10y" | "5y";

function parseQuadrant(v: string | string[] | undefined, fallback: number): number {
  const raw = Array.isArray(v) ? v[0] : v;
  const n = Number(raw);
  return n >= 1 && n <= 4 ? n : fallback;
}

function parseMinOcc(v: string | string[] | undefined): number {
  const raw = Array.isArray(v) ? v[0] : v;
  const n = Number(raw);
  if (!Number.isFinite(n)) return 5;
  return Math.min(20, Math.max(1, Math.round(n)));
}

function parseLookback(v: string | string[] | undefined): Lookback {
  const raw = Array.isArray(v) ? v[0] : v;
  if (raw === "10y" || raw === "5y") return raw;
  return "all";
}

export default async function BacktestPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const compassQ = parseQuadrant(sp.cq, 2);
  const gridQ = parseQuadrant(sp.gq, 4);
  const minOcc = parseMinOcc(sp.min_occ);
  const lookback = parseLookback(sp.lookback);

  const qs = new URLSearchParams({
    min_occ: String(minOcc),
    lookback,
  });
  const data = await apiFetch<BacktestTableResponse>(
    `/api/backtest/${compassQ}/${gridQ}?${qs}`
  );

  // Refresh Lambda runs 03:30 UTC daily; >30h since last write means it
  // missed at least one cycle -- worth surfacing rather than silently
  // serving day-old numbers. Clock skew a few hours either side is fine.
  let stalenessHours: number | null = null;
  if (data.last_refreshed_at) {
    const refreshed = new Date(data.last_refreshed_at).getTime();
    if (!Number.isNaN(refreshed)) {
      stalenessHours = (Date.now() - refreshed) / 3_600_000;
    }
  }

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="mb-1 text-2xl font-bold">BACKTEST</h1>
      <p className="mb-4 text-xs text-slate-400">
        Historical performance of every ETF during a specific Compass × Grid
        regime. Entry = close on signal date. Edge = Avg High% ÷ |Avg Low%|.
      </p>

      {stalenessHours !== null && stalenessHours > 30 && (
        <div className="mb-4 rounded border border-yellow-800 bg-yellow-950/40 px-3 py-2 text-xs text-yellow-300">
          ⚠ Backtest data is {Math.round(stalenessHours)}h old (last refreshed{" "}
          {new Date(data.last_refreshed_at!).toISOString().replace("T", " ").slice(0, 16)} UTC).
          Daily refresh runs at 03:30 UTC; if this keeps growing, check the
          cmon-stage-backend-backtest-refresher Lambda.
        </div>
      )}

      <BacktestClient
        compassQ={compassQ}
        gridQ={gridQ}
        minOcc={minOcc}
        lookback={lookback}
      />

      <div className="mb-3 rounded border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-300">
        Regime{" "}
        <span className="font-medium text-slate-100">
          {COMPASS_Q_LABELS[compassQ]} × {GRID_Q_LABELS[gridQ]}
        </span>{" "}
        (C{compassQ}×G{gridQ}) has {data.rows.length}{" "}
        {data.rows.length === 1 ? "ticker" : "tickers"} meeting the min-occurrences
        threshold ({minOcc}).
        {data.last_refreshed_at && (
          <span className="ml-2 text-slate-500">
            Data as of {new Date(data.last_refreshed_at).toISOString().slice(0, 10)}
          </span>
        )}
      </div>

      {data.error ? (
        <div className="rounded border border-yellow-800 bg-yellow-950/40 p-3 text-sm text-yellow-300">
          {data.error}
        </div>
      ) : data.rows.length === 0 ? (
        <div className="rounded border border-slate-800 bg-slate-900/40 p-3 text-sm text-slate-400">
          No tickers met the minimum occurrences threshold for this regime combo.
        </div>
      ) : (
        <BacktestTable
          rows={data.rows}
          compassQ={compassQ}
          gridQ={gridQ}
        />
      )}
    </main>
  );
}
