import { apiFetch } from "@/lib/api";
import { CotResponse } from "@/lib/types";
import { CotCard } from "../components/cot/CotCard";

/**
 * POSITIONING. Cards per contract grouped by sector, after the layout the
 * user's officemate built -- price sparkline of net spec positioning, the
 * net figure and its change. The COT index is what makes it comparable
 * across contracts: where this week's net sits in its own range.
 */
export default async function CotPage() {
  const data = await apiFetch<CotResponse>("/api/cot");

  return (
    <main className="mx-auto max-w-7xl p-6">
      <h1 className="mb-1 text-2xl font-bold">POSITIONING</h1>
      <p className="mb-4 text-xs leading-relaxed text-slate-400">
        Commitment of Traders · {data.source} · week of {data.as_of}. Large specs are momentum —
        most long at tops, most short at bottoms — so the extremes are where the fuel for
        continuation has gone. <span className="text-slate-300">COT index</span> is where this
        week&apos;s net sits in its own range: 0 = most short it has been, 100 = most long.
      </p>

      {data.extremes.length > 0 && (
        <section className="mb-5 rounded border border-slate-700 bg-slate-900/70 p-3">
          <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
            At the extremes
          </div>
          <div className="flex flex-wrap gap-2">
            {data.extremes.map((e) => (
              <div
                key={e.contract}
                className={`rounded border px-2.5 py-1.5 ${
                  (e.cot_index_3y ?? 50) <= 10
                    ? "border-emerald-800 bg-emerald-950/50"
                    : "border-red-800 bg-red-950/50"
                }`}
              >
                <div className="text-sm font-semibold text-slate-100">{e.contract}</div>
                <div className="text-[0.65rem] text-slate-400">
                  index {e.cot_index_3y} · OI-basis {e.cot_index_3y_pct_oi} · specs{" "}
                  {e.spec.toLocaleString()}
                </div>
                <div className="text-[0.65rem] text-slate-500">{e.signal}</div>
              </div>
            ))}
          </div>
        </section>
      )}

      {data.groups.map((g) => (
        <section key={g.group} className="mb-6">
          <div className="mb-2 text-[0.6rem] font-bold uppercase tracking-[2px] text-slate-500">
            {g.group}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {g.contracts.map((c) => (
              <CotCard key={c.contract} c={c} />
            ))}
          </div>
        </section>
      ))}

      <p className="mt-4 text-[0.68rem] leading-relaxed text-slate-600">{data.caveat}</p>
    </main>
  );
}
