import { PhRebalRow } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { peso, pct } from "./phFormat";

function Table({ title, rows, extra }: { title: string; rows: PhRebalRow[]; extra?: boolean }) {
  return (
    <div>
      <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">{title}</div>
      <table className="w-full text-xs">
        <thead>
          <tr className="text-left text-[0.58rem] uppercase text-slate-600">
            <th className="pb-1 font-normal">Stock</th><th className="pb-1 text-right font-normal">Free-float cap</th><th className="pb-1 text-right font-normal">Float</th>
            <th className="pb-1 text-right font-normal">3M</th>{extra && <th className="pb-1 text-right font-normal" title="free-float cap relative to the smallest PSEi member">vs smallest</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.s} className="border-t border-slate-800/70">
              <td className="py-1 pr-2 font-semibold text-slate-100">{r.s}<span className="ml-1 text-[0.58rem] text-slate-500">{r.ind ?? ""}</span></td>
              <td className="py-1 pr-2 text-right tabular-nums text-slate-300">{peso(r.ffmc)}</td>
              <td className="py-1 pr-2 text-right tabular-nums text-slate-500">{r.fl != null ? `${r.fl.toFixed(0)}%` : "—"}</td>
              <td className="py-1 pr-2 text-right tabular-nums" style={{ color: pctColor(r.ret_3m) }}>{pct(r.ret_3m, 0)}</td>
              {extra && <td className="py-1 text-right tabular-nums text-slate-400">{r.vs_smallest_member != null ? `${r.vs_smallest_member.toFixed(2)}×` : "—"}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Where PSEi membership could change: the weakest members against the largest non-members, by free-float market cap. */
export function PhRebalance({ rb }: { rb: { n_members: number; weakest_members: PhRebalRow[]; nearest_non_members: PhRebalRow[]; method: string } }) {
  return (
    <section className="mb-4 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Rebalance watch · PSEi</div>
        <div className="text-[0.68rem] text-slate-500">{rb.n_members} members · the PSE reviews the list in February and August; the member list is updated by hand after each review</div>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <Table title="Smallest members (candidates to drop)" rows={rb.weakest_members} />
        <Table title="Largest non-members (candidates to add)" rows={rb.nearest_non_members} extra />
      </div>
      <p className="mt-2 text-[0.62rem] leading-relaxed text-slate-600">
        A screen on public numbers: {rb.method}. It shows where a change is plausible, not that one will happen; the PSE&apos;s announcement of a review result is the event.
      </p>
    </section>
  );
}
