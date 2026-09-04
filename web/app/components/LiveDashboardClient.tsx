"use client";

import { useState } from "react";
import { LiveResponse } from "@/lib/types";
import { HudTable } from "./HudTable";
import { TradingViewChart } from "./TradingViewChart";

export function LiveDashboardClient({ data }: { data: LiveResponse }) {
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
          <HudTable key={name} group={group} onSelectSymbol={setSelectedSymbol} />
        );
      })}
      <TradingViewChart symbol={selectedSymbol} />
    </>
  );
}
