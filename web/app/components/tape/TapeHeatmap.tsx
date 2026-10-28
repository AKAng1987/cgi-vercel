"use client";

import { HudGroup, HudTicker } from "@/lib/types";
import { HKey, HORIZONS, isPriceGroup, isStale, tileColor } from "@/lib/tapeMath";
import { fmtPct, asOfLabel } from "./format";

function tip(t: HudTicker): string {
  const parts = HORIZONS.map((h) => `${h.label} ${fmtPct(t[h.key])}`);
  return `${t.symbol}: ${parts.join(" · ")}${t.as_of ? ` (close ${t.as_of})` : ""}`;
}

export function TapeHeatmap({
  groups,
  order,
  latest,
  horizon,
  onSelect,
}: {
  groups: HudGroup[];
  order: string[];
  latest: string;
  horizon: HKey;
  onSelect: (symbol: string) => void;
}) {
  const byName = new Map(groups.map((g) => [g.name, g]));
  const label = HORIZONS.find((h) => h.key === horizon)?.label ?? "";
  return (
    <div>
      <p className="mb-1 text-[0.65rem] text-slate-500">
        Colour is the move over {label}; a tile is full colour at ±{HORIZONS.find((h) => h.key === horizon)?.cap}%. Dimmed tiles carry an older close.
      </p>
      {order.map((name) => {
        const g = byName.get(name);
        if (!g || g.tickers.length === 0) return null;
        return (
          <div key={name} className="mt-3.5">
            <div className="mb-1 border-l-[3px] border-l-[var(--cgi-accent-dim)] bg-[var(--cgi-surface-head)] px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
              {g.name}
              {!isPriceGroup(g) && (
                <span className="ml-2 text-[0.6rem] font-normal normal-case tracking-normal text-[var(--cgi-muted-blue)]">
                  % change of the level, not a price return
                </span>
              )}
            </div>
            <div className="grid grid-cols-3 gap-1 sm:grid-cols-5 md:grid-cols-7 lg:grid-cols-9">
              {g.tickers.map((t) => {
                const stale = isStale(t, latest);
                return (
                  <button
                    key={t.symbol}
                    type="button"
                    title={tip(t)}
                    onClick={() => onSelect(t.symbol)}
                    className="relative rounded px-1 py-1.5 text-center hover:ring-1 hover:ring-[var(--cgi-accent)]"
                    style={{ background: tileColor(t[horizon], horizon), opacity: stale ? 0.5 : 1 }}
                  >
                    <div className="truncate text-[0.72rem] font-semibold text-slate-100">{t.symbol}</div>
                    <div className="text-[0.68rem] text-slate-200">{fmtPct(t[horizon], 1)}</div>
                    {stale && t.as_of && (
                      <div className="text-[0.55rem] text-[var(--cgi-gold)]">as of {asOfLabel(t.as_of)}</div>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
