import { RegimeBlock } from "@/lib/types";
import { regimeView } from "@/lib/regimeView";

const REGIME_GOLD = "var(--cgi-gold)";

function StatLine({
  label,
  value,
  refValue,
  pct,
  asOf,
}: {
  label: string;
  value: number | string | null;
  refValue?: number | string | null;
  pct: string;
  asOf?: string | null;
}) {
  if (value === null || value === undefined) {
    return (
      <div className="mb-[3px]">
        <span className="text-slate-400">{label}&nbsp;</span>—
      </div>
    );
  }
  return (
    <div className="mb-[3px]">
      <span className="text-slate-400">{label}&nbsp;</span>
      <b>{value}</b>{" "}
      {refValue !== undefined && refValue !== null && (
        <span className="text-[0.7rem] text-slate-500">
          (was {refValue}, {pct})
        </span>
      )}
      {asOf && <span className="ml-1 text-[0.7rem] text-slate-500">as of {asOf}</span>}
    </div>
  );
}

export function RegimeCard({
  kind,
  data,
}: {
  kind: "compass" | "grid";
  data: RegimeBlock;
}) {
  const v = regimeView(kind, data);
  const [ax1, ax2] = v.axes;

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <div className="mb-1.5 text-[0.62rem] uppercase tracking-[2px] text-slate-400">
        {v.title}
      </div>
      <div className="mb-2.5 text-[1.05rem] font-bold" style={{ color: REGIME_GOLD }}>
        {v.regimeLabel}
      </div>

      {v.staleNote && (
        <div className="mb-2.5 rounded border border-amber-700 bg-amber-950/50 px-2 py-1 text-xs text-amber-400">
          {v.staleNote}
        </div>
      )}

      <div className="mb-2.5 flex items-baseline gap-5">
        <div>
          <div className="text-[0.68rem] text-slate-500">{ax1.label}</div>
          <div className="text-[1.6rem] font-bold leading-tight" style={{ color: ax1.color }}>
            {ax1.arrow} {ax1.word}
          </div>
        </div>
        <div className="w-px self-stretch bg-slate-700" />
        <div>
          <div className="text-[0.68rem] text-slate-500">{ax2.label}</div>
          <div className="text-[1.6rem] font-bold leading-tight" style={{ color: ax2.color }}>
            {ax2.arrow} {ax2.word}
          </div>
        </div>
      </div>

      <div className="border-t border-slate-800 pt-2 text-[0.78rem] text-slate-200">
        {v.stats.length === 0 && <div className="text-slate-500">No metrics available</div>}
        {v.stats.map((m) => (
          <StatLine key={m.label} label={m.label} value={m.value} refValue={m.ref} pct={m.pct} asOf={m.asOf} />
        ))}
      </div>

      {v.since && (
        <div className="mt-2 text-[0.65rem] text-slate-500">
          In this regime since {v.since}
        </div>
      )}
    </div>
  );
}
