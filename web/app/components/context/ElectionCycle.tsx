import study from "./election_cycle.json";

/**
 * Midterm elections and the S&P 500 (research/election_cycle). A static snapshot built 2026-11-04 from results.json: nothing is fetched
 * at view time. Descriptive. n = 19 midterms, so "not distinguishable" is the honest reading of a null, never "no effect".
 */
const pc = (v: number, d = 1) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(d)}%`;
const pts = (v: number, d = 1) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(d)} pts`;
const tone = (v: number) => (v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-slate-400");
const Num = ({ v, kind = "pc" }: { v: number; kind?: "pc" | "pts" }) => (
  <span className={`tabular-nums ${tone(v)}`}>{kind === "pc" ? pc(v) : pts(v)}</span>
);
const T = ["low vol", "mid vol", "high vol"];
const SCEN_SHORT: Record<string, string> = {
  "Pres party loses both (blue-wave analog)": "President's party lacks both chambers (blue-wave analog)",
  "Loses House only (Dem House / GOP Senate analog)": "Lacks House only (Dem House / GOP Senate analog)",
  "Loses Senate only (the other split)": "Lacks Senate only (the other split)",
  "Keeps both (red-wave analog)": "Holds both (red-wave analog)",
};

function Tile({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
      <div className="text-[0.62rem] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-2xl font-bold tabular-nums text-slate-100">{value}</div>
      {sub && <div className="text-[0.65rem] text-slate-500">{sub}</div>}
    </div>
  );
}

function ExcessBars() {
  const max = 0.25;
  return (
    <div>
      <div className="mb-1 text-[0.7rem] text-slate-300">
        12 months after each midterm vs the volatility-matched baseline <span className="text-slate-500">(excess return, points)</span>
      </div>
      <div className="space-y-[2px]">
        {study.events.map((e) => {
          const w = Math.min(Math.abs(e.excess252) / max, 1) * 50;
          const up = e.excess252 >= 0;
          return (
            <div key={e.year} className="flex items-center gap-2 text-[0.7rem]">
              <span className="w-9 tabular-nums text-slate-400">{e.year}</span>
              <div className="relative h-3 flex-1 rounded-sm bg-slate-900/60">
                <div className="absolute inset-y-0 left-1/2 w-px bg-slate-700" />
                <div
                  className={`absolute inset-y-0 ${up ? "bg-emerald-500/70" : "bg-rose-500/70"}`}
                  style={up ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
                />
              </div>
              <span className="w-16 text-right"><Num v={e.excess252} kind="pts" /></span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ElectionCycle() {
  const p = study.primary;
  const s2 = study.secondary;
  const live = study.live;
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.72rem] uppercase tracking-wide text-slate-400">Midterm elections and the S&amp;P 500</div>
        <div className="text-[0.66rem] text-slate-500">
          study of {study.n} midterms, 1950–2022 · built {study.built} · fresh-context audit {study.audit}
        </div>
      </div>

      <div className="mb-3 max-w-4xl rounded border border-amber-800 bg-amber-950/30 px-3 py-2 text-[0.78rem] leading-relaxed text-slate-300">
        <span className="font-semibold text-amber-300">Not distinguishable from the normal baseline.</span> The 12 months after a midterm
        averaged <Num v={p.mean_event} /> against <Num v={p.mean_baseline} /> for days in the same volatility band: an excess of{" "}
        <Num v={p.mean_excess} kind="pts" /> (permutation p = {p.p.toFixed(2)}). With only {study.n} midterms the test cannot reliably see
        anything under about {study.harness.smallest_detectable_pts} points, so a null here means <em>can&apos;t tell</em>, not <em>no effect</em>.
        Calendar context, never a forecast or a rule.
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile label="12 months after" value={pc(p.mean_event)} sub={`baseline ${pc(p.mean_baseline)} · excess ${pts(p.mean_excess)}`} />
        <Tile label="Day after the vote" value={pc(study.react_all.mean, 2)} sub={`up in ${study.react_all.up} of ${study.react_all.n} midterms`} />
        <Tile label="Mar–Sep of midterm years" value={pc(study.season.return.midterm_mean)} sub={`other years ${pc(study.season.return.other_mean)} · p = ${study.season.return.p.toFixed(2)}`} />
        <Tile label="Worst drawdown, Mar–Sep" value={pc(study.season.max_drawdown.midterm_mean)} sub={`other years ${pc(study.season.max_drawdown.other_mean)} · p = ${study.season.max_drawdown.p.toFixed(3)}`} />
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <ExcessBars />
        <div>
          <div className="mb-1 text-[0.7rem] text-slate-300">What the other windows say <span className="text-slate-500">(excess over baseline; 6 pre-registered tests)</span></div>
          <table className="w-full text-[0.75rem]">
            <thead>
              <tr className="border-b border-slate-800 text-left text-[0.65rem] uppercase text-slate-500">
                <th className="py-1 pr-2 font-medium">window</th>
                <th className="py-1 pr-2 text-right font-medium">excess</th>
                <th className="py-1 pr-2 text-right font-medium">95% interval</th>
                <th className="py-1 text-right font-medium">p</th>
              </tr>
            </thead>
            <tbody>
              {([
                ["+21 trading days", s2.post_21],
                ["+63 trading days", s2.post_63],
                ["+126 trading days", s2.post_126],
                ["12 months, 1994–2022 only", s2.primary_1994_2022],
              ] as const).map(([k, v]) => (
                <tr key={k} className="border-b border-slate-900">
                  <td className="py-1 pr-2 text-slate-300">{k}</td>
                  <td className="py-1 pr-2 text-right"><Num v={v.mean_excess} kind="pts" /></td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-500">{pts(v.ci95[0], 1)} to {pts(v.ci95[1], 1)}</td>
                  <td className={`py-1 text-right tabular-nums ${v.p < 0.05 ? "text-amber-400" : "text-slate-400"}`}>{v.p.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[0.68rem] leading-relaxed text-slate-500">
            Six tests were run, so about 0.3 false positives are expected at 5%. The weak midterm summer and the strong recovery after the
            vote are one story, and the main 12-month test did not confirm it. Only the 126-day window and the summer drawdown survive a
            strict multiple-test cut.
          </p>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 text-[0.7rem] text-slate-300">
          By outcome of the vote <span className="text-slate-500">(relative to the president&apos;s party, after the election; descriptive, not pre-registered)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-[0.75rem]">
            <thead>
              <tr className="border-b border-slate-800 text-left text-[0.65rem] uppercase text-slate-500">
                <th className="py-1 pr-2 font-medium">scenario</th>
                <th className="py-1 pr-2 text-right font-medium">n</th>
                <th className="py-1 pr-2 text-right font-medium">day after</th>
                <th className="py-1 pr-2 text-right font-medium">+21d</th>
                <th className="py-1 pr-2 text-right font-medium">+126d</th>
                <th className="py-1 pr-2 text-right font-medium">1m</th>
                <th className="py-1 pr-2 text-right font-medium">3m</th>
                <th className="py-1 pr-2 text-right font-medium">12m</th>
                <th className="py-1 text-right font-medium">12m excess</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(study.scenarios).map(([k, v]) => (
                <tr key={k} className="border-b border-slate-900 align-top">
                  <td className="py-1 pr-2 text-slate-300">
                    {SCEN_SHORT[k] ?? k}
                    <div className="text-[0.62rem] text-slate-600">{v.n ? v.years.join(", ") : "no historical case"}</div>
                  </td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-400">{v.n}</td>
                  {v.n ? (
                    <>
                      <td className="py-1 pr-2 text-right"><Num v={v.react as number} /></td>
                      <td className="py-1 pr-2 text-right"><Num v={v.r21 as number} /></td>
                      <td className="py-1 pr-2 text-right"><Num v={v.r126 as number} /></td>
                      <td className="py-1 pr-2 text-right"><Num v={v.r252 as number} /></td>
                      <td className="py-1 text-right"><Num v={v.excess252 as number} kind="pts" /></td>
                    </>
                  ) : (
                    <td colSpan={5} className="py-1 text-right text-slate-600">n/a</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 text-[0.7rem] text-slate-300">Every midterm</div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[840px] text-[0.72rem]">
            <thead>
              <tr className="border-b border-slate-800 text-left text-[0.62rem] uppercase text-slate-500">
                <th className="py-1 pr-2 font-medium">year</th>
                <th className="py-1 pr-2 text-right font-medium">6m in</th>
                <th className="py-1 pr-2 font-medium">House in → out</th>
                <th className="py-1 pr-2 font-medium">vol</th>
                <th className="py-1 pr-2 text-right font-medium">day after</th>
                <th className="py-1 pr-2 text-right font-medium">12m</th>
                <th className="py-1 pr-2 text-right font-medium">baseline</th>
                <th className="py-1 pr-2 text-right font-medium">excess</th>
                <th className="py-1 pr-2 text-right font-medium">Mar–Sep</th>
                <th className="py-1 pr-2 text-right font-medium">worst DD</th>
                <th className="py-1 font-medium">CGI</th>
              </tr>
            </thead>
            <tbody>
              {study.events.map((e) => (
                <tr key={e.year} className="border-b border-slate-900">
                  <td className="py-[3px] pr-2 tabular-nums text-slate-200">{e.year}</td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.ret6m} /></td>
                  <td className="py-[3px] pr-2 text-slate-300">
                    {e.house_before} → {e.house_after}
                    {e.house_before !== e.house_after && <span className="ml-1 text-amber-400">flip</span>}
                  </td>
                  <td className="py-[3px] pr-2 text-slate-500">{T[e.tercile]}</td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.react} /></td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.r21} /></td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.r63} /></td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.r252} /></td>
                  <td className="py-[3px] pr-2 text-right tabular-nums text-slate-500">{pc(e.baseline252)}</td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.excess252} kind="pts" /></td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.season_ret} /></td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.season_dd} /></td>
                  <td className="py-[3px] text-slate-500">{e.compass ? `C${e.compass}${e.grid ? `G${e.grid}` : ""}` : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[0.66rem] text-slate-600">
          &ldquo;6m in&rdquo; = S&amp;P 500 return over the 126 trading days to the close before election day (Up: +3% or more, Down: −3% or less, else Flat; split added after the main results, exploratory).
          House = majority party entering the vote and in the new Congress (D/R); &ldquo;flip&rdquo; = the House changed hands.
          Baseline = average 12-month return from days in the same expanding 20-day-volatility band, excluding days near any election.
          CGI regime exists only from 2004 (compass) and 2008 (grid).
        </p>
      </div>

      <p className="mt-2 text-[0.72rem] text-slate-400">
        By 6-month run-up, average 12-month excess:{" "}
        {(["Down", "Flat", "Up"] as const).map((k, i) => (
          <span key={k}>
            {i > 0 && " · "}
            {k} (n={study.state6[k].n}) <Num v={study.state6[k].excess252_mean} kind="pts" />
          </span>
        ))}
        . Descriptive; nothing here separates from the others at n = 19.
      </p>

      <div className="mt-4 rounded border border-slate-800 bg-slate-900/50 px-3 py-2 text-[0.78rem] text-slate-300">
        <span className="text-slate-500">2026 live case (not counted): </span>
        S&amp;P 500 closed at <span className="tabular-nums text-slate-100">{live.close.toLocaleString()}</span> on {live.close_date}, the eve of the
        vote: <span className="text-slate-100">{live.state}</span> going in ({pc(live.dd52w)} from the 52-week high, 3-month {pc(live.ret3m)}, 6-month {pc(live.ret6m)}),
        {" "}{T[live.tercile]} volatility. CGI regime then C{live.compass_hist}G{live.grid_hist}. Tracking at +1, +3, +6 and +12 months starts as the
        dates arrive (this snapshot is static: 2 Dec 2026, 2 Feb, 3 May and 2 Nov 2027).
      </div>

      <p className="mt-2 max-w-5xl text-[0.66rem] leading-relaxed text-slate-600">
        Method and checks: S&amp;P 500 price index (no dividends), Yahoo daily closes, {study.crosscheck.checked} closes cross-checked to TradingView
        with {study.crosscheck.gaps} gaps over 0.1%; the self-test finds a planted {study.harness.plant15_found} +15-point effect and
        {" "}{study.harness.noise_false} false claims on noise. Election results from the House Clerk (seats) and Wikipedia (Senate, because
        senate.gov blocked scripts). Pre-registered before any return was computed (research/election_cycle/PREREG.md). Source: research/election_cycle/RESULTS.md.
      </p>
    </div>
  );
}
