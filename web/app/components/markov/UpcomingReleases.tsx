import { UpcomingRelease } from "@/lib/types";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

const AXIS_LABEL: Record<string, string> = {
  liquidity: "Liquidity", credit: "Credit", growth: "Growth", inflation: "Inflation",
};

function q(model: "compass" | "grid", n: number): string {
  return model === "compass" ? `C${n}` : `G${n}`;
}
function qTitle(model: "compass" | "grid", n: number): string {
  return model === "compass" ? COMPASS_Q_LABELS[n] : GRID_Q_LABELS[n];
}
function daysUntil(asOf: string, date: string): number {
  return Math.round((Date.parse(date) - Date.parse(asOf)) / 86_400_000);
}

export function UpcomingReleases({
  current, upcoming, asOf,
}: { current: { compass: number; grid: number }; upcoming: UpcomingRelease[]; asOf: string }) {
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">Upcoming releases</div>
        <div className="text-xs text-slate-500">
          Now: <span className="font-bold text-slate-200" title={qTitle("compass", current.compass)}>C{current.compass}</span>
          {" × "}
          <span className="font-bold text-slate-200" title={qTitle("grid", current.grid)}>G{current.grid}</span>
          <span className="ml-2 text-slate-600">as of {asOf}</span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {upcoming.map((u) => {
          const d = daysUntil(asOf, u.date);
          const arrow = u.current_state ? "↑" : "↓";
          const pct = Math.round(u.p_flip * 100);
          const hot = u.p_flip >= 0.5;
          return (
            <div key={u.type} className={`rounded border p-3 ${hot ? "border-[#FCD34D]/60 bg-[#2a2410]" : "border-slate-800 bg-slate-900/60"}`}>
              <div className="flex items-baseline justify-between">
                <div className="text-sm font-bold text-slate-100">{u.type}</div>
                <div className="text-xs text-slate-400">
                  {u.date} <span className="text-slate-600">· {d <= 0 ? "today" : `in ${d}d`}</span>
                </div>
              </div>
              <div className="mt-1 text-[0.68rem] uppercase tracking-wide text-slate-500">
                moves {AXIS_LABEL[u.axis]} · now {arrow}
              </div>
              <div className="mt-2 flex items-baseline gap-2">
                <div className={`text-2xl font-bold ${hot ? "text-[#FCD34D]" : "text-slate-100"}`}>{pct}%</div>
                <div className="text-xs text-slate-400">chance it flips</div>
              </div>
              <div className="mt-1 text-xs text-slate-400">
                if it flips: <span className="text-slate-500">{q(u.model, u.current_quadrant)}</span>
                {" → "}
                <span className="font-bold text-slate-100" title={qTitle(u.model, u.if_flip_quadrant)}>
                  {q(u.model, u.if_flip_quadrant)}
                </span>
              </div>
              <div className="mt-2 text-[0.65rem] text-slate-600" title="flips ÷ expected releases while in this state">
                {u.basis.n_flips} flips / {u.basis.expected_releases} expected releases
                <span className="ml-1">({Math.round(u.basis.dwell_days / 365)}y in state)</span>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
