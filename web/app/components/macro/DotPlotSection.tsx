import { apiFetch } from "@/lib/api";
import type { DotPlotResponse } from "@/lib/macroTypes";
import { SectionHeader, ErrorCard } from "./SectionHeader";
import { DotPlotChart } from "./DotPlotChart";
import { DOT_PLOT_HORIZON_ORDER } from "@/lib/macroConstants";

export async function DotPlotSection() {
  let data: DotPlotResponse;
  try {
    data = await apiFetch<DotPlotResponse>("/api/macro/dot-plot");
  } catch (e) {
    return <ErrorCard label="SEP dot plot" message={e instanceof Error ? e.message : "Unknown error"} />;
  }

  const rows = data.dot_plot;
  if (rows.length === 0) {
    return (
      <section>
        <SectionHeader>SEP Dot Plot — Projected Appropriate Policy Rate</SectionHeader>
        <p className="text-sm text-slate-500">No dot plot data available.</p>
      </section>
    );
  }

  const firstHorizon = DOT_PLOT_HORIZON_ORDER.find((h) => rows.some((r) => r.year === h)) ?? rows[0].year;
  const nParticipants = rows.filter((r) => r.year === firstHorizon).length;

  return (
    <section>
      <SectionHeader>SEP Dot Plot — Projected Appropriate Policy Rate</SectionHeader>
      <DotPlotChart rows={rows} />
      <p className="mt-1 text-xs text-slate-600">
        {nParticipants} participants · Thick bars = median.
      </p>
    </section>
  );
}
