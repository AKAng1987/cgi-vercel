"use client";

import { ReactNode, useState } from "react";

/** S&P 500 | Nasdaq switch for the drawdown card. Both panels are rendered on the server and passed in, so this only toggles which one shows. */
export function DrawdownTabs({ spx, nasdaq }: { spx: ReactNode; nasdaq: ReactNode | null }) {
  const [tab, setTab] = useState<"spx" | "nasdaq">("spx");
  if (!nasdaq) return <>{spx}</>;
  const btn = (k: "spx" | "nasdaq", label: string) => (
    <button
      type="button"
      onClick={() => setTab(k)}
      aria-pressed={tab === k}
      className={`rounded px-2 py-0.5 text-[0.7rem] font-medium ${tab === k ? "bg-slate-700 text-slate-100" : "text-slate-400 hover:bg-slate-800"}`}
    >
      {label}
    </button>
  );
  return (
    <div>
      <div className="mb-2 flex gap-1">{btn("spx", "S&P 500")}{btn("nasdaq", "Nasdaq")}</div>
      {tab === "spx" ? spx : nasdaq}
    </div>
  );
}
