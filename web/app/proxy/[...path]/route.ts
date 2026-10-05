import { NextRequest, NextResponse } from "next/server";

/**
 * Authenticated, read-only passthrough to the CGI API, for `cgi-mcp` (the execution project's window
 * into CGI) when it runs on a network that sinkholes *.onrender.com.
 *
 * It holds NO secret. The caller sends its own `Authorization: Bearer <CGI_API_TOKEN>`; this forwards that
 * header to Render, and Render's own check decides. No token or a wrong token therefore gets Render's 401
 * back, so the login-protected endpoints stay exactly as protected as before. (Do not use apiFetch here: it
 * injects the SERVER's token, which would make every endpoint below public.)
 *
 * GET only (other methods get 405 from Next), and only the paths cgi-mcp actually uses. The write endpoints
 * (/api/series/*, /api/freshness/heartbeat) are deliberately not on the list.
 */
export const revalidate = 0;
// Vercel gives up at 60s; a sleeping Render instance can need ~75s to wake. cgi-mcp retries once.
export const maxDuration = 60;

const ALLOWED: RegExp[] = [
  /^api\/(live|markov|countries|priced-in|freshness|watchlists|universe|mixture|themes)$/,
  /^api\/cot\/public$/,
  /^api\/backtest\/current$/,
  /^api\/backtest\/[1-4]\/[1-4]$/,
];

export async function GET(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  if (path.some((p) => p === "" || p === "." || p === "..")) {
    return NextResponse.json({ error: "bad path" }, { status: 400 });
  }
  const joined = path.join("/");
  if (!ALLOWED.some((re) => re.test(joined))) {
    return NextResponse.json({ error: "path not available through this proxy" }, { status: 400 });
  }
  const base = process.env.API_URL;
  if (!base) {
    return NextResponse.json({ error: "API_URL is not configured" }, { status: 500 });
  }
  const auth = req.headers.get("authorization");
  try {
    const res = await fetch(`${base.replace(/\/$/, "")}/${joined}${req.nextUrl.search}`, {
      headers: auth ? { Authorization: auth } : {},
      cache: "no-store",
    });
    return new NextResponse(await res.text(), {
      status: res.status,
      headers: {
        "Content-Type": res.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
