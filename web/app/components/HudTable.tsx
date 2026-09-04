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

export function HudTable({
  group,
  onSelectSymbol,
}: {
  group: HudGroup;
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
      <div className="mb-1 border-l-[3px] border-l-[#3b4f8a] bg-[#1a1f35] px-2.5 py-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
        {group.name}
        <span className="ml-2 text-[0.6rem] font-normal tracking-wide text-[#5b7fa6]">
          {denomLabel}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[0.76rem]">
          <thead>
            <tr>
              <th className="bg-[#1F2937] px-1.5 py-1 text-left text-[0.68rem] uppercase tracking-wide text-slate-400">
                Symbol
              </th>
              <th className="bg-[#1F2937] px-1.5 py-1 text-right text-[0.68rem] uppercase tracking-wide text-slate-400">
                Price
              </th>
              {HUD_DISPLAY_COLUMNS.map((c) => (
                <th
                  key={c.key}
                  className="bg-[#1F2937] px-1.5 py-1 text-right text-[0.68rem] uppercase tracking-wide text-slate-400"
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
                <td className="px-1.5 py-0.5 font-medium text-slate-200">{t.symbol}</td>
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
