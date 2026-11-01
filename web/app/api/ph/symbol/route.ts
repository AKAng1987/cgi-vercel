import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/** Same-origin proxy for /api/ph/symbol (the chart dock's one-ticker read). The server holds the token. */
export const revalidate = 0;

export async function GET(req: NextRequest) {
  const s = req.nextUrl.searchParams.get("s") ?? "";
  if (!/^[A-Za-z0-9]{1,8}$/.test(s)) return NextResponse.json({ error: "bad ticker" }, { status: 400 });
  try {
    return NextResponse.json(await apiFetch<unknown>(`/api/ph/symbol?s=${encodeURIComponent(s)}`));
  } catch (err) {
    return NextResponse.json({ error: err instanceof Error ? err.message : String(err) }, { status: 502 });
  }
}
