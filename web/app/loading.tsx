export default function Loading() {
  return (
    <main className="mx-auto max-w-6xl animate-pulse p-6">
      <div className="mb-3 h-7 w-48 rounded bg-slate-800" />
      <div className="mb-4 h-3 w-64 rounded bg-slate-800" />
      <div className="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="h-48 rounded-lg border border-slate-800 bg-slate-900" />
        <div className="h-48 rounded-lg border border-slate-800 bg-slate-900" />
      </div>
      {[...Array(4)].map((_, i) => (
        <div key={i} className="mb-3 h-32 rounded bg-slate-900" />
      ))}
    </main>
  );
}
