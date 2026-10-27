import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for /api/country_calendar, for the scheduled refresh routine (see ../freshness/route.ts for why
 * everything the routine calls goes through Vercel).
 *
 * GET returns the stored release calendar the routine uses to decide which series are due. POST stores the week's
 * TradingView calendar rows. The upstream endpoint is unauthenticated and does all the validation; this forwards, with
 * a size cap so the proxy is not an open pipe for large bodies. The server holds the token.
 */
export const revalidate = 0;
export const maxDuration = 60;

const MAX_BYTES = 128 * 1024;

export async function GET() {
  try {
    return NextResponse.json(await apiFetch<unknown>("/api/country_calendar"));
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}

export async function POST(req: NextRequest) {
  const raw = await req.text();
  if (raw.length > MAX_BYTES) {
    return NextResponse.json({ error: "body too large" }, { status: 413 });
  }
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return NextResponse.json({ error: "body must be JSON" }, { status: 400 });
  }
  try {
    const data = await apiFetch<unknown>("/api/country_calendar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
