import { apiFetch } from "@/lib/api";
import { LiveResponse } from "@/lib/types";
import { DateHeader } from "./components/DateHeader";
import { RegimeCard } from "./components/RegimeCard";
import { LiveDashboardClient } from "./components/LiveDashboardClient";

export default async function Home() {
  const data = await apiFetch<LiveResponse>("/api/live");

  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="mb-3 text-2xl font-bold">CGI Dashboard</h1>
      <DateHeader asOf={data.as_of} generatedAt={data.generated_at} />

      <section className="mb-2 grid grid-cols-1 gap-4 md:grid-cols-2">
        <RegimeCard kind="compass" data={data.compass} />
        <RegimeCard kind="grid" data={data.grid} />
      </section>

      <LiveDashboardClient data={data} />
    </main>
  );
}
