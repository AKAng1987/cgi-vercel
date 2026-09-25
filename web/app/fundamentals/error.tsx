"use client";

/**
 * Boundary for /fundamentals. The page is one server-side fetch of
 * /api/fundamentals, which on a cold cache pulls ~65 SEC companyfacts
 * payloads -- so the realistic failures are a timeout or an SEC hiccup, both
 * of which retry cleanly. Without this the route rendered a blank body, which
 * is how the first deploy looked broken when it was only slow.
 */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="mx-auto flex min-h-[60vh] max-w-xl flex-col items-center justify-center gap-4 p-8">
      <div className="w-full rounded-lg border border-red-800 bg-red-950/50 p-4 text-sm">
        <span className="font-medium text-red-400">Failed to load FUNDAMENTALS</span>
        <p className="mt-1 break-words text-slate-400">{error.message}</p>
        <p className="mt-2 text-[0.7rem] text-slate-500">
          This page reads SEC XBRL live. A cold cache pulls every filer in the universe, so a
          timeout here usually just needs a retry.
        </p>
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
