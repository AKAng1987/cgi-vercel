import { NextRequest, NextResponse } from "next/server";
import { apiFetch } from "@/lib/api";
import { BacktestOccurrencesResponse } from "@/lib/types";

/**
 * Same-origin proxy so the client-side OccurrenceDetail component can
 * fetch backtest occurrence detail without ever seeing API_TOKEN. Keeps
 * the token server-side; the browser only sees /api/backtest-occurrences.
 */
export async function GET(req: NextRequest) {
  const sp = req.nextUrl.searchParams;
  const cq = Number(sp.get("cq"));
  const gq = Number(sp.get("gq"));
  const ticker = sp.get("ticker");

  if (![1, 2, 3, 4].includes(cq) || ![1, 2, 3, 4].includes(gq) || !ticker) {
    return NextResponse.json(
      { error: "cq and gq must each be 1-4, and ticker must be provided" },
      { status: 400 }
    );
  }

  try {
    const data = await apiFetch<BacktestOccurrencesResponse>(
      `/api/backtest/${cq}/${gq}/occurrences?ticker=${encodeURIComponent(ticker)}`
    );
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
