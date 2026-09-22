import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/** Same-origin proxy for GET /api/series (what to pull, last stored date). */
export const revalidate = 0;

export async function GET() {
  try {
    const data = await apiFetch<unknown>("/api/series");
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
