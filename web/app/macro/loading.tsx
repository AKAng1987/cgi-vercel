export default function Loading() {
  return (
    <main className="mx-auto max-w-6xl animate-pulse p-6">
      <div className="mb-4 h-7 w-32 rounded bg-slate-800" />
      {[...Array(3)].map((_, i) => (
        <div key={i} className="mb-3 h-48 rounded-lg border border-slate-800 bg-slate-900" />
      ))}
    </main>
  );
}
