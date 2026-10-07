"use client";

import { HudGroup } from "@/lib/types";
import { HUD_DISPLAY_COLUMNS, pctColor } from "@/lib/regimeConstants";

function fmtPrice(v: number | null): string {
  if (v === null || v === undefined) return "—";
  // Streamlit's "{:.4g}" -- 4 significant figures
  return Number(v.toPrecision(4)).toString();
}

function fmtPct(v: number | null): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function asOfLabel(d: string): string {
  return `${MONTHS[Number(d.slice(5, 7)) - 1]} ${Number(d.slice(8, 10))}`;
}

export function HudTable({
  group,
  latest,
  onSelectSymbol,
}: {
  group: HudGroup;
  latest?: string;
  onSelectSymbol: (symbol: string) => void;
}) {
  // Streamlit's render_hud_group returns early (renders nothing -- no
  // header, no table) when the group's dataframe is empty (app.py:631-632).
  if (!group.tickers || group.tickers.length === 0) {
    return null;
  }

  const denomLabel = group.default_rs_denom ? `RS vs ${group.default_rs_denom}` : "no RS";

  return (
    <div className="mt-3.5">
      <div className="mb-1 border-l-[3px] border-l-[var(--cgi-accent-dim)] bg-[var(--cgi-surface-head)] px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
        {group.name}
        <span className="ml-2 text-[0.6rem] font-normal tracking-wide text-[var(--cgi-muted-blue)]">
          {denomLabel}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[0.76rem]">
          <thead>
            <tr>
              <th className="bg-[var(--cgi-surface)] px-1.5 py-1 text-left text-[0.68rem] uppercase tracking-wide text-slate-400">
                Symbol
              </th>
              <th className="bg-[var(--cgi-surface)] px-1.5 py-1 text-right text-[0.68rem] uppercase tracking-wide text-slate-400">
                Price
              </th>
              {HUD_DISPLAY_COLUMNS.map((c) => (
                <th
                  key={c.key}
                  className="bg-[var(--cgi-surface)] px-1.5 py-1 text-right text-[0.68rem] uppercase tracking-wide text-slate-400"
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {group.tickers.map((t) => (
              <tr
                key={t.symbol}
                onClick={() => onSelectSymbol(t.symbol)}
                className="cursor-pointer hover:bg-slate-800/50"
              >
                <td className="px-1.5 py-0.5 font-medium text-slate-200">
                  {t.symbol}
                  {latest && t.as_of && t.as_of < latest && (
                    <span className="ml-1.5 text-[0.62rem] font-normal text-[var(--cgi-gold)]" title={`Newest close we hold for ${t.symbol}; other rows are at ${latest}`}>
                      as of {asOfLabel(t.as_of)}
                    </span>
                  )}
                </td>
                <td className="px-1.5 py-0.5 text-right text-slate-200">{fmtPrice(t.current)}</td>
                {HUD_DISPLAY_COLUMNS.map((c) => {
                  const v = t[c.key as keyof typeof t] as number | null;
                  return (
                    <td
                      key={c.key}
                      className="px-1.5 py-0.5 text-right font-medium"
                      style={{ color: pctColor(v) }}
                    >
                      {fmtPct(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
