"use client";

import { useState } from "react";
import { HudGroup } from "@/lib/types";
import { isPriceGroup, isStale, num, stretchZ } from "@/lib/tapeMath";
import { asOfLabel } from "./format";

const SCALE = 3; // bars run ±3 standard deviations

export function TapeStretch({
  groups,
  order,
  latest,
  onSelect,
}: {
  groups: HudGroup[];
  order: string[];
  latest: string;
  onSelect: (symbol: string) => void;
}) {
  const usable = order.map((n) => groups.find((g) => g.name === n)).filter((g): g is HudGroup => !!g && isPriceGroup(g) && g.tickers.length > 0);
  const [name, setName] = useState<string>(usable[0]?.name ?? "");
  const g = usable.find((x) => x.name === name) ?? usable[0];
  const rows = (g?.tickers ?? [])
    .map((t) => ({ t, z: stretchZ(t) }))
    .sort((a, b) => (num(b.z) ? b.z : -99) - (num(a.z) ? a.z : -99));

  return (
    <section aria-label="Stretch">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <label className="text-[0.65rem] uppercase tracking-wide text-slate-500" htmlFor="stretch-group">Group</label>
        <select
          id="stretch-group"
          value={g?.name ?? ""}
          onChange={(e) => setName(e.target.value)}
          className="rounded border border-[var(--cgi-rule)] bg-[var(--cgi-surface)] px-2 py-1 text-[0.72rem] text-slate-200"
        >
          {usable.map((x) => (<option key={x.name} value={x.name}>{x.name}</option>))}
        </select>
        <span className="text-[0.62rem] text-slate-500">price minus its 7-day average, in 7-day standard deviations; marks at ±2</span>
      </div>
      <div className="max-w-3xl text-[0.76rem]">
        {rows.map(({ t, z }) => {
          const stale = isStale(t, latest);
          const w = num(z) ? Math.min(Math.abs(z), SCALE) / SCALE * 50 : 0;
          return (
            <button key={t.symbol} type="button" onClick={() => onSelect(t.symbol)} className="flex w-full items-center gap-2 px-1 py-0.5 text-left hover:bg-slate-800/50" style={{ opacity: stale ? 0.5 : 1 }}>
              <span className="w-16 shrink-0 font-medium text-slate-200">{t.symbol}</span>
              <span className="relative h-3 flex-1 bg-[var(--cgi-surface-alt)]" aria-hidden>
                <span className="absolute inset-y-0 left-1/2 w-px bg-[var(--cgi-null)]" />
                <span className="absolute inset-y-0 w-px bg-[var(--cgi-rule)]" style={{ left: `${50 - (2 / SCALE) * 50}%` }} />
                <span className="absolute inset-y-0 w-px bg-[var(--cgi-rule)]" style={{ left: `${50 + (2 / SCALE) * 50}%` }} />
                {num(z) && (
                  <span
                    className="absolute inset-y-0"
                    style={{ left: z >= 0 ? "50%" : `${50 - w}%`, width: `${w}%`, background: z >= 0 ? "var(--cgi-up)" : "var(--cgi-down)" }}
                  />
                )}
              </span>
              <span className="w-12 shrink-0 text-right text-slate-300">{num(z) ? `${z >= 0 ? "+" : ""}${z.toFixed(1)}` : "—"}</span>
              {stale && t.as_of && <span className="w-16 shrink-0 text-[0.58rem] text-[var(--cgi-gold)]">as of {asOfLabel(t.as_of)}</span>}
            </button>
          );
        })}
      </div>
      <p className="mt-2 max-w-3xl text-[0.62rem] text-slate-500">
        Descriptive only. Daily peer overshoot reversion measured about 0.1% per event after costs and was decaying, so a stretched row is not an entry or a fade signal.
      </p>
    </section>
  );
}
