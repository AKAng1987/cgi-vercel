import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for /api/brief, mirroring app/api/watchlists/route.ts.
 *
 * Read-only and unauthenticated: the cloud routines cannot hold a secret and
 * cannot reach *.onrender.com. The server holds the token.
 *
 * `cadence` is whitelisted rather than forwarded: passing an arbitrary query
 * string through to the upstream API is how a proxy becomes an open redirect
 * for someone else's parameters.
 */
export const revalidate = 0;

export async function GET(req: NextRequest) {
  const raw = req.nextUrl.searchParams.get("cadence");
  const cadence = raw === "weekly" ? "weekly" : "daily";
  try {
    const data = await apiFetch<unknown>(`/api/brief?cadence=${cadence}`);
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
