import { apiFetch } from "@/lib/api";
import type { GrowthResponse, GdpVintageRow } from "@/lib/macroTypes";
import { SectionHeader, ErrorCard } from "./SectionHeader";
import { LineChart } from "./LineChart";
import { BarChart } from "./BarChart";
import { MetricStat } from "./MetricStat";
import { COLORS } from "@/lib/macroConstants";

function quarterEnd(dateStr: string): string {
  const d = new Date(dateStr);
  d.setMonth(d.getMonth() + 3, 0); // last day of the quarter (start + 2 months, then day 0 of next)
  return d.toISOString().slice(0, 10);
}

function yearsAgo(dateStr: string, years: number): string {
  const d = new Date(dateStr);
  d.setFullYear(d.getFullYear() - years);
  return d.toISOString().slice(0, 10);
}

function monthsAgoFromNow(months: number): string {
  const d = new Date();
  d.setMonth(d.getMonth() - months);
  return d.toISOString().slice(0, 10);
}

export async function GrowthSection() {
  let data: GrowthResponse;
  try {
    data = await apiFetch<GrowthResponse>("/api/macro/growth");
  } catch (e) {
    return <ErrorCard label="Growth panels" message={e instanceof Error ? e.message : "Unknown error"} />;
  }

  // ---- Lending Standards ----
  const lend = [...data.lending_standards].sort((a, b) => a.date.localeCompare(b.date));
  const latestLend = lend[lend.length - 1];
  const priorLend = lend.length > 1 ? lend[lend.length - 2] : null;
  const lendDelta = priorLend ? +(latestLend.value - priorLend.value).toFixed(1) : null;
  const qoqChg = lend.map((p, i) => (i === 0 ? 0 : +(p.value - lend[i - 1].value).toFixed(2)));

  // ---- GDP ----
  const gdpQ = [...data.gdp.quarterly].sort((a, b) => a.date.localeCompare(b.date));
  const latestGdp = gdpQ[gdpQ.length - 1];
  const priorGdp = gdpQ.length > 1 ? gdpQ[gdpQ.length - 2] : null;
  const gdpNowSorted = [...data.gdp_nowcast].sort((a, b) => a.date.localeCompare(b.date));

  const cutoff5y = latestGdp ? yearsAgo(latestGdp.date, 5) : "2018-01-01";
  const gdp3a = gdpQ.filter((p) => p.date >= cutoff5y);
  const gdpNow3a = gdpNowSorted.filter((p) => p.date >= cutoff5y);

  const vintages = [...data.gdp.vintages].sort((a, b) => a.quarter.localeCompare(b.quarter));
  const byVintageName = (name: GdpVintageRow["vintage"]) => vintages.filter((v) => v.vintage === name);
  const advanceRows = byVintageName("Advance");
  // GDPNow final pre-Advance: last gdpnow reading strictly before each Advance's release_date
  const finalPreAdvance = advanceRows
    .map((a) => {
      const pre = gdpNowSorted.filter((g) => g.date < a.release_date);
      if (pre.length === 0) return null;
      return { qend: quarterEnd(a.quarter), gdpnow: pre[pre.length - 1].gdpnow };
    })
    .filter((r): r is { qend: string; gdpnow: number } => r !== null);

  const gdpNow12m = gdpNowSorted.filter((p) => p.date >= monthsAgoFromNow(12));

  // ---- Inflation ----
  const inflation = [...data.inflation].sort((a, b) => a.date.localeCompare(b.date));

  // ---- Core PCE ----
  const pce = [...data.pce].sort((a, b) => a.date.localeCompare(b.date));
  const pceCutoff = pce.length > 0 ? yearsAgo(pce[pce.length - 1].date, 10) : undefined;
  const pcePlot = pceCutoff ? pce.filter((p) => p.date >= pceCutoff && p.pce_core_yoy != null) : pce;

  return (
    <div className="flex flex-col gap-6">
      <section>
        <SectionHeader>Bank Lending Standards — C&amp;I Loans (Net % Tightening)</SectionHeader>
        {latestLend && (
          <MetricStat
            label="Latest Reading"
            value={`${latestLend.value.toFixed(1)}%`}
            delta={lendDelta !== null ? `${lendDelta > 0 ? "+" : ""}${lendDelta}pp vs prior quarter` : undefined}
            help={`FRED DRTSCILM · as of ${latestLend.date}`}
          />
        )}
        <LineChart
          height={220}
          title="Level — Net % Tightening C&I Loans (Senior Loan Officer Survey)"
          yTitle="Net % Tightening"
          hLineY={0}
          series={[
            {
              name: "Net % Tightening",
              x: lend.map((p) => p.date),
              y: lend.map((p) => p.value),
              color: COLORS.lower,
              shape: "hv",
              fill: "tozeroy",
              fillColor: "rgba(96,165,250,0.08)",
              showlegend: false,
            },
          ]}
        />
        <BarChart
          height={200}
          title="QoQ Change (pp) — Red = More Tightening · Green = More Loosening"
          yTitle="pp change"
          bars={[
            {
              name: "QoQ Change (pp)",
              x: lend.map((p) => p.date),
              y: qoqChg,
              colors: qoqChg.map((v) => (v > 0 ? COLORS.gdpBarNeg : COLORS.gdpBarPos)),
            },
          ]}
        />
      </section>

      <section>
        <SectionHeader>Real GDP Growth — QoQ Annualized (%)</SectionHeader>
        {latestGdp && (
          <MetricStat
            label="Latest QoQ (ann.)"
            value={`${latestGdp.gdp_pct.toFixed(1)}%`}
            delta={priorGdp ? `${(latestGdp.gdp_pct - priorGdp.gdp_pct).toFixed(1)}pp vs prior quarter` : undefined}
            help={`BEA NIPA T10101 · ${latestGdp.date}`}
          />
        )}
        <BarChart
          height={300}
          title="3a. BEA Quarterly GDP (bars, quarter-end) vs GDPNow Real-Time Nowcast (line)"
          yTitle="% annualized"
          bars={[
            {
              name: "BEA (latest vintage)",
              x: gdp3a.map((p) => quarterEnd(p.date)),
              y: gdp3a.map((p) => p.gdp_pct),
              colors: gdp3a.map((p) => (p.gdp_pct < 0 ? COLORS.gdpBarNeg : COLORS.gdpBarPos)),
            },
          ]}
          overlays={[{ name: "GDPNow (Atlanta Fed)", x: gdpNow3a.map((p) => p.date), y: gdpNow3a.map((p) => p.gdpnow), color: COLORS.gdpNow, size: 4 }]}
        />
        {vintages.length > 0 && (
          <BarChart
            height={280}
            title="3b. Three BEA Estimates per Quarter (ALFRED) — Advance / Second / Third  ◆ GDPNow final pre-Advance"
            yTitle="% annualized"
            bars={(["Advance", "Second", "Third"] as const)
              .map((name) => byVintageName(name))
              .filter((rows) => rows.length > 0)
              .map((rows) => ({
                name: rows[0].vintage,
                x: rows.map((r) => quarterEnd(r.quarter)),
                y: rows.map((r) => r.value),
                colors:
                  rows[0].vintage === "Advance" ? COLORS.vintageAdvance : rows[0].vintage === "Second" ? COLORS.vintageSecond : COLORS.vintageThird,
              }))}
            overlays={
              finalPreAdvance.length > 0
                ? [
                    {
                      name: "GDPNow (final pre-Advance)",
                      x: finalPreAdvance.map((r) => r.qend),
                      y: finalPreAdvance.map((r) => r.gdpnow),
                      color: COLORS.gdpNowFinalDiamond,
                      mode: "markers",
                      symbol: "diamond",
                      size: 12,
                    },
                  ]
                : []
            }
          />
        )}
        {gdpNow12m.length > 0 && (
          <LineChart
            height={240}
            title={`3c. GDPNow Time Series — Current Estimate: ${gdpNow12m[gdpNow12m.length - 1].gdpnow.toFixed(1)}%`}
            yTitle="% annualized"
            hLineY={0}
            series={[
              {
                name: "GDPNow",
                x: gdpNow12m.map((p) => p.date),
                y: gdpNow12m.map((p) => p.gdpnow),
                color: COLORS.gdpNow3c,
                showlegend: false,
              },
            ]}
          />
        )}
      </section>

      <section>
        <SectionHeader>Inflation — YoY %</SectionHeader>
        <LineChart
          height={320}
          yTitle="YoY %"
          hLineY={2}
          hLineLabel="2%"
          series={[
            { name: "CPI", x: inflation.map((p) => p.date), y: inflation.map((p) => p.CPI), color: COLORS.cpi },
            { name: "Core CPI", x: inflation.map((p) => p.date), y: inflation.map((p) => p["Core CPI"]), color: COLORS.coreCpi },
            { name: "PPI", x: inflation.map((p) => p.date), y: inflation.map((p) => p.PPI), color: COLORS.ppi },
          ]}
        />
      </section>

      <section>
        <SectionHeader>Core PCE — YoY % (Fed Target)</SectionHeader>
        <LineChart
          height={270}
          yTitle="YoY %"
          hLineY={2}
          hLineLabel="2%"
          series={[
            {
              name: "Core PCE YoY",
              x: pcePlot.map((p) => p.date),
              y: pcePlot.map((p) => p.pce_core_yoy),
              color: COLORS.pce,
            },
          ]}
        />
      </section>
    </div>
  );
}
