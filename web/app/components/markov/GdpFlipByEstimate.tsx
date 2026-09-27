import type { MarkovResponse } from "@/lib/types";

/**
 * Whether BEA's three GDP estimates are equally likely to move the growth
 * axis. The pooled P(flip) assumes they are -- it counts all twelve releases
 * a year identically, so a third estimate, which carries the least new
 * information of the three, is treated exactly like an advance.
 *
 * That was an assumption sitting inside a probability. This is the
 * measurement, shown beside it. Where a bucket is too thin to support its own
 * rate the pooled figure is the honest answer, and the row says so rather
 * than quoting a rate over three observations.
 */
export function GdpFlipByEstimate({ d }: { d: MarkovResponse["gdp_flip_by_estimate"] }) {
  if (!d) return null;
  const order = ["advance", "second", "third"];
  const rows = order.filter((k) => d.by_estimate[k]);
  if (rows.length === 0) return null;

  return (
    <section className="mt-6">
      <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
        GDP flip rate by estimate
      </div>
      <table className="w-full max-w-lg text-left text-xs">
        <thead>
          <tr className="bg-slate-800 uppercase text-[0.62rem] text-slate-400">
            <th className="px-2 py-1">Estimate</th>
            <th className="px-2 py-1 text-right">Releases</th>
            <th className="px-2 py-1 text-right">Flips</th>
            <th className="px-2 py-1 text-right">Own rate</th>
            <th className="px-2 py-1 text-right">Used</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((k) => {
            const b = d.by_estimate[k];
            return (
              <tr key={k} className="border-t border-slate-800">
                <td className="px-2 py-1 capitalize">{k}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-400">{b.n_releases}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-400">{b.n_flips}</td>
                <td className="px-2 py-1 text-right tabular-nums">
                  {b.flip_rate === null ? (
                    <span className="text-slate-600">—</span>
                  ) : (
                    <span className={b.thin ? "text-slate-600 line-through" : "text-slate-200"}>
                      {(b.flip_rate * 100).toFixed(0)}%
                    </span>
                  )}
                </td>
                <td className="px-2 py-1 text-right tabular-nums">
                  {b.effective_rate === null ? (
                    <span className="text-slate-600">—</span>
                  ) : (
                    <>
                      <span className="text-slate-200">{(b.effective_rate * 100).toFixed(0)}%</span>
                      {b.use === "pooled" && (
                        <span className="ml-1 text-[0.6rem] text-amber-400">pooled</span>
                      )}
                    </>
                  )}
                </td>
              </tr>
            );
          })}
          <tr className="border-t border-slate-700 text-slate-400">
            <td className="px-2 py-1">All GDP</td>
            <td className="px-2 py-1 text-right tabular-nums">{d.pooled.n_releases}</td>
            <td className="px-2 py-1 text-right tabular-nums">{d.pooled.n_flips}</td>
            <td className="px-2 py-1 text-right tabular-nums">
              {d.pooled.flip_rate === null ? "—" : `${(d.pooled.flip_rate * 100).toFixed(0)}%`}
            </td>
            <td className="px-2 py-1" />
          </tr>
        </tbody>
      </table>
      <p className="mt-1 max-w-lg text-[0.66rem] leading-relaxed text-slate-600">
        {d.note} A struck-through own rate is one computed over fewer than{" "}
        {d.min_n_for_own_rate} releases; those rows fall back to the pooled figure. n travels with
        every rate here because with roughly four of each a year, n is the whole story.
      </p>
    </section>
  );
}
