import { TimelineEvent } from "@/lib/types";

const INFORM_COLOR: Record<string, string> = {
  liquidity: "#60A5FA", credit: "#A78BFA", growth: "#34D399", inflation: "#F97316", positioning: "#94A3B8",
};

function daysFrom(asOf: string, date: string): number {
  return Math.round((Date.parse(date) - Date.parse(asOf)) / 86_400_000);
}

export function Timeline({ events, asOf }: { events: TimelineEvent[]; asOf: string }) {
  if (!events.length) return null;
  // group by date so same-day events sit together
  const byDate = new Map<string, TimelineEvent[]>();
  for (const e of events) byDate.set(e.date, [...(byDate.get(e.date) ?? []), e]);
  return (
    <section className="mb-6">
      <div className="mb-2 flex items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">Next 45 days</div>
        <div className="text-xs text-slate-500">
          <span className="font-bold text-slate-300">bold</span> = sets an axis · others feed the nowcasts and narrative · colour = what it informs
        </div>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {Array.from(byDate.entries()).map(([date, evs]) => {
          const d = daysFrom(asOf, date);
          const hasAxis = evs.some((e) => e.tier === "axis");
          return (
            <div key={date} className={`min-w-[7.5rem] shrink-0 rounded border px-2 py-1.5 ${hasAxis ? "border-slate-600 bg-slate-900/80" : "border-slate-800 bg-slate-900/40"}`}>
              <div className="flex items-baseline justify-between text-[0.68rem]">
                <span className={hasAxis ? "font-bold text-slate-100" : "text-slate-300"}>{date.slice(5)}</span>
                <span className="text-slate-600">{d === 0 ? "today" : d === 1 ? "tmrw" : `+${d}d`}</span>
              </div>
              {evs.map((e) => (
                <div key={e.type} className={`mt-0.5 text-[0.7rem] leading-tight ${e.tier === "axis" ? "font-bold text-slate-100" : "text-slate-400"}`}>
                  <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full align-middle" style={{ background: INFORM_COLOR[e.informs[0]] ?? "#64748B" }} title={`informs ${e.informs.join(", ")}`} />
                  {e.label}
                </div>
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}
