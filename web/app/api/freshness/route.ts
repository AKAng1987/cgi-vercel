import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for /api/freshness, for the scheduled refresh routine.
 *
 * The routine runs on the user's own machine, and some networks it sits on (the
 * office network, the home network) sinkhole *.onrender.com -- DNS answers with a
 * private 192.168.x address -- while vercel.app stays reachable. On 2026-10-05 the
 * routine's first weekday run failed with "Network is unreachable" for exactly this
 * reason and wrote no heartbeat. Everything the routine calls must therefore be
 * reachable through here: this, /api/freshness/heartbeat, /api/series/<symbol>
 * and /api/watchlists.
 *
 * Read-only and unauthenticated, like the upstream endpoint: it exposes dates
 * already visible on the pages. The server holds the token.
 */
export const revalidate = 0;
// The upstream payload is cached, but a cold Render instance plus a rebuild can take
// a while; the routine retries once, so give the first call room.
export const maxDuration = 60;

export async function GET() {
  try {
    const data = await apiFetch<unknown>("/api/freshness");
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
