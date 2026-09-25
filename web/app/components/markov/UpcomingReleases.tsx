import { UpcomingRelease } from "@/lib/types";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

const AXIS_LABEL: Record<string, string> = {
  liquidity: "Liquidity", credit: "Credit", growth: "Growth", inflation: "Inflation",
};
const BIG_GAP = 0.3;

function q(model: "compass" | "grid", n: number): string {
  return model === "compass" ? `C${n}` : `G${n}`;
}
function qTitle(model: "compass" | "grid", n: number): string {
  return model === "compass" ? COMPASS_Q_LABELS[n] : GRID_Q_LABELS[n];
}
function daysUntil(asOf: string, date: string): number {
  return Math.round((Date.parse(date) - Date.parse(asOf)) / 86_400_000);
}
function pct(p: number): string {
  return `${Math.round(p * 100)}%`;
}

export function UpcomingReleases({
  current, upcoming, asOf,
}: { current: { compass: number; grid: number }; upcoming: UpcomingRelease[]; asOf: string }) {
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Upcoming releases</div>
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
          const bigGap = u.gap !== null && Math.abs(u.gap) >= BIG_GAP;
          return (
            <div key={u.type} className={`rounded border p-3 ${bigGap ? "border-[#FCD34D]/70 bg-[#2a2410]" : "border-slate-800 bg-slate-900/60"}`}>
              <div className="flex items-baseline justify-between">
                <div className="text-sm font-bold text-slate-100">{u.type}</div>
                <div className="text-xs text-slate-400">
                  {u.date} <span className="text-slate-600">· {d <= 0 ? "today" : `in ${d}d`}</span>
                </div>
              </div>
              <div className="mt-1 text-[0.68rem] uppercase tracking-wide text-slate-500">
                moves {AXIS_LABEL[u.axis]} · now {arrow} · if flip {q(u.model, u.current_quadrant)} →{" "}
                <span className="font-bold text-slate-300" title={qTitle(u.model, u.if_flip_quadrant)}>{q(u.model, u.if_flip_quadrant)}</span>
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <div title={`${u.basis.n_flips} flips / ${u.basis.expected_releases} expected releases over ${Math.round(u.basis.dwell_days / 365)}y in this state`}>
                  <div className="text-[0.65rem] uppercase tracking-wide text-slate-500">History</div>
                  <div className="text-2xl font-bold text-slate-100">{pct(u.p_flip)}</div>
                  <div className="text-[0.65rem] text-slate-600">{u.basis.n_flips}/{u.basis.expected_releases} releases</div>
                </div>
                <div title={u.market ? `${u.market.source} — ${u.market.detail}` : "no market read for this axis yet"}>
                  <div className="text-[0.65rem] uppercase tracking-wide text-slate-500">
                    Market{u.market?.experimental && <span className="ml-1 text-[#FCD34D]/70">exp.</span>}
                  </div>
                  <div className={`text-2xl font-bold ${u.market ? (bigGap ? "text-[#FCD34D]" : "text-slate-100") : "text-slate-700"}`}>
                    {u.market ? pct(u.market.p_flip) : "—"}
                  </div>
                  <div className="truncate text-[0.65rem] text-slate-600">
                    {u.market ? u.market.detail : u.context?.gdpnow != null ? `GDPNow ${u.context.gdpnow.toFixed(1)}% (context)` : "no instrument tracked"}
                  </div>
                </div>
              </div>

              {u.gap !== null && (
                <div className={`mt-2 text-[0.68rem] ${bigGap ? "font-bold text-[#FCD34D]" : "text-slate-500"}`}>
                  gap {u.gap > 0 ? "+" : ""}{Math.round(u.gap * 100)} pts ·{" "}
                  {u.gap > 0 ? "market prices a flip history calls rare" : "market leans hold vs. history"}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
