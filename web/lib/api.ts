/**
 * Server-side only: reads API_URL / API_TOKEN from the environment, so the
 * token never reaches the browser. Only call this from Server Components,
 * Route Handlers, or other server-side code.
 */
const TIMEOUT_MS = 55_000; // below the pages' 60 s maxDuration

export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const apiUrl = process.env.API_URL;
  const apiToken = process.env.API_TOKEN;

  if (!apiUrl) {
    throw new Error("API_URL environment variable is not set");
  }
  if (!apiToken) {
    throw new Error("API_TOKEN environment variable is not set");
  }

  const url = `${apiUrl.replace(/\/$/, "")}${path}`;

  // A time budget: a stuck call (sleeping or rebuilding API) fails after TIMEOUT_MS instead of letting the whole
  // function run into Vercel's execution limit, so the page shows its error state, not a platform timeout.
  const res = await fetch(url, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${apiToken}`,
    },
    cache: "no-store",
    signal: init?.signal ?? AbortSignal.timeout(TIMEOUT_MS),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API request failed: ${res.status} ${res.statusText} ${body}`);
  }

  return res.json() as Promise<T>;
}
