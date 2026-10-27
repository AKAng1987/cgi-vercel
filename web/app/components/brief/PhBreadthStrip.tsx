import phData from "@/data/ph_breadth.json";
import { NetHighsChart } from "./NetHighsChart";

type PhGauge = { symbol: string; label: string; value: number; change: number | null; zone: string; days_below_30_of_60: number };
type PhSeries = { date: string; net: number; fast: number; slow: number; colour: "green" | "red" | "white" }[];

const COLOUR: Record<string, { dot: string; text: string; label: string }> = {
  red: { dot: "bg-red-500", text: "text-red-300", label: "RED" },
  white: { dot: "bg-slate-300", text: "text-slate-200", label: "CHOP" },
  green: { dot: "bg-emerald-500", text: "text-emerald-300", label: "GREEN" },
};

const ZONE: Record<string, string> = {
  oversold: "text-red-300",
  overbought: "text-emerald-300",
  neutral: "text-slate-400",
};

/**
 * Philippine breadth, the same read as the S&P strip above it: net new 52-week highs minus lows across the liquid PSE
 * names, the 8 and 20 day EMAs, and the share of those names above their 5, 20, 50 and 200 day averages. Computed in
 * Pulse from TradingView bars and exported by scripts/export_ph_breadth.py into data/ph_breadth.json, so it is as of the
 * last export, not live. The 30 and 70 lines are borrowed from the S&P gauges and are untested on the PSE.
 */
export function PhBreadthStrip() {
  const d = phData as unknown as {
    as_of: string; built: string; universe: string; streak_days: number; net: number; ema_fast: number; ema_slow: number;
    colour: string; series: PhSeries; gauges: PhGauge[];
  };
  if (!d.series?.length) return null;
  const c = COLOUR[d.colour] ?? COLOUR.white;

  return (
    <section className="mb-6 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">PH breadth</div>
        <div className="text-xs text-slate-500">
          net new highs is the primary · gauges confirm · {d.universe} · as of {d.as_of}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${c.dot}`} />
          <span className={`text-lg font-bold ${c.text}`}>{c.label}</span>
          <span className="text-sm text-slate-300">
            net <span className="font-semibold text-slate-100">{d.net}</span>
          </span>
          <span className="text-[0.7rem] text-slate-500">
            8ema {d.ema_fast} · 20ema {d.ema_slow} · {d.streak_days}d streak
          </span>
        </div>
      </div>

      <NetHighsChart series={d.series} />
      <div className="mt-0.5 flex gap-4 text-[0.6rem] text-slate-600">
        <span><span className="text-blue-400">—</span> 8 EMA</span>
        <span><span className="text-violet-400">—</span> 20 EMA</span>
        <span>{d.series.length} sessions</span>
        <span><span className="text-emerald-900">▉</span> 3d net highs</span>
        <span><span className="text-red-950">▉</span> 3d net lows</span>
        <span>unshaded = chop</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-4">
        {d.gauges.map((g) => (
          <div key={g.symbol} className="min-w-[5.5rem]">
            <div className="flex items-baseline gap-1.5">
              <span className="text-[0.7rem] font-medium text-slate-400">{g.symbol}</span>
              <span className={`text-base font-bold ${ZONE[g.zone]}`}>{g.value}</span>
              {g.change !== null && (
                <span className={`text-[0.65rem] ${g.change > 0 ? "text-emerald-500" : "text-red-500"}`}>
                  {g.change > 0 ? "+" : ""}
                  {g.change}
                </span>
              )}
            </div>
            <div className="text-[0.6rem] text-slate-600">{g.label}</div>
            {g.days_below_30_of_60 > 0 && (
              <div className="text-[0.6rem] text-slate-600">{g.days_below_30_of_60}/60d under 30</div>
            )}
          </div>
        ))}
      </div>

      <p className="mt-2 text-[0.65rem] leading-relaxed text-slate-600">
        Computed in Pulse from TradingView bars and exported here, so it is as of {d.as_of}, not live. Net new highs are closes at a 52-week
        high minus closes at a 52-week low across the liquid PSE names. The 30 and 70 lines are borrowed from the S&amp;P gauges and are not tested on the
        PSE. With about 65 names the net count is small, so read the percentages and the streak, not the size of the bars. Same colour rule as above.
      </p>
    </section>
  );
}
