import { SignalsResponse } from "@/lib/types";

function pct(v: number | null): string {
  return v === null ? "—" : `${Math.round(v * 100)}%`;
}

export function SummaryStrip({ summary }: { summary: SignalsResponse["summary"] }) {
  const horizons = ["1w", "1m", "3m"] as const;
  return (
    <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-4">
      <div className="rounded border border-slate-800 bg-slate-900/60 p-3">
        <div className="text-[0.65rem] uppercase tracking-[2px] text-slate-500">Signals logged</div>
        <div className="mt-1 text-2xl font-bold text-slate-100">{summary.n_signals}</div>
        <div className="text-xs text-slate-500">
          {summary.first_signal_date} → {summary.last_signal_date}
          <span className="ml-2 text-slate-600">· {summary.n_with_divergence} with divergence</span>
        </div>
      </div>

      {horizons.map((h) => {
        const hz = summary.horizons[h];
        return (
          <div key={h} className="rounded border border-slate-800 bg-slate-900/60 p-3">
            <div className="text-[0.65rem] uppercase tracking-[2px] text-slate-500">
              {h} outcomes · {hz.compass.n_scored} scored
            </div>
            <div className="mt-1 grid grid-cols-2 gap-2">
              {(["compass", "grid"] as const).map((ax) => {
                const a = hz[ax];
                return (
                  <div key={ax}>
                    <div className="text-[0.65rem] uppercase text-slate-500">{ax}</div>
                    <div className="text-xl font-bold text-slate-100">{pct(a.hit_rate_on_changed)}</div>
                    <div className="text-[0.68rem] text-slate-500">
                      {a.n_top3_hit}/{a.n_changed} hit on changed
                      {a.n_scored - a.n_changed > 0 && (
                        <span className="text-slate-600"> · {a.n_scored - a.n_changed} same</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
