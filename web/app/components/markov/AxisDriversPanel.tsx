import { AxisDrivers, MarkovAxis } from "@/lib/types";

const ORDER: MarkovAxis[] = ["liquidity", "credit", "growth", "inflation"];
const LABEL: Record<MarkovAxis, string> = { liquidity: "Liquidity", credit: "Credit", growth: "Growth", inflation: "Inflation" };
const T = ["low", "mid", "high"];

function pct(p: number | null | undefined): string {
  return p === null || p === undefined ? "—" : `${Math.round(p * 100)}%`;
}
function val(v: number | null | undefined, name: string): string {
  if (v === null || v === undefined) return "—";
  const isPct = name.includes("%");
  return `${v > 0 ? "+" : ""}${v.toFixed(isPct ? 1 : 2)}${isPct ? "%" : ""}`;
}

export function AxisDriversPanel({ drivers }: { drivers: { as_of: string; axes: Record<MarkovAxis, AxisDrivers> } | null }) {
  if (!drivers) return null;
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">What moves each axis</div>
        <div className="text-xs text-slate-500">
          30-day driver moves at the start of each release window · P(flip) by tercile of the driver&apos;s own history · current tercile highlighted
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {ORDER.map((axis) => {
          const a = drivers.axes[axis];
          if (!a) return null;
          const c = a.current;
          const arrow = a.current_state ? "↑" : "↓";
          const cond = c.conditioned_p_flip, base = c.base_rate;
          const dir = cond !== null && base !== null ? cond - base : null;
          return (
            <div key={axis} className="rounded border border-slate-800 bg-slate-900/60 p-3">
              <div className="flex items-baseline justify-between">
                <div className="text-sm font-bold text-slate-100">
                  {LABEL[axis]} <span className="text-slate-500">{arrow}</span>
                  <span className="ml-2 text-[0.68rem] font-normal uppercase tracking-wide text-slate-500">{a.release_type} · {a.cadence_days}d windows</span>
                </div>
                <div className="text-xs text-slate-400">
                  base <span className="text-slate-200">{pct(base)}</span>
                  <span className="mx-1 text-slate-600">→</span>
                  now <span className={`font-bold ${dir !== null && Math.abs(dir) >= 0.08 ? "text-[#FCD34D]" : "text-slate-100"}`}>{pct(cond)}</span>
                  <span className="ml-1 text-slate-600">({c.n_flips}/{c.n_windows} windows flipped)</span>
                </div>
              </div>
              <table className="mt-2 w-full border-collapse text-[0.72rem]">
                <thead>
                  <tr className="text-[0.62rem] uppercase tracking-wide text-slate-500">
                    <th className="py-0.5 text-left">driver</th>
                    <th className="py-0.5 text-right">now</th>
                    <th className="py-0.5 text-right">P(flip) low</th>
                    <th className="py-0.5 text-right">mid</th>
                    <th className="py-0.5 text-right">high</th>
                    <th className="py-0.5 text-right">at flips vs not</th>
                  </tr>
                </thead>
                <tbody>
                  {c.drivers.map((d) => {
                    if (d.insufficient) return (
                      <tr key={d.name} className="border-t border-slate-800/60 text-slate-600"><td className="py-0.5">{d.name}</td><td colSpan={5} className="py-0.5 text-right">insufficient history (n={d.n})</td></tr>
                    );
                    return (
                      <tr key={d.name} className="border-t border-slate-800/60">
                        <td className="py-0.5 text-slate-300">{d.name}</td>
                        <td className="py-0.5 text-right text-slate-200" title={`tercile: ${d.current_tercile === null || d.current_tercile === undefined ? "—" : T[d.current_tercile]}`}>{val(d.current_value, d.name)}</td>
                        {[0, 1, 2].map((k) => (
                          <td key={k} className={`py-0.5 text-right ${d.current_tercile === k ? "rounded bg-[#2a2410] font-bold text-[#FCD34D]" : "text-slate-400"}`} title={`${d.n_by_tercile?.[k] ?? 0} windows`}>
                            {pct(d.p_by_tercile?.[k])}
                          </td>
                        ))}
                        <td className="py-0.5 text-right text-slate-500">{val(d.mean_flip, d.name)} <span className="text-slate-700">/</span> {val(d.mean_noflip, d.name)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>
    </section>
  );
}
