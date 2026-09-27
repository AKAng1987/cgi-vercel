import { NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";

/**
 * Same-origin proxy for /api/priced-in, so the FUNDAMENTALS panel can be
 * driven from the browser without the API token reaching it.
 *
 * Read-only, like the other proxies here: this endpoint computes, it does not
 * store anything, and every input comes from the caller.
 */
export const revalidate = 0;

const PASS = [
  "growth_pct",
  "rate_pct",
  "multiple",
  "erp_pct",
  "fade_years",
  "terminal_growth_pct",
] as const;

export async function GET(req: Request) {
  const src = new URL(req.url).searchParams;
  const qs = new URLSearchParams();
  for (const k of PASS) {
    const v = src.get(k);
    if (v !== null && v !== "") qs.set(k, v);
  }
  if (!qs.has("growth_pct")) {
    return NextResponse.json({ error: "growth_pct is required" }, { status: 400 });
  }
  try {
    const data = await apiFetch<unknown>(`/api/priced-in?${qs.toString()}`);
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
