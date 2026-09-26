import { apiFetch } from "@/lib/api";
import { ContextResponse, MarkovResponse } from "@/lib/types";
import { UpcomingReleases } from "../components/markov/UpcomingReleases";
import { EventLog } from "../components/markov/EventLog";
import { DailyRuns } from "../components/markov/DailyRuns";
import { AxisDriversPanel } from "../components/markov/AxisDriversPanel";
import { Timeline } from "../components/markov/Timeline";
import { ContextTables } from "../components/context/ContextTables";

/**
 * CGI tab -- event-driven regime state (Phase 1.5). Renamed from MARKOV
 * 2026-09-26: the tab is not a Markov model, it is CGI's own compass/grid
 * state and the probabilities attached to it. The /api/markov endpoint and
 * the components/markov/ directory keep their names -- only what the user
 * sees changed.
 *
 * The discrete regime only moves on data releases, and each release moves
 * exactly one axis. So the forecast is one probability per upcoming
 * release ("does its axis flip?"), and the track record is one row per
 * release as it lands, scored by Brier. The daily Phase 1 rows remain the
 * pre-registered audit trail and are shown collapsed into runs below.
 */
export default async function CgiPage() {
  const [data, ctx] = await Promise.all([
    apiFetch<MarkovResponse>("/api/markov"),
    // Additive: a failure here must not take the page down. But it must not be
    // INVISIBLE either -- a NameError in context_tables once made this whole
    // section vanish while the page returned a healthy 200, and the silence is
    // what made it hard to spot. The error is captured and rendered below.
    apiFetch<ContextResponse>("/api/context").catch((e: unknown) => ({
      __error: e instanceof Error ? e.message : String(e),
    }) as unknown as ContextResponse & { __error: string }),
  ]);

  return (
    <main className="mx-auto max-w-7xl p-6">
      <h1 className="mb-1 text-2xl font-bold">CGI — regime state, and what could flip it</h1>
      <p className="mb-4 text-xs text-slate-400">
        The regime only moves on data releases — FOMC → Liquidity, SLOOS → Credit, CPI → Inflation,
        GDP → Growth. For each upcoming release: <span className="text-slate-300">History</span> is how
        often that axis flipped from its current state; <span className="text-slate-300">Market</span> is
        what&apos;s priced (fed funds futures for the Fed; the driver panel below for the rest). Both are
        stored the morning before and scored after.
      </p>

      <Timeline events={data.timeline} asOf={data.as_of} />

      <UpcomingReleases current={data.current} upcoming={data.upcoming} asOf={data.as_of} />

      <AxisDriversPanel drivers={data.drivers} />

      <EventLog events={data.event_log} pending={data.pending} summary={data.summary} />

      <DailyRuns runs={data.runs} latest={data.latest_daily} nDaily={data.n_daily_rows} />

      <div className="mt-6 text-[0.68rem] leading-relaxed text-slate-600">
        <p>
          <span className="text-slate-500">P(flip):</span> flips ÷ expected releases while in that
          state, where expected = dwell-days ÷ 365 × releases-per-year (FOMC 8, SLOOS 4, CPI 12,
          GDP 12 — advance, second and third estimates all count). Clamped to [0.02, 0.98].
          {" "}<span className="text-slate-500">Brier:</span> (p − outcome)², 0 is perfect, 0.25 is
          coin-flip. <span className="text-slate-500">Hit</span> is the coarse companion at the 0.5 line.
        </p>
        <p className="mt-1">
          Daily rows are written 00:55 UTC — <em>before</em> that day&apos;s releases — so a release-day
          row still shows the prior regime; the flip appears on the next day&apos;s row. Unscheduled
          transitions (an emergency FOMC move) show in the event log without a prior probability.
          Calendar dates are hardcoded from the official BLS / BEA / Fed schedules.
        </p>
      </div>

      {ctx && "__error" in ctx ? (
        <div className="mt-8 rounded border border-amber-800 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          Context tables unavailable: {(ctx as { __error: string }).__error}
        </div>
      ) : (
        ctx && <ContextTables ctx={ctx} />
      )}
    </main>
  );
}
