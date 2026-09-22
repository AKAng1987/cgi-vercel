import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for /api/watchlists. The cloud routine that rewrites
 * the TradingView lists cannot reach *.onrender.com (egress policy), and
 * the user's home network sinkholes that domain too -- both can reach
 * vercel.app. Read-only, no token needed (ticker lists only).
 */
export const revalidate = 0;

export async function GET() {
  try {
    const data = await apiFetch<unknown>("/api/watchlists");
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
