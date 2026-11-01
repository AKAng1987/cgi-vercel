import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for POST /api/ph/index_events: the announcement-day task posts the Philippine additions and deletions of an MSCI,
 * FTSE or WisdomTree review (see ../../country_calendar/route.ts for why everything the scheduled tasks call goes through Vercel).
 * The upstream endpoint is unauthenticated and validates everything (provider allow-list, PSE tickers, short text, https source,
 * date window, at most 60 rows); this forwards with a size cap. The server holds the token.
 */
export const revalidate = 0;
export const maxDuration = 60;

const MAX_BYTES = 32 * 1024;

export async function POST(req: NextRequest) {
  const raw = await req.text();
  if (raw.length > MAX_BYTES) return NextResponse.json({ error: "body too large" }, { status: 413 });
  let body: unknown;
  try {
    body = JSON.parse(raw);
  } catch {
    return NextResponse.json({ error: "body must be JSON" }, { status: 400 });
  }
  try {
    const data = await apiFetch<unknown>("/api/ph/index_events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : String(err) }, { status: 502 });
  }
}
