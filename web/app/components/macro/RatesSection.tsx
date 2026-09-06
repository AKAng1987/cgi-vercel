import { apiFetch } from "@/lib/api";
import type { RatesResponse } from "@/lib/macroTypes";
import { SectionHeader, ErrorCard } from "./SectionHeader";
import { LineChart } from "./LineChart";
import { MetricStat } from "./MetricStat";
import { FomcProbabilityPanel } from "./FomcProbabilityPanel";
import { YieldCurvePanel } from "./YieldCurvePanel";
import { COLORS } from "@/lib/macroConstants";

/**
 * Independent data-fetch + render for /api/macro/rates. Errors are caught
 * here, not thrown -- per PHASE2_PLAN.md's explicit relaxation of the
 * "one page-level skeleton" rule (overnight-report-20260905.md risk #5):
 * each of the 3 macro endpoints renders/errors independently rather than
 * one slow/failing source blocking the whole MACRO page.
 */
export async function RatesSection() {
  let data: RatesResponse;
  try {
    data = await apiFetch<RatesResponse>("/api/macro/rates");
  } catch (e) {
    return <ErrorCard label="Rates panels" message={e instanceof Error ? e.message : "Unknown error"} />;
  }

  const ffr = [...data.fed_funds_range].sort((a, b) => a.date.localeCompare(b.date));
  const latestFfr = ffr[ffr.length - 1];

  return (
    <div className="flex flex-col gap-6">
      <section>
        <SectionHeader>Fed Funds Target Range</SectionHeader>
        {latestFfr && (
          <MetricStat
            label="Current Target Range"
            value={`${latestFfr.lower.toFixed(2)}% – ${latestFfr.upper.toFixed(2)}%`}
            help={`as of ${latestFfr.date}`}
          />
        )}
        <LineChart
          height={260}
          yTitle="Rate (%)"
          series={[
            { name: "Upper Target", x: ffr.map((p) => p.date), y: ffr.map((p) => p.upper), color: COLORS.upper, shape: "hv" },
            {
              name: "Lower Target",
              x: ffr.map((p) => p.date),
              y: ffr.map((p) => p.lower),
              color: COLORS.lower,
              shape: "hv",
              fill: "tonexty",
              fillColor: "rgba(96,165,250,0.10)",
            },
          ]}
        />
      </section>

      <section>
        <SectionHeader>FOMC Rate Probabilities (CME FedWatch)</SectionHeader>
        <FomcProbabilityPanel probs={data.fomc_probabilities} />
      </section>

      <section>
        <SectionHeader>Treasury Yield Curve (FRED DGS)</SectionHeader>
        <YieldCurvePanel data={data.treasury_curve} />
      </section>

      <section>
        <SectionHeader>Spreads — 10Y–2Y &amp; HY OAS</SectionHeader>
        <LineChart
          height={320}
          yTitle="10Y–2Y (%)"
          y2Title="HY OAS (bp)"
          hLineY={0}
          series={[
            {
              name: "10Y–2Y (%)",
              x: data.spreads.map((p) => p.date),
              y: data.spreads.map((p) => p.T10Y2Y),
              color: COLORS.t10y2y,
            },
            {
              name: "HY OAS (bp)",
              x: data.spreads.map((p) => p.date),
              y: data.spreads.map((p) => p.HY_Spread),
              color: COLORS.hySpread,
              yaxis: "y2",
            },
          ]}
        />
      </section>
    </div>
  );
}
