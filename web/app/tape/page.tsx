import { apiFetch } from "@/lib/api";
import { LiveResponse } from "@/lib/types";
import { DateHeader } from "../components/DateHeader";
import { RegimeCard } from "../components/RegimeCard";
import { LiveDashboardClient } from "../components/LiveDashboardClient";

export default async function Tape() {
  const data = await apiFetch<LiveResponse>("/api/live");

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="mb-1 text-2xl font-bold">TAPE</h1>
      <p className="mb-3 text-xs text-slate-400">Overnight and weekly moves across the whole universe — the scan. The brief is on <a href="/" className="underline">LIVE</a>.</p>
      <DateHeader asOf={data.as_of} generatedAt={data.generated_at} />

      <section className="mb-2 grid grid-cols-1 gap-4 md:grid-cols-2">
        <RegimeCard kind="compass" data={data.compass} />
        <RegimeCard kind="grid" data={data.grid} />
      </section>

      <LiveDashboardClient data={data} />
    </main>
  );
}
