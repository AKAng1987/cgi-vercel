import { SectionSkeleton } from "../components/macro/SectionSkeleton";

export default function Loading() {
  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="mb-4 text-2xl font-bold">BACKTEST</h1>
      <SectionSkeleton lines={4} />
    </main>
  );
}
