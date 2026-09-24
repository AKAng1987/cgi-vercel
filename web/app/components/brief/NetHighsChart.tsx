import { TechnicalsResponse } from "@/lib/types";

/**
 * Net new highs as bars (green above zero, red below) with the 8 and 20 day
 * EMAs over the top. Inline SVG -- no chart library, no client JS. The read
 * is the zero line and the EMA cross, so those are what the drawing
 * emphasises.
 */
export function NetHighsChart({ series }: { series: TechnicalsResponse["net_new_highs"]["series"] }) {
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

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-3 w-full" role="img" aria-label="net new highs">
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
        const h = Math.max(0.8, Math.abs(zero - y(p.net)));
        return (
          <rect
            key={p.date}
            x={x(i) - barW / 2}
            y={top}
            width={barW}
            height={h}
            fill={p.net >= 0 ? "#15803d" : "#b91c1c"}
          />
        );
      })}
      <path d={path("slow")} fill="none" stroke="#7c3aed" strokeWidth={1.6} />
      <path d={path("fast")} fill="none" stroke="#3b82f6" strokeWidth={1.6} />
    </svg>
  );
}
