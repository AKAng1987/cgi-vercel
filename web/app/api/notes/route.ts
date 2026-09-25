import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for /api/notes, mirroring app/api/watchlists/route.ts.
 *
 * Read-only and unauthenticated on purpose: the cloud routines cannot hold a
 * secret, and they cannot reach *.onrender.com at all -- the egress policy
 * blocks it and the user's home network sinkholes the domain. The server holds
 * the token; the caller never sees it.
 *
 * This exposes nothing new. Every one of these already renders as a public
 * page; without the proxy the monthly review routine was fetching a 404.
 */
export const revalidate = 0;

export async function GET() {
  try {
    const data = await apiFetch<unknown>("/api/notes");
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
