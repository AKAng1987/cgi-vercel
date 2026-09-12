"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useTransition } from "react";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

/**
 * URL-synced controls for the BACKTEST tab. Every change pushes a new
 * search string; the page (server component) reruns and refetches. All
 * state lives in the URL, so a bookmarked/shared link restores the exact
 * view -- the Streamlit tab uses session_state for the same purpose but
 * can't be shared that way.
 */
export function BacktestClient({
  compassQ,
  gridQ,
  minOcc,
  lookback,
}: {
  compassQ: number;
  gridQ: number;
  minOcc: number;
  lookback: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  function updateParam(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set(key, value);
    startTransition(() => {
      router.push(`?${params.toString()}`, { scroll: false });
    });
  }

  return (
    <div
      className={`mb-4 grid grid-cols-1 gap-3 rounded border border-slate-800 bg-slate-900/40 p-3 md:grid-cols-4 ${
        isPending ? "opacity-60" : ""
      }`}
    >
      <label className="flex flex-col text-xs text-slate-400">
        Compass
        <select
          value={compassQ}
          onChange={(e) => updateParam("cq", e.target.value)}
          className="mt-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100"
        >
          {[1, 2, 3, 4].map((q) => (
            <option key={q} value={q}>
              {COMPASS_Q_LABELS[q]}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col text-xs text-slate-400">
        Grid
        <select
          value={gridQ}
          onChange={(e) => updateParam("gq", e.target.value)}
          className="mt-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100"
        >
          {[1, 2, 3, 4].map((q) => (
            <option key={q} value={q}>
              {GRID_Q_LABELS[q]}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col text-xs text-slate-400">
        Min occurrences: <span className="text-slate-200">{minOcc}</span>
        <input
          type="range"
          min={1}
          max={20}
          step={1}
          value={minOcc}
          onChange={(e) => updateParam("min_occ", e.target.value)}
          className="mt-2 accent-blue-500"
        />
      </label>

      <label className="flex flex-col text-xs text-slate-400">
        Lookback
        <select
          value={lookback}
          onChange={(e) => updateParam("lookback", e.target.value)}
          className="mt-1 rounded border border-slate-700 bg-slate-950 px-2 py-1 text-sm text-slate-100"
        >
          <option value="all">All history</option>
          <option value="10y">Last 10 years</option>
          <option value="5y">Last 5 years</option>
        </select>
      </label>
    </div>
  );
}
