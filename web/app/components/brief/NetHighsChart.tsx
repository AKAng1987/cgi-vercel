"use client";

import { useState } from "react";
import { TechnicalsResponse } from "@/lib/types";

const STATE: Record<string, string> = { green: "GREEN", red: "RED", white: "CHOP" };

function fmtDate(iso: string): string {
  return new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}

/**
 * Net new highs as bars (green above zero, red below) with the 8 and 20 day
 * EMAs over the top. Inline SVG -- no chart library. The read is the zero
 * line and the EMA cross, so those are what the drawing emphasises. Client
 * code is only the hover readout (date, net, both EMAs, state); pointer
 * events cover mouse and touch.
 */
export function NetHighsChart({ series }: { series: TechnicalsResponse["net_new_highs"]["series"] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (!series?.length) return null;

  const W = 880;
  const H = 150;
  const PAD = 4;
  const vals = series.flatMap((p) => [p.net, p.fast, p.slow]);
  const lo = Math.min(...vals);
  const hi = Math.max(...vals);
  const span = hi - lo || 1;
  const y = (v: number) => PAD + (hi - v) / span * (H - 2 * PAD);
  const x = (i: number) => (i / Math.max(1, series.length - 1)) * W;
  const barW = Math.max(1.2, W / series.length - 0.6);
  const zero = y(0);

  const path = (key: "fast" | "slow") =>
    series.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join("");

  const at = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    if (!r.width) return;
    const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
    setHover(Math.round(f * (series.length - 1)));
  };

  const h = hover === null ? null : series[hover];

  return (
    <div className="mt-3">
      <div className="mb-1 h-4 text-[0.68rem] tabular-nums text-slate-400" aria-live="polite">
        {h ? (
          <>
            <span className="font-semibold text-slate-200">{fmtDate(h.date)}</span>
            {"  ·  "}net <span className="text-slate-200">{h.net}</span>
            {"  ·  "}8ema <span className="text-blue-400">{h.fast}</span>
            {"  ·  "}20ema <span className="text-violet-400">{h.slow}</span>
            {"  ·  "}
            {STATE[h.colour] ?? "CHOP"}
          </>
        ) : (
          <span className="text-slate-600">hover for the date</span>
        )}
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        role="img"
        aria-label="net new highs"
        onPointerMove={at}
        onPointerDown={at}
        onPointerLeave={() => setHover(null)}
      >
        {/* background bands: green where three straight days of net highs,
            red where three straight days of net lows, white = chop */}
        {series.map((p, i) => (
          <rect
            key={`bg-${p.date}`}
            x={x(i) - barW / 2 - 0.3}
            y={0}
            width={barW + 0.6}
            height={H}
            fill={p.colour === "green" ? "#052e16" : p.colour === "red" ? "#340d0d" : "transparent"}
          />
        ))}
        <line x1={0} x2={W} y1={zero} y2={zero} stroke="#475569" strokeWidth={1} />
        {series.map((p, i) => {
          const top = p.net >= 0 ? y(p.net) : zero;
          const bh = Math.max(0.8, Math.abs(zero - y(p.net)));
          return (
            <rect
              key={p.date}
              x={x(i) - barW / 2}
              y={top}
              width={barW}
              height={bh}
              fill={p.net >= 0 ? "#15803d" : "#b91c1c"}
            />
          );
        })}
        <path d={path("slow")} fill="none" stroke="#7c3aed" strokeWidth={1.6} />
        <path d={path("fast")} fill="none" stroke="#3b82f6" strokeWidth={1.6} />
        {hover !== null && (
          <line
            x1={x(hover)}
            x2={x(hover)}
            y1={0}
            y2={H}
            className="stroke-slate-400"
            strokeWidth={1}
            strokeDasharray="3 3"
            pointerEvents="none"
          />
        )}
      </svg>
    </div>
  );
}
