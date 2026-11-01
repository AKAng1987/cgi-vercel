import { apiFetch } from "@/lib/api";
import { PhResponse } from "@/lib/types";
import { PhBreadthStrip } from "../components/brief/PhBreadthStrip";
import { PhEarnings } from "../components/ph/PhEarnings";
import { PhFeed } from "../components/ph/PhFeed";
import { PhHeader } from "../components/ph/PhHeader";
import { PhMacro } from "../components/ph/PhMacro";
import { PhMarket } from "../components/ph/PhMarket";
import { PhChartDock } from "../components/ph/PhChartDock";
import { PhRebalance } from "../components/ph/PhRebalance";
import { PhSelectProvider } from "../components/ph/PhSelect";
import { PhScanner } from "../components/ph/PhScanner";

// A cold API rebuild can take a while: give the page the full 60 s.
export const maxDuration = 60;

/**
 * PHILIPPINES. His home market in one place: BSP and the Philippine macro releases with a calendar, CGI's regime read for
 * the PSE and the peso, breadth, a leaderboard and segments over the liquid names, earnings and buy-backs and material
 * disclosures read from PSE EDGE, a PSEi rebalance screen, and a sortable scanner that exports a TradingView list.
 */
export default async function PhilippinesPage() {
  const d = await apiFetch<PhResponse>("/api/ph");
  const f = d.freshness;
  return (
    <PhSelectProvider>
    <main id="ph-top" className="mx-auto max-w-7xl p-6">
      <h1 className="mb-1 text-2xl font-bold">PHILIPPINES</h1>
      <p className="mb-4 text-xs leading-relaxed text-slate-400">
        Prices to {f.prices.asof ?? "—"} · PSE EDGE disclosures refreshed {f.edge.built_at ? f.edge.built_at.slice(0, 10) : "—"}. Descriptive: what traded, what was filed, what is scheduled. Not a signal.
      </p>
      {(f.prices.age_days ?? 0) > 4 && (
        <p className="mb-4 rounded border border-amber-800 bg-amber-950/40 p-2 text-xs text-amber-300">Prices are {f.prices.age_days} days old: the daily PH price build has not run.</p>
      )}
      <PhHeader d={d} />
      <PhMacro d={d} />
      <PhBreadthStrip data={d.breadth ?? undefined} />
      <PhMarket horizons={d.horizons} nLiquid={f.prices.n_liquid} asof={f.prices.asof} />
      <PhFeed rows={d.material} builtAt={f.edge.built_at} />
      <PhEarnings next={d.earnings.next} reported={d.earnings.reported} buybacks={d.buybacks} />
      <PhRebalance rb={d.rebalance} ix={d.index} />
      <PhScanner rows={d.scanner} />
      <PhChartDock />
      <p className="mt-2 text-[0.65rem] leading-relaxed text-slate-600">{d.caveats.join(" ")}</p>
    </main>
    </PhSelectProvider>
  );
}
