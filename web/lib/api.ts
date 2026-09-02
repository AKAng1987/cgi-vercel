/**
 * Server-side only: reads API_URL / API_TOKEN from the environment, so the
 * token never reaches the browser. Only call this from Server Components,
 * Route Handlers, or other server-side code.
 */
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

  const res = await fetch(url, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${apiToken}`,
    },
    cache: "no-store",
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API request failed: ${res.status} ${res.statusText} ${body}`);
  }

  return res.json() as Promise<T>;
}
