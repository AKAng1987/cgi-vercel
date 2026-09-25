export default function Loading() {
  return (
    <main className="mx-auto max-w-5xl animate-pulse p-6">
      <div className="mb-3 h-7 w-44 rounded bg-slate-800" />
      <div className="mb-5 h-10 w-full rounded bg-slate-900" />
      {/* A cold load pulls ~65 companyfacts payloads from the SEC, so the
          first request after the 12h cache expires genuinely takes ~15s.
          Say so rather than showing an ambiguous spinner. */}
      <p className="mb-4 text-[0.7rem] text-slate-600">
        Reading filings from the SEC — a cold load pulls every filer in the universe and takes a
        few seconds.
      </p>
      <div className="mb-3 h-32 rounded-lg border border-slate-800 bg-slate-900" />
      <div className="mb-3 h-40 rounded-lg border border-slate-800 bg-slate-900" />
      <div className="h-64 rounded-lg border border-slate-800 bg-slate-900" />
    </main>
  );
}
