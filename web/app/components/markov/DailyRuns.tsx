import { MarkovRun, SignalRow } from "@/lib/types";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

export function DailyRuns({ runs, latest, nDaily }: { runs: MarkovRun[]; latest: SignalRow | null; nDaily: number }) {
  const div = latest?.divergence?.axes;
  return (
    <section>
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Daily audit trail</div>
        <div className="text-xs text-slate-500">{nDaily} rows written at 00:55 UTC, collapsed into runs</div>
      </div>
      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="w-full border-collapse text-[0.76rem]">
          <thead>
            <tr>
              {["Regime", "From", "To", "Days"].map((h, i) => (
                <th key={h} className={`bg-[#1F2937] px-2 py-1 text-[0.68rem] uppercase tracking-wide text-slate-400 ${i === 3 ? "text-right" : "text-left"}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.start} className="border-t border-slate-800/60">
                <td className="px-2 py-1.5">
                  <span className="font-bold text-slate-100" title={COMPASS_Q_LABELS[r.compass]}>C{r.compass}</span>
                  <span className="text-slate-500"> × </span>
                  <span className="font-bold text-slate-100" title={GRID_Q_LABELS[r.grid]}>G{r.grid}</span>
                </td>
                <td className="px-2 py-1.5 text-slate-300">{r.start}</td>
                <td className="px-2 py-1.5 text-slate-300">{r.end}</td>
                <td className="px-2 py-1.5 text-right text-slate-300">{r.days}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {div && (
        <div className="mt-3 text-xs text-slate-500">
          <span className="text-[0.65rem] uppercase tracking-[2px] text-slate-600">Experimental market-implied read ({latest?.signal_date}):</span>
          {(["credit", "inflation"] as const).map((k) => {
            const a = div[k];
            if (!a) return null;
            const dir = a.direction;
            return (
              <span key={k} className="ml-3">
                <span className="capitalize text-slate-400">{k}</span>{" "}
                <span className={dir ? "font-bold text-[#FCD34D]" : "text-slate-300"}>
                  {dir ? (dir === "market_up" ? "market leans ↑" : "market leans ↓") : "agrees with print"}
                </span>
                <span className="ml-1 text-slate-600">(P↑ {a.p_up === null ? "—" : a.p_up.toFixed(2)})</span>
              </span>
            );
          })}
        </div>
      )}
    </section>
  );
}
