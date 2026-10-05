import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for POST /api/freshness/heartbeat: how the refresh routine says
 * it ran. See ../route.ts for why it goes through Vercel (the routine's network
 * sinkholes *.onrender.com).
 *
 * The upstream endpoint is unauthenticated and does the validation; this forwards,
 * with a size cap so the proxy is not an open pipe for large bodies.
 */
export const revalidate = 0;
export const maxDuration = 60;

const MAX_BYTES = 64 * 1024;

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
    const data = await apiFetch<unknown>("/api/freshness/heartbeat", {
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
