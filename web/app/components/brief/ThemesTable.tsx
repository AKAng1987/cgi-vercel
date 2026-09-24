import { ThemeRow, RunStats } from "@/lib/types";

const STAGE_STYLE: Record<string, string> = {
  early: "bg-emerald-950/60 text-emerald-300 border-emerald-800",
  mid: "bg-sky-950/60 text-sky-300 border-sky-800",
  late: "bg-amber-950/60 text-amber-300 border-amber-800",
};

function pct(v: number | null | undefined) {
  return v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(0)}%`;
}

/**
 * Layer 2 -- discovery. Age is the point: it says whether a theme still has
 * runway or is already consensus. A theme whose leading proxy runs while the
 * lagging one does not is early (miners before the metal).
 */
export function ThemesTable({ themes, runStats }: { themes: ThemeRow[]; runStats?: RunStats }) {
  const mega = themes.filter((t) => t.stage && t.class === "megatrend");
  const running = themes.filter((t) => t.stage && t.class !== "megatrend");
  const dormant = themes.filter((t) => !t.stage);

  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">Themes in force</div>
        <div className="text-xs text-slate-500">
          relative strength vs SPY above its 200-day trend · how much runway is typically left, not how old
        </div>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="text-[0.62rem] uppercase tracking-wide text-slate-500">
            <th className="px-2 py-1 text-left font-normal">theme</th>
            <th className="px-2 py-1 text-left font-normal">stage</th>
            <th className="px-2 py-1 text-left font-normal">started</th>
            <th className="px-2 py-1 text-right font-normal">age</th>
            <th className="px-2 py-1 text-right font-normal" title="share of 727 historical runs that lasted longer than this one has">runway</th>
            <th className="px-2 py-1 text-right font-normal">RS</th>
            <th className="px-2 py-1 text-right font-normal">price</th>
            <th className="px-2 py-1 text-left font-normal">legs running</th>
          </tr>
        </thead>
        <tbody>
          {mega.length > 0 && (
            <tr>
              <td colSpan={7} className="px-2 pb-1 pt-2 text-[0.6rem] uppercase tracking-[2px] text-slate-500">
                megatrend{" "}
                <span className="normal-case tracking-normal text-slate-600">
                  — secular, not rotational; runway is context here, not a countdown
                </span>
              </td>
            </tr>
          )}
          {[...mega, ...(mega.length ? [null] : []), ...running].map((t, i) => {
            if (t === null) {
              return (
                <tr key="hdr-rot">
                  <td colSpan={7} className="px-2 pb-1 pt-3 text-[0.6rem] uppercase tracking-[2px] text-slate-500">
                    rotation
                  </td>
                </tr>
              );
            }
            const lead = t.legs.find((l) => l.symbol === t.lead_symbol);
            const partial = t.n_running < t.n_legs;
            const isMega = t.class === "megatrend";
            return (
              <tr key={t.theme} className="border-t border-slate-800/60 text-[0.76rem]">
                <td className="px-2 py-1 font-medium text-slate-100">{t.theme}</td>
                <td className="px-2 py-1">
                  <span className={`rounded border px-1.5 py-0.5 text-[0.62rem] ${STAGE_STYLE[t.stage!]}`}>
                    {t.stage}
                  </span>
                </td>
                <td className="px-2 py-1 text-slate-400">{t.onset}</td>
                <td className="px-2 py-1 text-right text-slate-300">{t.age_days}d</td>
                <td className={`px-2 py-1 text-right ${isMega ? "text-slate-600" : (t.survival_pct ?? 0) >= 0.5 ? "text-slate-200" : (t.survival_pct ?? 0) >= 0.2 ? "text-slate-400" : "text-slate-600"}`}
                    title={isMega ? "measured over rotational runs; a secular trend is not drawn from that distribution" : undefined}>
                  {t.survival_pct === null ? "—" : `${Math.round(t.survival_pct * 100)}%`}
                  {isMega && <span className="ml-0.5 text-[0.6rem] text-slate-700">n/a</span>}
                </td>
                <td className="px-2 py-1 text-right font-semibold text-slate-100">{pct(lead?.rs_gain_pct)}</td>
                <td className="px-2 py-1 text-right text-slate-300">{pct(lead?.price_gain_pct)}</td>
                <td className="px-2 py-1 text-slate-400">
                  {t.legs
                    .filter((l) => l.status === "running")
                    .map((l) => l.symbol)
                    .join(" ")}
                  {partial && (
                    <span className="ml-1 text-[0.62rem] text-slate-500" title="some proxies in this theme are running and some are not — partial participation, not necessarily a lead/lag sequence">
                      · {t.n_running}/{t.n_legs}
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {runStats && (
        <p className="mt-2 text-[0.68rem] text-slate-600">
          Runway = share of {runStats.n_runs} historical runs that lasted longer than this one has.
          Median run {runStats.median_days}d, p75 {runStats.p75_days}d, p90 {runStats.p90_days}d
          (measured {runStats.measured_on}). Stage boundaries are terciles of that distribution,
          not round numbers.
        </p>
      )}

      {dormant.length > 0 && (
        <p className="mt-2 text-[0.7rem] leading-relaxed text-slate-600">
          <span className="text-slate-500">No active run:</span>{" "}
          {dormant.map((t) => t.theme).join(" · ")} — loud narratives with nothing in the price belong here.
        </p>
      )}
    </section>
  );
}
