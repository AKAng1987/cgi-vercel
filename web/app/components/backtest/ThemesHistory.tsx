"use client";

import { useMemo, useState } from "react";
import history from "./themes_history.json";

/**
 * Themes in play, retroactively: which themes the detector (api/themes_data.py) would have had in force at each
 * month end. The committed JSON (scripts/themes_history_report.py) holds one stored snapshot per month, and this
 * component LOOKS UP the selected year and month; nothing is recomputed on view, so it renders even when the API is down.
 *
 * Read it as a reconstruction, not a record: it uses today's theme legs, and the stage cut-offs were measured on the
 * full history, so older months are slightly flattered by hindsight.
 */
type Row = [string, string, string, number, string, string, number]; // theme, stage, class, age, lead, onset, n_running
type Snap = { d: string; t: Row[] };

const STAGE_BG: Record<string, string> = {
  early: "bg-emerald-700/70",
  mid: "bg-amber-700/70",
  late: "bg-slate-600/70",
};
const STAGE_TEXT: Record<string, string> = {
  early: "text-emerald-300",
  mid: "text-amber-300",
  late: "text-slate-400",
};
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const snaps = history.snapshots as unknown as Snap[];
const yearOf = (d: string) => Number(d.slice(0, 4));
const monthOf = (d: string) => Number(d.slice(5, 7)) - 1;
const isMonthEnd = (d: string) => {
  const t = new Date(`${d}T00:00:00Z`);
  const next = new Date(t.getTime() + 86_400_000);
  return next.getUTCMonth() !== t.getUTCMonth();
};
const label = (d: string) =>
  new Date(`${d}T00:00:00Z`).toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

function Chip({
  on,
  disabled,
  children,
  onClick,
  title,
}: {
  on: boolean;
  disabled?: boolean;
  children: React.ReactNode;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      title={title}
      aria-pressed={on}
      className={`rounded border px-2 py-0.5 text-[0.68rem] ${
        on
          ? "border-emerald-700 bg-emerald-900/50 text-emerald-300"
          : disabled
            ? "cursor-not-allowed border-slate-900 text-slate-700"
            : "border-slate-700 text-slate-400 hover:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}

export function ThemesHistory() {
  const [selected, setSelected] = useState<string>(snaps.length ? snaps[snaps.length - 1].d : "");
  const years = useMemo(() => [...new Set(snaps.map((s) => yearOf(s.d)))], []);
  if (!snaps.length) return null;

  const selSnap = snaps.find((s) => s.d === selected) ?? snaps[snaps.length - 1];
  const year = yearOf(selSnap.d);
  const byMonth = new Map<number, Snap>();
  for (const s of snaps) if (yearOf(s.d) === year) byMonth.set(monthOf(s.d), s);
  const yearSnaps = [...byMonth.entries()].sort((a, b) => a[0] - b[0]);

  const pickYear = (y: number) => {
    const inYear = snaps.filter((s) => yearOf(s.d) === y);
    // keep the same month when it exists, otherwise the nearest later month, otherwise the last one of that year
    const same = inYear.find((s) => monthOf(s.d) === monthOf(selSnap.d));
    setSelected((same ?? inYear.find((s) => monthOf(s.d) > monthOf(selSnap.d)) ?? inYear[inYear.length - 1]).d);
  };

  const rows = [...selSnap.t].sort((a, b) => (a[2] !== b[2] ? (a[2] === "megatrend" ? -1 : 1) : b[3] - a[3]));
  const latest = snaps[snaps.length - 1];
  const monthToDate = selSnap.d === latest.d && !isMonthEnd(latest.d);

  // strip: every theme in force in any month of the selected year, newest-first by how many months it appears
  const stripThemes = [...new Set(yearSnaps.flatMap(([, s]) => s.t.map((r) => r[0])))].sort((a, b) => {
    const n = (t: string) => yearSnaps.filter(([, s]) => s.t.some((r) => r[0] === t)).length;
    return n(b) - n(a) || a.localeCompare(b);
  });

  return (
    <section className="mt-10">
      <h2 className="mb-1 text-[0.7rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
        Themes in play, retroactively
      </h2>
      <p className="mb-3 max-w-3xl text-xs text-slate-400">
        Pick a month to see the themes the detector would have had in force at that month end, using only data up to
        that date ({snaps.length} stored snapshots, {label(snaps[0].d)} to {label(latest.d)}).
      </p>

      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[0.62rem] uppercase tracking-wide text-slate-500">Year</span>
        {years.map((y) => (
          <Chip key={y} on={y === year} onClick={() => pickYear(y)}>
            {y}
          </Chip>
        ))}
      </div>
      <div className="mb-3 flex flex-wrap items-center gap-1.5">
        <span className="mr-1 text-[0.62rem] uppercase tracking-wide text-slate-500">Month</span>
        {MONTHS.map((m, i) => {
          const s = byMonth.get(i);
          return (
            <Chip key={m} on={s?.d === selSnap.d} disabled={!s} onClick={() => s && setSelected(s.d)} title={s ? s.d : "no snapshot"}>
              {m}
            </Chip>
          );
        })}
      </div>

      <div className="mb-1 text-xs text-slate-300">
        As of <span className="font-medium text-slate-100">{label(selSnap.d)}</span>
        {monthToDate && <span className="text-slate-500"> (latest bar, month to date)</span>}
        <span className="text-slate-500"> · {rows.length} themes in force</span>
      </div>
      <div className="overflow-x-auto rounded border border-slate-800">
        <table className="w-full border-collapse text-[0.72rem]">
          <thead>
            <tr className="bg-slate-900 text-slate-500">
              <th className="px-2 py-1 text-left font-medium">Theme</th>
              <th className="px-2 py-1 text-left font-medium">Stage</th>
              <th className="px-2 py-1 text-left font-medium">Class</th>
              <th className="px-2 py-1 text-right font-medium">Age</th>
              <th className="px-2 py-1 text-left font-medium">Onset</th>
              <th className="px-2 py-1 text-left font-medium">Lead ETF</th>
              <th className="px-2 py-1 text-right font-medium">Legs running</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-2 py-3 text-slate-500">
                  No theme was in force at this date.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r[0]} className="border-t border-slate-800">
                <td className="whitespace-nowrap px-2 py-1 text-slate-200">{r[0]}</td>
                <td className={`px-2 py-1 ${STAGE_TEXT[r[1]] ?? "text-slate-400"}`}>{r[1]}</td>
                <td className="px-2 py-1 text-slate-400">{r[2]}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-300">{r[3]}d</td>
                <td className="px-2 py-1 tabular-nums text-slate-500">{r[5]}</td>
                <td className="px-2 py-1 text-slate-300">{r[4]}</td>
                <td className="px-2 py-1 text-right tabular-nums text-slate-400">{r[6]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 text-[0.62rem] uppercase tracking-wide text-slate-500">{year}: age in days at each month end</div>
      <div className="mt-1 overflow-x-auto rounded border border-slate-800">
        <table className="w-full border-collapse text-[0.62rem]">
          <thead>
            <tr className="bg-slate-900 text-slate-500">
              <th className="px-2 py-1 text-left font-medium">Theme</th>
              {MONTHS.map((m, i) => {
                const s = byMonth.get(i);
                return (
                  <th key={m} className="px-0 py-1 text-center font-medium">
                    <button
                      type="button"
                      disabled={!s}
                      onClick={() => s && setSelected(s.d)}
                      className={`w-full px-1 ${s?.d === selSnap.d ? "text-emerald-300" : s ? "text-slate-400 hover:text-slate-200" : "cursor-not-allowed text-slate-700"}`}
                    >
                      {m}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {stripThemes.map((n) => (
              <tr key={n} className="border-t border-slate-800">
                <td className="whitespace-nowrap px-2 py-0.5 text-slate-300">{n}</td>
                {MONTHS.map((m, i) => {
                  const s = byMonth.get(i);
                  const r = s?.t.find((x) => x[0] === n);
                  return (
                    <td key={m} className="p-px">
                      {r && s ? (
                        <button
                          type="button"
                          onClick={() => setSelected(s.d)}
                          title={`${n}: ${r[1]} ${r[2]}, ${r[3]}d, lead ${r[4]} (${s.d})`}
                          className={`h-5 w-full min-w-[26px] rounded-sm text-center tabular-nums text-slate-100 ${STAGE_BG[r[1]] ?? "bg-slate-700"} ${s.d === selSnap.d ? "ring-1 ring-emerald-400" : ""}`}
                        >
                          {r[3]}
                        </button>
                      ) : (
                        <div className="h-5 w-full min-w-[26px]" />
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

      <p className="mt-3 max-w-3xl text-[0.65rem] leading-relaxed text-slate-600">
        Reconstructed with today&rsquo;s theme legs (extended 2026-10-09), so this is not a stored copy of what CGI
        showed then. A run starts where the current stretch above its 200-day relative-strength trend began, with
        dips under 15 calendar days merged into it, so a one-day dip no longer resets a mature theme&rsquo;s age.
        Stage cut-offs (55 and 152 days) and the megatrend rule (over 365 days) were measured on the full history, so
        older months are slightly flattered by hindsight. Prices are loaded from {history.load_from}, so a run&rsquo;s
        age is capped by how far back that goes. A theme can only appear once one of its ETFs has 400 days of
        history, so the earliest months can include only themes whose ETFs already existed. Discovery only, not an
        edge. Generated {history.generated_at.slice(0, 10)} by scripts/themes_history_report.py.
      </p>
    </section>
  );
}
