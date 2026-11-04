import study from "./presidential_cycle.json";

/**
 * Presidential elections and the S&P 500 (research/presidential_cycle). A static snapshot built 2026-11-04 from results.json: nothing is
 * fetched at view time. Descriptive. n = 19 presidential elections, so "not distinguishable" is the honest reading of a null.
 */
const pc = (v: number, d = 1) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(d)}%`;
const pts = (v: number, d = 1) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toFixed(d)} pts`;
const tone = (v: number) => (v > 0 ? "text-emerald-400" : v < 0 ? "text-rose-400" : "text-slate-400");
const Num = ({ v, kind = "pc" }: { v: number; kind?: "pc" | "pts" }) => (
  <span className={`tabular-nums ${tone(v)}`}>{kind === "pc" ? pc(v) : pts(v)}</span>
);
const T = ["low vol", "mid vol", "high vol"];

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
  const max = 0.35;
  return (
    <div>
      <div className="mb-1 text-[0.7rem] text-slate-300">
        12 months after each presidential election vs the volatility-matched baseline <span className="text-slate-500">(excess return, points)</span>
      </div>
      <div className="space-y-[2px]">
        {study.events.map((e) => {
          const w = Math.min(Math.abs(e.excess252) / max, 1) * 50;
          const up = e.excess252 >= 0;
          return (
            <div key={e.year} className="flex items-center gap-2 text-[0.7rem]">
              <span className="w-9 tabular-nums text-slate-400">{e.year}</span>
              <span className="w-4 text-slate-500">{e.winner}</span>
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

const GROUP_LABEL: Record<string, Record<string, string>> = {
  winner: { D: "Democrat won", R: "Republican won" },
  party_change: { True: "White House changed party", False: "Party held it" },
  incumbent_ran: { True: "Incumbent ran", False: "Open seat" },
  state6: { Down: "6-month run-up down", Flat: "6-month run-up flat", Up: "6-month run-up up" },
};

export function PresidentialCycle() {
  const p = study.primary;
  const s = study.secondary;
  const se = study.season;
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.72rem] uppercase tracking-wide text-slate-400">Presidential elections and the S&amp;P 500</div>
        <div className="text-[0.66rem] text-slate-500">
          study of {study.n} elections, 1952–2024 · built {study.built} · fresh-context audit {study.audit}
        </div>
      </div>

      <div className="mb-3 max-w-4xl rounded border border-amber-800 bg-amber-950/30 px-3 py-2 text-[0.78rem] leading-relaxed text-slate-300">
        <span className="font-semibold text-amber-300">Not distinguishable from the normal baseline, in either part.</span> The 12 months after
        a presidential election averaged <Num v={p.mean_event} /> against <Num v={p.mean_baseline} /> for days in the same volatility band:
        an excess of <Num v={p.mean_excess} kind="pts" /> (p = {p.p.toFixed(2)}). January–June of presidential years returned{" "}
        <Num v={se.janjun_ret.pres_mean} /> against <Num v={se.janjun_ret.other_mean} /> in other years (p = {se.janjun_ret.p.toFixed(2)}).
        With {study.n} elections the first test cannot reliably see anything under about {study.harness.a.sde} points, so a null means{" "}
        <em>can&apos;t tell</em>, not <em>no effect</em>. Calendar context, never a forecast or a rule.
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile label="12 months after" value={pc(p.mean_event)} sub={`baseline ${pc(p.mean_baseline)} · excess ${pts(p.mean_excess)}`} />
        <Tile label="Day after the vote" value={pc(study.react_all.mean, 2)} sub={`up in ${study.react_all.up} of ${study.react_all.n} elections`} />
        <Tile label="Jan–Jun, primary season" value={pc(se.janjun_ret.pres_mean)} sub={`other years ${pc(se.janjun_ret.other_mean)} · p = ${se.janjun_ret.p.toFixed(2)}`} />
        <Tile label="Jul–Oct, to the vote" value={pc(se.julopt_ret.pres_mean)} sub={`other years ${pc(se.julopt_ret.other_mean)} · p = ${se.julopt_ret.p.toFixed(2)}`} />
      </div>

      <div className="mt-4 grid gap-6 lg:grid-cols-2">
        <ExcessBars />
        <div>
          <div className="mb-1 text-[0.7rem] text-slate-300">What the other windows say <span className="text-slate-500">(excess over baseline; 8 pre-registered tests, 0 claims)</span></div>
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
                ["+21 trading days", s.post_21],
                ["+63 trading days", s.post_63],
                ["+126 trading days", s.post_126],
              ] as const).map(([k, v]) => (
                <tr key={k} className="border-b border-slate-900">
                  <td className="py-1 pr-2 text-slate-300">{k}</td>
                  <td className="py-1 pr-2 text-right"><Num v={v.mean_excess} kind="pts" /></td>
                  <td className="py-1 pr-2 text-right tabular-nums text-slate-500">{pts(v.ci95[0], 1)} to {pts(v.ci95[1], 1)}</td>
                  <td className="py-1 text-right tabular-nums text-slate-400">{v.p.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-[0.68rem] leading-relaxed text-slate-500">
            Season returns, presidential years vs the other 56 years since 1950: Jan–Jun {pc(se.janjun_ret.pres_mean)} vs {pc(se.janjun_ret.other_mean)},
            Jul–Oct {pc(se.julopt_ret.pres_mean)} vs {pc(se.julopt_ret.other_mean)}, worst Jan–Jun drawdown {pc(se.janjun_dd.pres_mean)} vs{" "}
            {pc(se.janjun_dd.other_mean)}. The primary-season window is a fixed January–June calendar proxy, not the actual nomination dates.
          </p>
        </div>
      </div>

      <div className="mt-4">
        <div className="mb-1 text-[0.7rem] text-slate-300">
          By who won and how <span className="text-slate-500">(hand-entered public facts; descriptive, not tested)</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-[0.75rem]">
            <thead>
              <tr className="border-b border-slate-800 text-left text-[0.65rem] uppercase text-slate-500">
                <th className="py-1 pr-2 font-medium">group</th>
                <th className="py-1 pr-2 text-right font-medium">n</th>
                <th className="py-1 pr-2 text-right font-medium">day after</th>
                <th className="py-1 pr-2 text-right font-medium">12m</th>
                <th className="py-1 pr-2 text-right font-medium">12m excess</th>
                <th className="py-1 text-right font-medium">Jan–Jun</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(study.groups).flatMap(([gk, g]) =>
                Object.entries(g).map(([k, v]) => (
                  <tr key={`${gk}-${k}`} className="border-b border-slate-900">
                    <td className="py-[3px] pr-2 text-slate-300">{GROUP_LABEL[gk]?.[k] ?? k}</td>
                    <td className="py-[3px] pr-2 text-right tabular-nums text-slate-400">{v.n}</td>
                    <td className="py-[3px] pr-2 text-right"><Num v={v.react as number} /></td>
                    <td className="py-[3px] pr-2 text-right"><Num v={v.r252 as number} /></td>
                    <td className="py-[3px] pr-2 text-right"><Num v={v.excess252 as number} kind="pts" /></td>
                    <td className="py-[3px] text-right"><Num v={v.janjun_ret as number} /></td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-1 max-w-5xl text-[0.66rem] leading-relaxed text-slate-600">
          The widest gap is the winner&apos;s party (Democrat +8.3 vs Republican −6.5 points, about 2 standard errors), one of roughly nine groupings looked at
          in groups of 8 and 11 with a few years doing the work: about one gap this size is expected by chance, so it is folklore on known history, not a finding.
        </p>
      </div>

      <div className="mt-4">
        <div className="mb-1 text-[0.7rem] text-slate-300">Every presidential election</div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-[0.72rem]">
            <thead>
              <tr className="border-b border-slate-800 text-left text-[0.62rem] uppercase text-slate-500">
                <th className="py-1 pr-2 font-medium">year</th>
                <th className="py-1 pr-2 font-medium">won</th>
                <th className="py-1 pr-2 font-medium">party</th>
                <th className="py-1 pr-2 font-medium">incumbent</th>
                <th className="py-1 pr-2 text-right font-medium">6m in</th>
                <th className="py-1 pr-2 font-medium">vol</th>
                <th className="py-1 pr-2 text-right font-medium">day after</th>
                <th className="py-1 pr-2 text-right font-medium">12m</th>
                <th className="py-1 pr-2 text-right font-medium">baseline</th>
                <th className="py-1 pr-2 text-right font-medium">excess</th>
                <th className="py-1 text-right font-medium">Jan–Jun</th>
              </tr>
            </thead>
            <tbody>
              {study.events.map((e) => (
                <tr key={e.year} className="border-b border-slate-900">
                  <td className="py-[3px] pr-2 tabular-nums text-slate-200">{e.year}</td>
                  <td className="py-[3px] pr-2 text-slate-300">{e.winner}</td>
                  <td className="py-[3px] pr-2 text-slate-500">{e.party_change ? "changed" : "held"}</td>
                  <td className="py-[3px] pr-2 text-slate-500">{e.incumbent_ran ? "ran" : "open seat"}</td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.ret6m} /></td>
                  <td className="py-[3px] pr-2 text-slate-500">{T[e.tercile]}</td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.react} /></td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.r252} /></td>
                  <td className="py-[3px] pr-2 text-right tabular-nums text-slate-500">{pc(e.baseline252)}</td>
                  <td className="py-[3px] pr-2 text-right"><Num v={e.excess252} kind="pts" /></td>
                  <td className="py-[3px] text-right"><Num v={e.janjun_ret} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-1 text-[0.66rem] text-slate-600">
          &ldquo;6m in&rdquo; = S&amp;P 500 return over the 126 trading days to the close before the vote. Baseline = average 12-month return from days in the same
          expanding 20-day-volatility band, excluding days near any presidential election. 2024 counts as an open seat (the incumbent withdrew).
        </p>
      </div>

      <p className="mt-2 max-w-5xl text-[0.66rem] leading-relaxed text-slate-600">
        Method and checks: S&amp;P 500 price index (no dividends), Yahoo daily closes, {study.crosscheck.checked} closes cross-checked to TradingView with{" "}
        {study.crosscheck.gaps} gaps over 0.1%; the self-test finds a planted +15 point effect {study.harness.a.found} (noise falsely claimed {study.harness.a.noise})
        for the vote test and +10 points {study.harness.b.found} (noise {study.harness.b.noise}) for the season test. Pre-registered before any return was computed. The
        2026 midterm study above carries the live case; there is none here (next presidential vote: 2028).
      </p>
    </div>
  );
}
