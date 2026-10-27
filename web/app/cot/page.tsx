import { apiFetch } from "@/lib/api";
import { CotResponse } from "@/lib/types";
import { CotCard } from "../components/cot/CotCard";

// The data pages wait on the API (cold start or a cache rebuild can take 30-75 s): give them the full 60 s.
export const maxDuration = 60;

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
        Commitment of Traders · {data.source} · as of {data.as_of_weekday ? `${data.as_of_weekday} ` : ""}{data.as_of}{data.published_est ? `, published ${data.published_est}` : ""}. Large specs are momentum —
        most long at tops, most short at bottoms — so the extremes are where the fuel for
        continuation has gone. <span className="text-slate-300">COT index</span> is where this
        week&apos;s net sits in its own range: 0 = most short it has been, 100 = most long.
      </p>

      {data.cadence?.problem && (
        <p className="mb-4 rounded border border-amber-800 bg-amber-950/40 p-2 text-xs text-amber-300">
          The report calendar has changed in a way this page does not know: {data.cadence.problem}. Numbers below are the
          weekly reports only; check the CFTC schedule.
        </p>
      )}

      {data.cadence?.twice_weekly && (
        <p className="mb-4 text-xs text-slate-500">
          The CFTC now publishes twice a week
          {data.cadence.first_non_tuesday_seen ? ` (first non-Tuesday as-of date ${data.cadence.first_non_tuesday_seen})` : ""}.
          The weekly report sets the numbers and extremes; the earlier read is shown below as interim.
        </p>
      )}

      {data.interim && data.interim.contracts.length > 0 && (
        <section className="mb-5 rounded border border-slate-800 bg-slate-900/40 p-3">
          <div className="mb-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-slate-400">
            Interim read · as of {data.interim.as_of} · published {data.interim.published_est}
          </div>
          <p className="mb-2 text-[0.65rem] text-slate-500">{data.interim.note}</p>
          <div className="flex flex-wrap gap-2">
            {data.interim.contracts
              .filter((c) => c.cot_index_3y !== null && (c.cot_index_3y <= 10 || c.cot_index_3y >= 90 || Math.abs((c.cot_index_3y ?? 50) - (c.final_cot_index_3y ?? 50)) >= 10))
              .map((c) => (
                <div key={c.contract} className="rounded border border-slate-700 px-2 py-1 text-[0.65rem] text-slate-400">
                  <span className="font-semibold text-slate-200">{c.contract}</span> index {c.final_cot_index_3y} → {c.cot_index_3y} ·
                  specs {c.change_vs_final >= 0 ? "+" : ""}
                  {c.change_vs_final.toLocaleString()} since the weekly report
                </div>
              ))}
          </div>
          <p className="mt-2 text-[0.6rem] text-slate-600">
            Only contracts at an extreme or that moved 10+ index points since the weekly report are listed.
          </p>
        </section>
      )}

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
