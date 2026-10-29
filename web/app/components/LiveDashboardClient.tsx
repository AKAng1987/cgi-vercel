"use client";

import { useEffect, useState } from "react";
import { LiveResponse } from "@/lib/types";
import { HORIZONS, HKey, commonClose, newestClose } from "@/lib/tapeMath";
import { HudTable } from "./HudTable";
import { TradingViewChart } from "./TradingViewChart";
import { TapeControls, TapeView, VIEWS } from "./tape/TapeControls";
import { TapeHeatmap } from "./tape/TapeHeatmap";
import { TapeMovers } from "./tape/TapeMovers";
import { TapeRotation } from "./tape/TapeRotation";
import { TapeStretch } from "./tape/TapeStretch";

export function LiveDashboardClient({ data }: { data: LiveResponse }) {
  // The newest close any row has. A row older than this is shown with its own date, so a source that has
  // fallen behind cannot pass for today's number (2026-10: RUT sat on Oct 2 beside Oct 6 rows).
  const latest = newestClose(data.hud_groups);
  // The views below measure "stale" against the date most rows share, so a feed that publishes a day early does not make the rest look stale.
  const common = commonClose(data.hud_groups);
  const [selectedSymbol, setSelectedSymbol] = useState(
    data.hud_groups[0]?.tickers[0]?.symbol ?? "SPX"
  );
  const [view, setView] = useState<TapeView>("table");
  const [horizon, setHorizon] = useState<HKey>("pct_1m");

  // The view and horizon live in the URL (?view=heatmap&h=3m) so a link reopens the same screen.
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const v = p.get("view");
    const h = (p.get("h") ?? "").toLowerCase();
    if (v && VIEWS.some((x) => x.key === v)) setView(v as TapeView);
    const hk = HORIZONS.find((x) => x.label.toLowerCase() === h);
    if (hk) setHorizon(hk.key);
  }, []);

  function remember(v: TapeView, h: HKey) {
    try {
      const p = new URLSearchParams(window.location.search);
      p.set("view", v);
      p.set("h", (HORIZONS.find((x) => x.key === h)?.label ?? "1M").toLowerCase());
      window.history.replaceState(null, "", `?${p.toString()}`);
    } catch {
      /* a URL we cannot edit is not worth failing the page over */
    }
  }

  function select(symbol: string) {
    setSelectedSymbol(symbol);
    // The chart sits under the views; bring it into sight when a tile, dot or mover is chosen.
    if (view !== "table") {
      requestAnimationFrame(() => document.getElementById("tape-chart")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  }

  const groupsByName = new Map(data.hud_groups.map((g) => [g.name, g]));

  return (
    <>
      <TapeControls
        view={view}
        horizon={horizon}
        onView={(v) => { setView(v); remember(v, horizon); }}
        onHorizon={(h) => { setHorizon(h); remember(view, h); }}
      />
      {(view === "table" || view === "heatmap") && (
        <TapeMovers groups={data.hud_groups} latest={common} horizon={horizon} onSelect={select} />
      )}
      {view === "table" &&
        data.hud_group_order.map((name) => {
          const group = groupsByName.get(name);
          if (!group) return null;
          return <HudTable key={name} group={group} latest={latest} onSelectSymbol={select} />;
        })}
      {view === "heatmap" && (
        <TapeHeatmap groups={data.hud_groups} order={data.hud_group_order} latest={common} horizon={horizon} onSelect={select} />
      )}
      {view === "rotation" && <TapeRotation groups={data.hud_groups} latest={common} onSelect={select} />}
      {view === "stretch" && (
        <TapeStretch groups={data.hud_groups} order={data.hud_group_order} latest={common} onSelect={select} />
      )}
      <div id="tape-chart">
        <TradingViewChart symbol={selectedSymbol} />
      </div>
    </>
  );
}
