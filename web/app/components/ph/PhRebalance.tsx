import { PhIndex, PhRebalRow } from "@/lib/types";
import { pctColor } from "@/lib/regimeConstants";
import { PhTicker } from "./PhSelect";
import { dayLabel, peso, pct } from "./phFormat";

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
              <td className="py-1 pr-2"><PhTicker s={r.s} list={rows.map((x) => x.s)}>{r.s}</PhTicker><span className="ml-1 text-[0.58rem] text-slate-500">{r.ind ?? ""}</span></td>
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
const PROV: Record<string, string> = { MSCI: "MSCI", FTSE: "FTSE", WISDOMTREE: "WisdomTree", PSE: "PSE" };

function IndexCalendar({ ix }: { ix: PhIndex }) {
  const up = ix.calendar.filter((e) => e.status !== "done");
  return (
    <div className="mb-5 grid gap-5 md:grid-cols-2">
      <div>
        <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">Index review calendar (MSCI · FTSE · WisdomTree · PSE)</div>
        <ul className="space-y-1 text-xs">
          {up.map((e, i) => (
            <li key={`${e.provider}-${e.event}-${i}`} className="flex gap-2">
              <span className="w-20 shrink-0 tabular-nums text-slate-400">{e.announce ? dayLabel(e.announce) : "date tbc"}</span>
              <span className="w-20 shrink-0 font-semibold text-slate-200">{PROV[e.provider] ?? e.provider}</span>
              <span className="text-slate-300">
                {e.event}{e.effective ? ` · effective ${dayLabel(e.effective)}` : ""}{e.status === "estimated" ? " · estimate" : ""}
                {e.days_to_announce != null && e.days_to_announce >= 0 && e.days_to_announce <= 14 ? <span className="ml-1 text-amber-300">in {e.days_to_announce}d</span> : null}
                {e.note && <span className="ml-1 text-slate-600">{e.note}</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <div className="mb-1 text-[0.6rem] uppercase tracking-wide text-slate-500">Announced changes{ix.circular ? ` · latest PSE circular ${ix.circular.circular}, ${dayLabel(ix.circular.date)}` : ""}</div>
        {ix.events.length === 0 ? (
          <p className="text-xs text-slate-500">nothing stored in the last 90 days. {ix.note}.</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {ix.events.map((e, i) => (
              <li key={`${e.provider}-${e.date}-${i}`} className="flex gap-2">
                <span className="w-14 shrink-0 tabular-nums text-slate-500">{dayLabel(e.date)}</span>
                <span className="w-16 shrink-0 font-semibold text-slate-200">{PROV[e.provider] ?? e.provider}</span>
                <span className="text-slate-300">
                  {e.index && <span className="text-slate-500">{e.index} </span>}
                  {e.kind === "add" && <span className="text-emerald-300">added {e.symbols.join(", ")}</span>}
                  {e.kind === "delete" && <span className="text-red-300">removed {e.symbols.join(", ")}</span>}
                  {e.kind === "note" && <span>{e.note}</span>}
                  {e.effective ? ` · effective ${dayLabel(e.effective)}` : ""}
                  {e.source_url && <a className="ml-1 text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={e.source_url}>source ↗</a>}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function PhRebalance({ rb, ix }: { rb: { n_members: number; weakest_members: PhRebalRow[]; nearest_non_members: PhRebalRow[]; method: string }; ix: PhIndex }) {
  return (
    <section className="mb-4 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Rebalance watch · PSEi, MSCI, FTSE, WisdomTree</div>
        <div className="text-[0.68rem] text-slate-500">PSEi {rb.n_members} members{ix.psei_members_as_of ? ` (list from the PSE circular of ${dayLabel(ix.psei_members_as_of)})` : ""}</div>
      </div>
      <IndexCalendar ix={ix} />
      <div className="grid gap-5 md:grid-cols-2">
        <Table title="Smallest members (candidates to drop)" rows={rb.weakest_members} />
        <Table title="Largest non-members (candidates to add)" rows={rb.nearest_non_members} extra />
      </div>
      <p className="mt-2 text-[0.62rem] leading-relaxed text-slate-600">
        The member and non-member screen is for the PSEi only: {rb.method}. It shows where a change is plausible, not that one will happen; the announcement is the event. MSCI, FTSE and WisdomTree do not publish per-stock candidates, so those rows appear only after each announcement.
      </p>
    </section>
  );
}
