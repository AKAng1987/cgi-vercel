"use client";

import { HudGroup } from "@/lib/types";
import { HKey, HORIZONS, isPriceGroup, isStale, num } from "@/lib/tapeMath";
import { pctColor } from "@/lib/regimeConstants";
import { fmtPct } from "./format";

type Row = { symbol: string; group: string; v: number; price: number | null };

// Same 4 significant figures the table uses for its Price column.
function fmtPrice(v: number | null): string {
  return num(v) ? Number(v.toPrecision(4)).toString() : "—";
}

export function TapeMovers({
  groups,
  latest,
  horizon,
  onSelect,
}: {
  groups: HudGroup[];
  latest: string;
  horizon: HKey;
  onSelect: (symbol: string) => void;
}) {
  const rows: Row[] = [];
  const seen = new Set<string>(); // a few symbols (KWEB, WOOD, SLX) sit in two groups; list each once
  let excluded = 0;
  for (const g of groups) {
    if (!isPriceGroup(g)) continue; // yields and spreads: a % change of a level is not a move in price
    for (const t of g.tickers) {
      const v = t[horizon];
      if (!num(v) || isStale(t, latest)) {
        excluded += 1;
        continue;
      }
      if (seen.has(t.symbol)) continue;
      seen.add(t.symbol);
      rows.push({ symbol: t.symbol, group: g.name, v, price: t.current });
    }
  }
  rows.sort((a, b) => b.v - a.v);
  const top = rows.slice(0, 10);
  const bottom = rows.slice(-10).reverse();
  const label = HORIZONS.find((h) => h.key === horizon)?.label ?? "";

  const col = (title: string, list: Row[]) => (
    <div className="min-w-0 flex-1">
      <div className="mb-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">{title}</div>
      <ul className="text-[0.76rem]">
        {list.map((r) => (
          <li key={r.symbol}>
            <button
              type="button"
              onClick={() => onSelect(r.symbol)}
              className="flex w-full items-baseline gap-2 px-1 py-0.5 text-left hover:bg-slate-800/50"
            >
              <span className="w-14 shrink-0 font-medium text-slate-200">{r.symbol}</span>
              <span className="w-16 shrink-0 text-right text-slate-300">{fmtPrice(r.price)}</span>
              <span className="w-16 shrink-0 text-right font-medium" style={{ color: pctColor(r.v) }}>
                {fmtPct(r.v)}
              </span>
              <span className="min-w-0 truncate text-[0.62rem] uppercase tracking-wide text-slate-500">{r.group}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <section className="mt-3.5 rounded border border-[var(--cgi-rule)] p-2.5" aria-label={`Biggest movers over ${label}`}>
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-[0.7rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Movers · {label}</h2>
        <span className="text-[0.62rem] text-slate-500">
          price groups only; closes as of {latest ? latest.slice(5) : "—"} or later; {excluded} row{excluded === 1 ? "" : "s"} left out (older close or no value)
        </span>
      </div>
      <div className="flex flex-col gap-3 md:flex-row">
        {col("Up most", top)}
        {col("Down most", bottom)}
      </div>
    </section>
  );
}
