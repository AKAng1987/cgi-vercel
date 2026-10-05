import { ImageResponse } from "next/og";
import { apiFetch } from "@/lib/api";
import { LiveResponse } from "@/lib/types";
import { regimeView, RegimeView } from "@/lib/regimeView";

/**
 * The regime card as a PNG, for the post to the CTS Ideas feed (api: cgi-cts-poster). CTS's server fetches this URL
 * and re-hosts the picture, so it must be public, answer inside ~20s, and not need a browser.
 *
 * It draws from the SAME view model as the card on the page (lib/regimeView.ts), so the words, arrows and readings
 * cannot drift. The image renderer cannot read CSS variables, so the light-theme values from globals.css are written
 * out below; when a token there changes, change it here. The renderer ships one regular-weight font, so "bold" is a
 * zero-blur text shadow rather than a font file.
 */
export const revalidate = 0;
export const maxDuration = 30;

// globals.css, light theme. slate ramp converted from oklch.
const C = {
  page: "#fdfdfe", card: "#e2e7eb", border: "#b3bfcd", rule: "#c3ccd8",
  strong: "#0f172b", body: "#1d293d", muted: "#45556c", faint: "#62748e",
  gold: "#8a6510", up: "#0a8f3c", down: "#c62828", warn: "#a85400",
};
const VARS: Record<string, string> = {
  "var(--cgi-up)": C.up, "var(--cgi-down)": C.down, "var(--cgi-warn)": C.warn, "var(--cgi-gold)": C.gold,
};
const hex = (c: string) => VARS[c] ?? C.body;
const bold = (color: string, px = 1.2) => ({ color, textShadow: `${px}px 0 0 ${color}, 0 ${px / 2}px 0 ${color}` });

function Card({ v }: { v: RegimeView }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, background: C.card,
      border: `1px solid ${C.border}`, borderRadius: 14, padding: "26px 30px" }}>
      <div style={{ display: "flex", fontSize: 15, letterSpacing: 3, color: C.muted, marginBottom: 8 }}>
        {v.title.toUpperCase()}
      </div>
      <div style={{ display: "flex", fontSize: 31, marginBottom: 18, ...bold(C.gold, 1.5) }}>{v.regimeLabel}</div>

      <div style={{ display: "flex", flexDirection: "row", marginBottom: 18 }}>
        {v.axes.map((ax, i) => (
          <div key={ax.label} style={{ display: "flex", flexDirection: "column",
            ...(i === 1 ? { marginLeft: 30, paddingLeft: 30, borderLeft: `1px solid ${C.rule}` } : {}) }}>
            <div style={{ display: "flex", fontSize: 16, color: C.faint, marginBottom: 2 }}>{ax.label}</div>
            <div style={{ display: "flex", fontSize: 42, lineHeight: 1.1, ...bold(hex(ax.color), 2) }}>{`${ax.arrow} ${ax.word}`}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", flexDirection: "column", borderTop: `1px solid ${C.rule}`, paddingTop: 12 }}>
        {v.stats.map((m) => (
          <div key={m.label} style={{ display: "flex", flexDirection: "row", alignItems: "baseline", marginBottom: 6, fontSize: 21 }}>
            <div style={{ display: "flex", color: C.muted, marginRight: 8 }}>{m.label}</div>
            <div style={{ display: "flex", marginRight: 8, ...bold(C.strong) }}>{String(m.value ?? "—")}</div>
            {m.ref !== null && m.ref !== undefined && (
              <div style={{ display: "flex", fontSize: 16, color: C.faint, marginRight: 8 }}>{`(was ${m.ref}, ${m.pct})`}</div>
            )}
            {m.asOf && <div style={{ display: "flex", fontSize: 16, color: C.faint }}>{`as of ${m.asOf}`}</div>}
          </div>
        ))}
      </div>
      {v.since && (
        <div style={{ display: "flex", fontSize: 16, color: C.faint, marginTop: 8 }}>{`In this regime since ${v.since}`}</div>
      )}
    </div>
  );
}

export async function GET() {
  let live: LiveResponse;
  try {
    live = await apiFetch<LiveResponse>("/api/live");
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 502 });
  }
  const code = `C${live.compass.quadrant ?? "?"}G${live.grid.quadrant ?? "?"}`;
  return new ImageResponse(
    (
      <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%", background: C.page, padding: 32 }}>
        <div style={{ display: "flex", flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", marginBottom: 20 }}>
          <div style={{ display: "flex", fontSize: 44, ...bold(C.strong, 2) }}>LIVE</div>
          <div style={{ display: "flex", fontSize: 18, color: C.muted }}>
            {`regime ${code} · ${live.compass.label} × ${live.grid.label} · as of ${live.as_of}`}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "row", gap: 24 }}>
          <Card v={regimeView("compass", live.compass)} />
          <Card v={regimeView("grid", live.grid)} />
        </div>
      </div>
    ),
    { width: 1200, height: 490, headers: { "Cache-Control": "public, max-age=300, s-maxage=300" } },
  );
}
