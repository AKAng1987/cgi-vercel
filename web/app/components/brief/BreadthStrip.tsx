import { TechnicalsResponse } from "@/lib/types";

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
 * The daily glance. Net new highs is the primary read; the participation
 * gauges are confirmation. Ordered the way the user reads them.
 */
export function BreadthStrip({ t }: { t: TechnicalsResponse }) {
  const n = t.net_new_highs;
  const c = COLOUR[n.colour] ?? COLOUR.white;

  return (
    <section className="mb-6 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">Breadth</div>
        <div className="text-xs text-slate-500">net new highs is the primary · gauges confirm</div>
      </div>

      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <div className="flex items-center gap-2">
          <span className={`inline-block h-2.5 w-2.5 rounded-full ${c.dot}`} />
          <span className={`text-lg font-bold ${c.text}`}>{c.label}</span>
          <span className="text-sm text-slate-300">
            net <span className="font-semibold text-slate-100">{n.value}</span>
          </span>
          <span className="text-[0.7rem] text-slate-500">
            8ema {n.ema_fast} · 20ema {n.ema_slow}
          </span>
        </div>
        {n.last_cross && (
          <div className="text-[0.7rem] text-slate-500">
            last cross{" "}
            <span className={n.last_cross.direction === "up" ? "text-emerald-400" : "text-amber-400"}>
              {n.last_cross.direction}
            </span>{" "}
            {n.last_cross.date} ({n.last_cross.days_ago}d ago)
          </div>
        )}
      </div>

      <p className="mt-1.5 text-sm text-slate-200">{n.state}</p>

      <div className="mt-3 flex flex-wrap gap-4">
        {t.gauges.map((g) => (
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
        Red after a sell-off is the buying window — held in names stronger than the market. A cross
        down from the top starts chop, so take profits near it; a cross up from below while still red
        is where risk goes back on. {t.caveat}
      </p>
    </section>
  );
}
