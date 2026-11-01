"use client";

import { createContext, useCallback, useContext, useMemo, useState } from "react";

type Ctx = { selected: string; list: string[]; select: (s: string, list?: string[]) => void };
const SelectCtx = createContext<Ctx>({ selected: "PSEI", list: [], select: () => {} });

/** The ticker under review. Any ticker on the page sets it (with the list it was clicked from, so the dock can step through that list). */
export function PhSelectProvider({ children }: { children: React.ReactNode }) {
  const [selected, setSelected] = useState("PSEI");
  const [list, setList] = useState<string[]>([]);
  const select = useCallback((s: string, l?: string[]) => {
    setSelected(s);
    if (l && l.length) setList(l);
    requestAnimationFrame(() => document.getElementById("ph-dock")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }, []);
  const v = useMemo(() => ({ selected, list, select }), [selected, list, select]);
  return <SelectCtx.Provider value={v}>{children}</SelectCtx.Provider>;
}

export const usePhSelect = () => useContext(SelectCtx);

/** A ticker that opens in the chart dock at the bottom of the page. */
export function PhTicker({ s, list, className, children }: { s: string; list?: string[]; className?: string; children?: React.ReactNode }) {
  const { select } = usePhSelect();
  return (
    <button type="button" onClick={(e) => { e.stopPropagation(); select(s, list); }} className={className ?? "font-semibold text-slate-100 hover:underline"} title="review the chart at the bottom of the page">
      {children ?? s}
    </button>
  );
}
