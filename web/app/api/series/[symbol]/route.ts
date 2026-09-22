import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for the append-only series loader, so the monthly
 * TradingView routine can write without reaching *.onrender.com. The
 * upstream endpoint does all validation (whitelist, ranges, append-only);
 * this only forwards.
 */
export const revalidate = 0;

export async function POST(req: NextRequest, ctx: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await ctx.params;
  if (!/^[A-Z_]{2,32}$/.test(symbol)) {
    return NextResponse.json({ error: "bad symbol" }, { status: 400 });
  }
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "body must be JSON" }, { status: 400 });
  }
  try {
    const data = await apiFetch<unknown>(`/api/series/${symbol}`, {
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
