"use client";

import { HudTicker } from "@/lib/types";
import { ladderState, num, paces } from "@/lib/tapeMath";

/** Six small bars, 1D to 1Y, each the move per trading day over that window, so a long window is not just a bigger bar. */
export function TapeLadder({ t, width = 54, height = 16 }: { t: HudTicker; width?: number; height?: number }) {
  const p = paces(t);
  const max = Math.max(...p.filter(num).map((x) => Math.abs(x)), 0);
  const state = ladderState(t);
  const bw = width / p.length;
  const mid = height / 2;
  return (
    <span className="inline-flex items-center gap-1.5" title={`Pace per trading day, 1D to 1Y: ${state}`}>
      <svg width={width} height={height} role="img" aria-label={`Pace ladder: ${state}`}>
        <line x1={0} x2={width} y1={mid} y2={mid} stroke="var(--cgi-rule)" strokeWidth={1} />
        {p.map((v, i) => {
          if (!num(v) || max === 0) return null;
          const h = (Math.abs(v) / max) * (mid - 1);
          return (
            <rect
              key={i}
              x={i * bw + 1}
              width={bw - 2}
              y={v >= 0 ? mid - h : mid}
              height={Math.max(h, 0.5)}
              fill={v >= 0 ? "var(--cgi-up)" : "var(--cgi-down)"}
            />
          );
        })}
      </svg>
      <span className="text-[0.62rem] text-slate-500">{state === "n/a" ? "" : state}</span>
    </span>
  );
}
