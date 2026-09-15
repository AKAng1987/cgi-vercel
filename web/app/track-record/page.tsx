import { apiFetch } from "@/lib/api";
import { SignalsResponse } from "@/lib/types";
import { SummaryStrip } from "../components/track-record/SummaryStrip";
import { SignalsTable } from "../components/track-record/SignalsTable";

/**
 * TRACK RECORD tab. Renders the Markov signal log exactly as the Lambdas
 * wrote it to cmon-stage-backend-regime-signals -- one row per day since
 * 2026-09-06, outcomes filling in at 1w / 1m / 3m as they land, plus the
 * experimental Phase 2 divergence read from 2026-09-14. No computation
 * happens here beyond formatting; the summary counts come from the API and
 * are defined there (hit rate is over days where the regime actually
 * changed, because the top-3 list only holds next-states).
 */
export default async function TrackRecordPage() {
  const data = await apiFetch<SignalsResponse>("/api/signals");

  return (
    <main className="mx-auto max-w-7xl p-6">
      <h1 className="mb-1 text-2xl font-bold">TRACK RECORD</h1>
      <p className="mb-4 text-xs text-slate-400">
        Dated, immutable Markov signal log. Each row is written at 00:55 UTC and never
        edited; outcomes are appended 1w / 1m / 3m later. Divergence (experimental) is the
        market-implied read vs. the print-confirmed regime.
      </p>

      <SummaryStrip summary={data.summary} />

      <SignalsTable signals={data.signals} />

      <div className="mt-6 text-[0.68rem] leading-relaxed text-slate-600">
        <p>
          <span className="text-slate-500">Hit:</span> the regime the model was in at the check date
          appeared in that day&apos;s top-3 next-regime list. Only meaningful on days the regime
          changed — a day that stayed in the same regime can never be a hit, so those are shown as
          &ldquo;same&rdquo; and excluded from the hit rate.
        </p>
        <p className="mt-1">
          <span className="text-slate-500">Entropy:</span> Shannon bits over the next-regime
          distribution. Lower = more concentrated call.{" "}
          <span className="text-slate-500">Divergence:</span> 1 − P(market agrees with the print);
          direction shows when the market is leaning the other way at 0.5. Experimental — logged
          from day one so it can be evaluated, not because it has been.
        </p>
      </div>
    </main>
  );
}
