import { Suspense } from "react";
import { RatesSection } from "../components/macro/RatesSection";
import { GrowthSection } from "../components/macro/GrowthSection";
import { DotPlotSection } from "../components/macro/DotPlotSection";
import { SectionSkeleton } from "../components/macro/SectionSkeleton";

/**
 * MACRO tab, ported from app.py's MACRO tab block (app.py:2086-2765).
 * Own route (/macro) rather than a tab-switcher within one page --
 * cleanest fit for Next.js App Router, and each of the 3 backend
 * endpoints (rates/growth/dot-plot) has genuinely different load times
 * (yfinance + BEA + BLS calls on a cache miss vs. a static CSV read), so
 * this deliberately relaxes Phase 1's "one page-level skeleton" rule:
 * each section streams in and errors independently via its own
 * <Suspense> boundary, per PHASE2_PLAN.md's explicit approval of that
 * exception (overnight-report-20260905.md risk #5).
 */
export default function MacroPage() {
  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="mb-4 text-2xl font-bold">MACRO</h1>

      <Suspense fallback={<SectionSkeleton lines={2} />}>
        <RatesSection />
      </Suspense>

      <hr className="my-6 border-slate-800" />

      <Suspense fallback={<SectionSkeleton lines={3} />}>
        <GrowthSection />
      </Suspense>

      <hr className="my-6 border-slate-800" />

      <Suspense fallback={<SectionSkeleton lines={1} />}>
        <DotPlotSection />
      </Suspense>

      <div className="mt-6 text-xs text-slate-600">
        For full market-implied probabilities across all meetings:{" "}
        <a
          href="https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
          target="_blank"
          rel="noreferrer"
          className="text-blue-400 hover:underline"
        >
          Open CME FedWatch ↗
        </a>
      </div>
    </main>
  );
}
