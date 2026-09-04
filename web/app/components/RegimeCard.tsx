import { RegimeBlock } from "@/lib/types";
import {
  COMPASS_Q_MAP,
  GRID_Q_MAP,
  compassLabel,
  gridLabel,
  dirColor,
} from "@/lib/regimeConstants";

const REGIME_GOLD = "#FCD34D";

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
  pct: number | null;
  asOf?: string | null;
}) {
  if (value === null || value === undefined) {
    return (
      <div className="mb-[3px]">
        <span className="text-slate-400">{label}&nbsp;</span>—
      </div>
    );
  }
  const pctStr = pct === null || pct === undefined ? "—" : `${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%`;
  return (
    <div className="mb-[3px]">
      <span className="text-slate-400">{label}&nbsp;</span>
      <b>{value}</b>{" "}
      {refValue !== undefined && refValue !== null && (
        <span className="text-[0.7rem] text-slate-500">
          (was {refValue}, {pctStr})
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
  const isCompass = kind === "compass";
  const qMap = isCompass ? COMPASS_Q_MAP : GRID_Q_MAP;
  const [arr1, arr2] = data.quadrant ? qMap[data.quadrant] ?? ["?", "?"] : ["?", "?"];

  const title = isCompass ? "COMPASS — Liquidity / Credit" : "GRID — Growth / Inflation";
  const axis1Label = isCompass ? "LIQUIDITY" : "GROWTH";
  const axis2Label = isCompass ? "CREDIT" : "INFLATION";
  const axis1Word = isCompass ? (arr1 === "↑" ? "Easing" : "Tightening") : (arr1 === "↑" ? "Rising" : "Falling");
  const axis2Word = isCompass ? (arr2 === "↑" ? "Easing" : "Tightening") : (arr2 === "↑" ? "Rising" : "Falling");
  const axis1Color = isCompass ? dirColor(arr1, "liquidity") : dirColor(arr1, "growth");
  const axis2Color = isCompass ? dirColor(arr2, "credit") : dirColor(arr2, "inflation");

  const metricEntries = Object.entries(data.metrics);
  const label = (k: string) => (isCompass ? compassLabel(k) : gridLabel(k));

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <div className="mb-1.5 text-[0.62rem] uppercase tracking-[2px] text-slate-400">
        {title}
      </div>
      <div className="mb-2.5 text-[1.05rem] font-bold" style={{ color: REGIME_GOLD }}>
        {data.label}
      </div>

      {data.stale_note && (
        <div className="mb-2.5 rounded border border-amber-700 bg-amber-950/50 px-2 py-1 text-xs text-amber-400">
          {data.stale_note}
        </div>
      )}

      <div className="mb-2.5 flex items-baseline gap-5">
        <div>
          <div className="text-[0.68rem] text-slate-500">{axis1Label}</div>
          <div className="text-[1.6rem] font-bold leading-tight" style={{ color: axis1Color }}>
            {arr1} {axis1Word}
          </div>
        </div>
        <div className="w-px self-stretch bg-slate-700" />
        <div>
          <div className="text-[0.68rem] text-slate-500">{axis2Label}</div>
          <div className="text-[1.6rem] font-bold leading-tight" style={{ color: axis2Color }}>
            {arr2} {axis2Word}
          </div>
        </div>
      </div>

      <div className="border-t border-slate-800 pt-2 text-[0.78rem] text-slate-200">
        {metricEntries.length === 0 && <div className="text-slate-500">No metrics available</div>}
        {metricEntries.map(([key, m]) => (
          <StatLine
            key={key}
            label={label(key)}
            value={m.current_value}
            refValue={"reference_value" in m ? m.reference_value : m.previous_value}
            pct={m.pct_change}
            asOf={m.current_date ?? m.release_date}
          />
        ))}
      </div>

      {data.since && (
        <div className="mt-2 text-[0.65rem] text-slate-500">
          In this regime since {data.since}
        </div>
      )}
    </div>
  );
}
