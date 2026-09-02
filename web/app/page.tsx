import { apiFetch } from "@/lib/api";

interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

export default async function Home() {
  let health: HealthResponse | null = null;
  let error: string | null = null;

  try {
    health = await apiFetch<HealthResponse>("/api/health");
  } catch (e) {
    error = e instanceof Error ? e.message : "Unknown error";
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-3xl font-bold">CGI Dashboard</h1>

      {health ? (
        <div className="w-full rounded-lg border border-emerald-800 bg-emerald-950/50 p-4 text-sm">
          <span className="font-medium text-emerald-400">
            API status: {health.status.toUpperCase()}
          </span>
          <span className="text-slate-400"> · {health.service} v{health.version}</span>
        </div>
      ) : (
        <div className="w-full rounded-lg border border-red-800 bg-red-950/50 p-4 text-sm">
          <span className="font-medium text-red-400">API status: ERROR</span>
          <p className="mt-1 text-slate-400">{error}</p>
        </div>
      )}
    </main>
  );
}
