import { apiFetch } from "@/lib/api";
import { BacktestTableResponse, SignalsResponse } from "@/lib/types";
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
type Trend = "all" | "extended" | "neutral" | "oversold";

function parseQuadrant(v: string | string[] | undefined): number | null {
  const raw = Array.isArray(v) ? v[0] : v;
  const n = Number(raw);
  return n >= 1 && n <= 4 ? n : null;
}

// Default the selectors to today's regime (from the latest Markov signal
// row, which Phase 1 derives from model-history at 00:55 UTC) so the tab
// opens on the combo that matters right now. Hardcoded fallback only if
// that lookup fails -- never block the page on it.
async function currentRegime(): Promise<{ cq: number; gq: number }> {
  try {
    const r = await apiFetch<SignalsResponse>("/api/signals?limit=1");
    const s = r.signals[0];
    const cq = s?.compass.current, gq = s?.grid.current;
    if (cq && gq) return { cq, gq };
  } catch {
    /* fall through */
  }
  return { cq: 2, gq: 4 };
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

function parseTrend(v: string | string[] | undefined): Trend {
  const raw = Array.isArray(v) ? v[0] : v;
  if (raw === "extended" || raw === "neutral" || raw === "oversold") return raw;
  return "all";
}

export default async function BacktestPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  let compassQ = parseQuadrant(sp.cq);
  let gridQ = parseQuadrant(sp.gq);
  if (compassQ === null || gridQ === null) {
    const cur = await currentRegime();
    compassQ ??= cur.cq;
    gridQ ??= cur.gq;
  }
  const minOcc = parseMinOcc(sp.min_occ);
  const lookback = parseLookback(sp.lookback);
  const trend = parseTrend(sp.trend);

  const qs = new URLSearchParams({
    min_occ: String(minOcc),
    lookback,
    trend,
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
        trend={trend}
      />

      <div className="mb-3 rounded border border-slate-800 bg-slate-900/60 px-3 py-2 text-xs text-slate-300">
        Regime{" "}
        <span className="font-medium text-slate-100">
          {COMPASS_Q_LABELS[compassQ]} × {GRID_Q_LABELS[gridQ]}
        </span>{" "}
        (C{compassQ}×G{gridQ}) has {data.rows.length}{" "}
        {data.rows.length === 1 ? "ticker" : "tickers"} meeting the min-occurrences
        threshold ({minOcc}).
        {trend !== "all" && (
          <span className="ml-1 text-[#FCD34D]">
            Entries only where the ticker was <b>{trend}</b> going in (20-day return vs. its own history).
          </span>
        )}
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
