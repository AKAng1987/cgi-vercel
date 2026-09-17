import { apiFetch } from "@/lib/api";
import { MarkovResponse } from "@/lib/types";
import { UpcomingReleases } from "../components/markov/UpcomingReleases";
import { EventLog } from "../components/markov/EventLog";
import { DailyRuns } from "../components/markov/DailyRuns";
import { AxisDriversPanel } from "../components/markov/AxisDriversPanel";
import { Timeline } from "../components/markov/Timeline";

/**
 * MARKOV tab -- event-driven (Phase 1.5).
 *
 * The discrete regime only moves on data releases, and each release moves
 * exactly one axis. So the forecast is one probability per upcoming
 * release ("does its axis flip?"), and the track record is one row per
 * release as it lands, scored by Brier. The daily Phase 1 rows remain the
 * pre-registered audit trail and are shown collapsed into runs below.
 */
export default async function MarkovPage() {
  const data = await apiFetch<MarkovResponse>("/api/markov");

  return (
    <main className="mx-auto max-w-7xl p-6">
      <h1 className="mb-1 text-2xl font-bold">MARKOV — event-driven regime forecast</h1>
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
    </main>
  );
}
