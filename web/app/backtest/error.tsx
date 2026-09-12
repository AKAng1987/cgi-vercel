"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col items-center justify-center gap-4 p-8">
      <div className="w-full rounded-lg border border-red-800 bg-red-950/50 p-4 text-sm">
        <span className="font-medium text-red-400">Failed to load BACKTEST page</span>
        <p className="mt-1 text-slate-400">{error.message}</p>
      </div>
      <button
        onClick={reset}
        className="rounded-md border border-slate-700 bg-slate-800 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700"
      >
        Retry
      </button>
    </main>
  );
}
