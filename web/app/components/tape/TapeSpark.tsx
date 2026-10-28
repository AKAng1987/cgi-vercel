"use client";

import { num } from "@/lib/tapeMath";

/** A line of the last ~60 closes, scaled to its own range. Draws nothing when there is no history: a gap stays a gap. */
export function TapeSpark({
  values,
  width = 64,
  height = 16,
  muted = false,
}: {
  values: number[] | null | undefined;
  width?: number;
  height?: number;
  muted?: boolean;
}) {
  const v = (values ?? []).filter(num);
  if (v.length < 2) return <span className="inline-block" style={{ width, height }} aria-hidden />;
  const lo = Math.min(...v), hi = Math.max(...v);
  const span = hi - lo || 1;
  const step = width / (v.length - 1);
  const pts = v.map((x, i) => `${(i * step).toFixed(1)},${(height - 1 - ((x - lo) / span) * (height - 2)).toFixed(1)}`).join(" ");
  const up = v[v.length - 1] >= v[0];
  return (
    <svg width={width} height={height} role="img" aria-label={`Last ${v.length} closes, ${up ? "up" : "down"} over the period`}>
      <polyline
        points={pts}
        fill="none"
        stroke={muted ? "var(--cgi-neutral)" : up ? "var(--cgi-up)" : "var(--cgi-down)"}
        strokeWidth={1.2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
