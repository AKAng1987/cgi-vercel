"use client";

import { HORIZONS, HKey } from "@/lib/tapeMath";

export type TapeView = "table" | "heatmap" | "rotation" | "stretch";

export const VIEWS: { key: TapeView; label: string }[] = [
  { key: "table", label: "Table" },
  { key: "heatmap", label: "Heatmap" },
  { key: "rotation", label: "Rotation" },
  { key: "stretch", label: "Stretch" },
];

const btn = (on: boolean) =>
  `rounded border px-2.5 py-1 text-[0.7rem] font-semibold uppercase tracking-wide ${
    on
      ? "border-[var(--cgi-accent)] bg-[var(--cgi-surface)] text-[color:var(--cgi-accent)]"
      : "border-[var(--cgi-rule)] text-slate-400 hover:text-slate-200"
  }`;

export function TapeControls({
  view,
  horizon,
  onView,
  onHorizon,
}: {
  view: TapeView;
  horizon: HKey;
  onView: (v: TapeView) => void;
  onHorizon: (h: HKey) => void;
}) {
  const showHorizon = view === "table" || view === "heatmap";
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="Tape view">
      <div className="flex gap-1">
        {VIEWS.map((v) => (
          <button key={v.key} type="button" onClick={() => onView(v.key)} className={btn(view === v.key)} aria-pressed={view === v.key}>
            {v.label}
          </button>
        ))}
      </div>
      {showHorizon && (
        <div className="flex gap-1" aria-label="Horizon">
          <span className="self-center pr-1 text-[0.65rem] uppercase tracking-wide text-slate-500">Move over</span>
          {HORIZONS.map((h) => (
            <button key={h.key} type="button" onClick={() => onHorizon(h.key)} className={btn(horizon === h.key)} aria-pressed={horizon === h.key}>
              {h.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
