import history from "./themes_history.json";

/**
 * Retroactive themes in play: which themes the detector (api/themes_data.py)
 * would have had in force at each month end. Static -- regenerated locally by
 * scripts/themes_history_report.py, which replays the detector on price data
 * up to each date and writes themes_history.json. No API call, so it renders
 * even when the backtest API is down.
 *
 * Read it as a reconstruction, not a record: it uses today's theme legs, and
 * the stage cut-offs were measured on the full history, so older columns are
 * slightly flattered by hindsight. Stage colours are runway: green early,
 * amber mid, grey late.
 */
type Row = [string, string, string, number, string, string, number];
type Snap = { d: string; t: Row[] };

const STAGE_BG: Record<string, string> = {
  early: "bg-emerald-700/70",
  mid: "bg-amber-700/70",
  late: "bg-slate-600/70",
};

export function ThemesHistory() {
  const snaps = history.snapshots as unknown as Snap[];
  if (!snaps.length) return null;

  const by = new Map<string, Map<string, Row>>();
  for (const s of snaps) {
    for (const r of s.t) {
      if (!by.has(r[0])) by.set(r[0], new Map());
      by.get(r[0])!.set(s.d, r);
    }
  }
  const names = [...by.keys()].sort(
    (a, b) => by.get(b)!.size - by.get(a)!.size || a.localeCompare(b),
  );
  const monthName = (d: string) =>
    new Date(`${d}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });

  return (
    <section className="mt-10">
      <h2 className="mb-1 text-[0.7rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
        Themes in play, retroactively
      </h2>
      <p className="mb-3 max-w-3xl text-xs text-slate-400">
        The themes the detector would have had in force at each month end, from {monthName(snaps[0].d)} to{" "}
        {monthName(snaps[snaps.length - 1].d)} ({snaps.length} snapshots, each using only data up to that date).
        Hover a cell for the stage, age and lead ETF.
      </p>

      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="border-collapse text-[0.65rem]">
          <thead>
            <tr className="bg-slate-900 text-slate-500">
              <th className="sticky left-0 z-10 bg-slate-900 px-2 py-1 text-left font-medium">Theme</th>
              {snaps.map((s, i) => {
                const y = s.d.slice(0, 4);
                const showYear = i === 0 || y !== snaps[i - 1].d.slice(0, 4);
                return (
                  <th key={s.d} className="px-0 py-1 text-center font-normal" title={s.d}>
                    <div className="h-3 whitespace-nowrap text-left text-[0.6rem] text-slate-400">{showYear ? y : ""}</div>
                    <div className="text-[0.55rem] text-slate-600">
                      {new Date(`${s.d}T00:00:00Z`).toLocaleDateString("en-US", { month: "narrow", timeZone: "UTC" })}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {names.map((n) => (
              <tr key={n} className="border-t border-slate-800">
                <td className="sticky left-0 z-10 whitespace-nowrap bg-slate-950 px-2 py-0.5 text-slate-300">{n}</td>
                {snaps.map((s) => {
                  const r = by.get(n)!.get(s.d);
                  return (
                    <td key={s.d} className="p-px">
                      {r ? (
                        <div
                          className={`h-4 w-[18px] rounded-sm ${STAGE_BG[r[1]] ?? "bg-slate-700"}`}
                          title={`${n}: ${r[1]} ${r[2]}, ${r[3]}d, lead ${r[4]} (as of ${s.d})`}
                        />
                      ) : (
                        <div className="h-4 w-[18px]" />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.65rem] text-slate-500">
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-emerald-700/70 align-middle" />early</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-amber-700/70 align-middle" />mid</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-slate-600/70 align-middle" />late</span>
        <span>blank = no active run</span>
      </div>

      <p className="mt-2 max-w-3xl text-[0.65rem] leading-relaxed text-slate-600">
        Reconstructed with today&rsquo;s theme legs (extended 2026-10-09), so this is not a stored copy of what CGI
        showed then. Stage cut-offs (51 and 137 days) and the megatrend rule (over 365 days) were measured on the
        full history, so older columns are slightly flattered by hindsight. Prices are loaded from{" "}
        {history.load_from}, so a run&rsquo;s age is capped by how far back that goes. Discovery only, not an edge.
        Generated {history.generated_at.slice(0, 10)} by scripts/themes_history_report.py.
      </p>
    </section>
  );
}
