"use client";

import { Fragment, useState } from "react";
import { SignalRow, SignalAxis, SignalOutcome, SignalDivergenceAxis } from "@/lib/types";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

const TH = "bg-[#1F2937] px-1.5 py-1 text-[0.68rem] uppercase tracking-wide text-slate-400";
const TD = "px-1.5 py-1 align-top";

function qLabel(axis: "compass" | "grid", q: number | null): string {
  if (q === null) return "—";
  return axis === "compass" ? `C${q}` : `G${q}`;
}
function qTitle(axis: "compass" | "grid", q: number | null): string {
  if (q === null) return "";
  return axis === "compass" ? COMPASS_Q_LABELS[q] : GRID_Q_LABELS[q];
}
function fmtP(v: number | null): string {
  return v === null ? "—" : v.toFixed(2);
}

function AxisCell({ axis, a }: { axis: "compass" | "grid"; a: SignalAxis }) {
  return (
    <div className="text-[0.76rem]">
      <span className="font-bold text-slate-100" title={qTitle(axis, a.current)}>
        {qLabel(axis, a.current)}
      </span>
      <span className="ml-2 text-slate-500">→</span>
      {a.next_top3.map((t, i) => (
        <span key={t.quadrant} className={`ml-1.5 ${i === 0 ? "text-slate-200" : "text-slate-500"}`} title={qTitle(axis, t.quadrant)}>
          {qLabel(axis, t.quadrant)}
          <span className="ml-0.5 text-[0.65rem]">{Math.round(t.probability * 100)}%</span>
        </span>
      ))}
      <div className="text-[0.65rem] text-slate-600">H {fmtP(a.transition_entropy)} bits</div>
    </div>
  );
}

function OutcomeCell({ axis, o, signalQ }: { axis: "compass" | "grid"; o: SignalOutcome | null; signalQ: number | null }) {
  if (!o) return <span className="text-slate-700">pending</span>;
  const x = o.axes[axis];
  if (!x.changed) {
    return (
      <span className="text-slate-500" title={`still ${qLabel(axis, signalQ)} on ${o.check_date}`}>
        same
      </span>
    );
  }
  return (
    <span
      className={x.top3_hit ? "font-bold text-[#00C851]" : "font-bold text-[#FF4444]"}
      title={`${qLabel(axis, signalQ)} → ${qLabel(axis, x.actual)} on ${o.check_date}`}
    >
      {x.top3_hit ? "HIT" : "MISS"} <span className="font-normal text-slate-400">→{qLabel(axis, x.actual)}</span>
    </span>
  );
}

function DivCell({ d, label }: { d: SignalDivergenceAxis | undefined; label: string }) {
  if (!d) return <span className="text-slate-700">—</span>;
  const p = d.p_up ?? 0;
  const dir = d.direction;
  return (
    <div className="text-[0.72rem]" title={`P(${label} up)=${p.toFixed(3)} vs print ${d.discrete_up ? "up" : "down"} (Q${d.discrete_quadrant})`}>
      <span className={dir ? "font-bold text-[#FCD34D]" : "text-slate-300"}>
        {dir ? (dir === "market_up" ? "mkt↑" : "mkt↓") : "agree"}
      </span>
      <span className="ml-1.5 text-slate-500">{fmtP(d.divergence_score)}</span>
    </div>
  );
}

export function SignalsTable({ signals }: { signals: SignalRow[] }) {
  const [showAll, setShowAll] = useState(false);
  const rows = showAll ? signals : signals.slice(0, 60);

  return (
    <div className="overflow-x-auto rounded border border-slate-800">
      <table className="w-full border-collapse text-[0.76rem]">
        <thead>
          <tr>
            <th className={`${TH} text-left`}>Date</th>
            <th className={`${TH} text-right`}>SPX</th>
            <th className={`${TH} text-left`}>Compass · next</th>
            <th className={`${TH} text-left`}>Grid · next</th>
            <th className={`${TH} text-left`} colSpan={2}>1w outcome (C / G)</th>
            <th className={`${TH} text-left`} colSpan={2}>1m outcome (C / G)</th>
            <th className={`${TH} text-left`} colSpan={2}>3m outcome (C / G)</th>
            <th className={`${TH} text-left`}>Credit div.</th>
            <th className={`${TH} text-left`}>Inflation div.</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.signal_id} className="border-t border-slate-800/60 hover:bg-slate-800/40">
              <td className={`${TD} whitespace-nowrap font-medium text-slate-200`} title={s.timestamp_utc ?? ""}>
                {s.signal_date}
              </td>
              <td className={`${TD} text-right text-slate-400`}>
                {s.spx_close_at_signal === null ? "—" : s.spx_close_at_signal.toFixed(0)}
              </td>
              <td className={TD}><AxisCell axis="compass" a={s.compass} /></td>
              <td className={TD}><AxisCell axis="grid" a={s.grid} /></td>
              {(["1w", "1m", "3m"] as const).map((h) => (
                <Fragment key={h}>
                  <td className={TD}><OutcomeCell axis="compass" o={s.outcomes[h]} signalQ={s.compass.current} /></td>
                  <td className={TD}><OutcomeCell axis="grid" o={s.outcomes[h]} signalQ={s.grid.current} /></td>
                </Fragment>
              ))}
              <td className={TD}><DivCell d={s.divergence?.axes.credit} label="credit" /></td>
              <td className={TD}><DivCell d={s.divergence?.axes.inflation} label="inflation" /></td>
            </tr>
          ))}
        </tbody>
      </table>
      {signals.length > 60 && !showAll && (
        <button
          onClick={() => setShowAll(true)}
          className="w-full border-t border-slate-800 py-2 text-xs text-slate-400 hover:bg-slate-800/40"
        >
          Show all {signals.length} signals
        </button>
      )}
    </div>
  );
}
