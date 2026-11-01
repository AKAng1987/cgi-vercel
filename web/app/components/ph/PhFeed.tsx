"use client";

import { useState } from "react";
import { PhDisclosure } from "@/lib/types";
import { PhTicker } from "./PhSelect";
import { CHIPS, dayLabel, edgeLink, num, peso, price } from "./phFormat";

const CHIP_TONE: Record<string, string> = {
  material: "text-amber-300", buyback: "text-emerald-300", insider: "text-sky-300", dividend: "text-violet-300", index: "text-amber-300", ownership: "text-sky-300",
  corporate: "text-red-300", meeting: "text-slate-400", people: "text-slate-400", press: "text-slate-400",
};

/** Material information, buy-backs, insider changes, dividends and corporate actions from PSE EDGE, newest first. Each row links to the filing. */
export function PhFeed({ rows, builtAt }: { rows: PhDisclosure[]; builtAt: string | null }) {
  const [chip, setChip] = useState("all");
  const [q, setQ] = useState("");
  const counts: Record<string, number> = {};
  for (const r of rows) counts[r.chip] = (counts[r.chip] ?? 0) + 1;
  const shown = rows.filter((r) => (chip === "all" || r.chip === chip) && (!q || r.symbol.toLowerCase().includes(q.toLowerCase()) || r.company.toLowerCase().includes(q.toLowerCase())));
  return (
    <section className="mb-4 rounded border border-slate-800 bg-slate-900/50 p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-3">
        <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">Material information · last 14 days</div>
        <div className="text-[0.68rem] text-slate-500">PSE EDGE disclosures · refreshed {builtAt ? builtAt.slice(0, 16).replace("T", " ") + " UTC" : "—"}</div>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="ticker or company" className="ml-auto w-40 rounded border border-slate-700 bg-slate-950 px-2 py-0.5 text-xs text-slate-200" />
      </div>
      <div className="mb-2 flex flex-wrap gap-1">
        {CHIPS.map((c) => (
          <button key={c.key} onClick={() => setChip(c.key)} className={`rounded px-2 py-0.5 text-xs ${chip === c.key ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:bg-slate-800"}`}>
            {c.label}{c.key === "all" ? ` ${rows.length}` : counts[c.key] ? ` ${counts[c.key]}` : ""}
          </button>
        ))}
      </div>
      <div className="max-h-[28rem] overflow-y-auto pr-1">
        <table className="w-full text-xs">
          <tbody>
            {shown.map((r) => (
              <tr key={r.edge_no} className="border-t border-slate-800/70 align-top">
                <td className="w-14 py-1 pr-2 tabular-nums text-slate-500">{dayLabel(r.announced)}</td>
                <td className="w-16 py-1 pr-2"><PhTicker s={r.symbol} list={Array.from(new Set(shown.map((x) => x.symbol)))}>{r.symbol}</PhTicker></td>
                <td className={`w-28 py-1 pr-2 ${CHIP_TONE[r.chip] ?? "text-slate-400"}`}>{CHIPS.find((c) => c.key === r.chip)?.label ?? r.chip}{r.amend ? ` (amend ${r.amend})` : ""}</td>
                <td className="py-1 pr-2 text-slate-300">
                  {r.subject ?? r.title}
                  {r.subject && r.chip !== "material" && <span className="ml-2 text-slate-600">{r.title}</span>}
                  {r.dividend && (
                    <span className="ml-2 text-violet-300">
                      ₱{r.dividend.per_share} a share{r.dividend.type ? ` (${r.dividend.type.toLowerCase()})` : ""}
                      {r.dividend.record ? ` · record ${dayLabel(r.dividend.record)}` : ""}{r.dividend.payment ? ` · paid ${dayLabel(r.dividend.payment)}` : ""}
                    </span>
                  )}
                  {r.insider && (
                    <span className={`ml-2 ${r.insider.side === "bought" ? "text-emerald-300" : r.insider.side === "sold" ? "text-red-300" : "text-slate-400"}`}>
                      {r.insider.name ?? "insider"}{r.insider.position ? ` (${r.insider.position})` : ""} {r.insider.side} {num(Math.abs(r.insider.net_shares))} sh · {peso(Math.abs(r.insider.net_value))}
                    </span>
                  )}
                  {r.buyback && <span className="ml-2 text-emerald-300">{num(r.buyback.shares)} sh @ {price(r.buyback.avg_price)} = {peso(r.buyback.value)}</span>}
                </td>
                <td className="w-12 py-1 text-right"><a className="text-slate-500 hover:text-slate-200" target="_blank" rel="noopener noreferrer" href={edgeLink(r.edge_no)}>EDGE ↗</a></td>
              </tr>
            ))}
            {shown.length === 0 && <tr><td className="py-3 text-slate-500">nothing in this filter yet</td></tr>}
          </tbody>
        </table>
      </div>
    </section>
  );
}
