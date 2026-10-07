"use client";

import { useState } from "react";
import { LiveResponse } from "@/lib/types";
import { HudTable } from "./HudTable";
import { TradingViewChart } from "./TradingViewChart";

export function LiveDashboardClient({ data }: { data: LiveResponse }) {
  // The newest close any row has. A row older than this is shown with its own date, so a source that has
  // fallen behind cannot pass for today's number (2026-10: RUT sat on Oct 2 beside Oct 6 rows).
  const latest = data.hud_groups.flatMap((g) => g.tickers.map((t) => t.as_of ?? "")).reduce((a, b) => (b > a ? b : a), "");
  const [selectedSymbol, setSelectedSymbol] = useState(
    data.hud_groups[0]?.tickers[0]?.symbol ?? "SPX"
  );

  const groupsByName = new Map(data.hud_groups.map((g) => [g.name, g]));

  return (
    <>
      {data.hud_group_order.map((name) => {
        const group = groupsByName.get(name);
        if (!group) return null;
        return (
          <HudTable key={name} group={group} latest={latest} onSelectSymbol={setSelectedSymbol} />
        );
      })}
      <TradingViewChart symbol={selectedSymbol} />
    </>
  );
}
