import type { RegimeDurationLevel, RegimeDurationsResponse } from "@/lib/types";

/**
 * How long regimes have lasted. Completed runs only -- the run in force is a
 * censored observation, so its age is shown beside the history, never inside
 * it. "Lasted longer" is the share of past runs of the same kind that outran
 * the current age: a base rate, not a forecast.
 *
 * n travels with every row. The compass quadrants C3 and C4 and most C3/C4
 * combined regimes have under ten completed runs, and a median over four
 * runs is an anecdote, so those rows say so instead of looking like the rest.
 */
const LEVELS: { key: "combined" | "compass" | "grid"; label: string; rowLabel: string }[] = [
  { key: "combined", label: "Combined regime (Compass × Grid)", rowLabel: "Regime" },
  { key: "compass", label: "Compass (liquidity × credit)", rowLabel: "Quadrant" },
  { key: "grid", label: "Grid (growth × inflation)", rowLabel: "Quadrant" },
];

function flagOf(s: { thin: boolean; anecdotal: boolean }) {
  return s.anecdotal ? "anecdotal" : s.thin ? "thin" : "";
}

function InForce({ level, label }: { level: RegimeDurationLevel; label: string }) {
  const c = level.current;
  if (!c) return null;
  return (
    <tr className="border-t border-slate-800">
      <td className="px-2 py-1 text-slate-400">{label}</td>
      <td className="px-2 py-1 font-semibold text-slate-200">{c.regime}</td>
      <td className="px-2 py-1 text-slate-400">since {c.since}</td>
      <td className="px-2 py-1 text-right tabular-nums">{c.age_days}d</td>
      <td className="px-2 py-1 text-right tabular-nums text-slate-400">
        {c.same_regime_median_days ?? "—"}d
      </td>
      <td className="px-2 py-1 text-right tabular-nums">
        {c.survival_pct_same_regime === null ? "—" : `${c.survival_pct_same_regime}%`}
        <span className="ml-1 text-[0.6rem] text-slate-600">of {c.completed_runs_of_this_regime}</span>
        {c.completed_runs_of_this_regime <= 4 && (
          <span className="ml-1 text-[0.6rem] text-amber-400">anecdotal</span>
        )}
      </td>
    </tr>
  );
}

export function RegimeDurations({ d }: { d: RegimeDurationsResponse }) {
  return (
    <div>
      <div className="mb-2 text-[0.72rem] uppercase tracking-wide text-slate-400">How long regimes last</div>

      <table className="w-full max-w-3xl text-left text-xs">
        <thead>
          <tr className="bg-slate-800 uppercase text-[0.62rem] text-slate-400">
            <th className="px-2 py-1">In force</th>
            <th className="px-2 py-1">Now</th>
            <th className="px-2 py-1">Since</th>
            <th className="px-2 py-1 text-right">Age</th>
            <th className="px-2 py-1 text-right">Past median</th>
            <th className="px-2 py-1 text-right">Outlasted age</th>
          </tr>
        </thead>
        <tbody>
          {LEVELS.map((l) => (
            <InForce key={l.key} level={d[l.key]} label={l.key} />
          ))}
        </tbody>
      </table>

      <div className="mt-4 grid gap-6 lg:grid-cols-3">
        {LEVELS.map((l) => {
          const lv = d[l.key];
          const o = lv.overall;
          return (
            <div key={l.key}>
              <div className="mb-1 text-[0.7rem] text-slate-300">
                {l.label}
                <span className="ml-2 text-slate-500">
                  n={o.n} · mean {o.mean_days}d · median {o.median_days}d
                </span>
              </div>
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="bg-slate-800 uppercase text-[0.62rem] text-slate-400">
                    <th className="px-2 py-1">{l.rowLabel}</th>
                    <th className="px-2 py-1 text-right">n</th>
                    <th className="px-2 py-1 text-right">Mean</th>
                    <th className="px-2 py-1 text-right">Median</th>
                    <th className="px-2 py-1 text-right">Range</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(lv.by_regime).map(([k, s]) => {
                    const flag = flagOf(s);
                    return (
                      <tr key={k} className="border-t border-slate-800">
                        <td className="px-2 py-1">
                          {k}
                          {flag && <span className="ml-1 text-[0.6rem] text-amber-400">{flag}</span>}
                        </td>
                        <td className="px-2 py-1 text-right tabular-nums text-slate-400">{s.n}</td>
                        <td className="px-2 py-1 text-right tabular-nums">{s.mean_days}</td>
                        <td className="px-2 py-1 text-right tabular-nums">{s.median_days}</td>
                        <td className="px-2 py-1 text-right tabular-nums text-slate-500">
                          {s.min_days}–{s.max_days}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        })}
      </div>

      <p className="mt-2 max-w-3xl text-[0.66rem] leading-relaxed text-slate-600">
        {d.caveat} Days. Outlasted age = share of past completed runs of the same regime that lasted
        longer than the current run has so far.
      </p>
    </div>
  );
}
