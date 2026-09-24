import { CotContract } from "@/lib/types";

function Spark({ vals }: { vals: number[] }) {
  if (!vals?.length) return null;
  const W = 220, H = 42;
  const lo = Math.min(...vals, 0), hi = Math.max(...vals, 0);
  const span = hi - lo || 1;
  const y = (v: number) => H - ((v - lo) / span) * H;
  const x = (i: number) => (i / Math.max(1, vals.length - 1)) * W;
  const d = vals.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const last = vals[vals.length - 1];
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="mt-1.5 w-full">
      <line x1={0} x2={W} y1={y(0)} y2={y(0)} stroke="#334155" strokeWidth={0.8} />
      <path d={d} fill="none" stroke={last >= 0 ? "#10b981" : "#ef4444"} strokeWidth={1.4} />
    </svg>
  );
}

export function CotCard({ c }: { c: CotContract }) {
  if (c.status !== "ok") {
    return (
      <div className="rounded border border-slate-800/60 bg-slate-950/50 p-3 text-slate-600">
        <div className="text-sm font-semibold">{c.contract}</div>
        <div className="text-[0.65rem]">{c.status}</div>
      </div>
    );
  }
  const idx = c.cot_index["3y"];
  const extreme = idx !== null && (idx <= 10 || idx >= 90);
  return (
    <div
      className={`rounded border p-3 ${
        extreme ? "border-[#8b9dc3] bg-slate-900/80" : "border-slate-800 bg-slate-900/50"
      }`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold text-slate-100">{c.contract}</span>
        <span
          className={`text-sm font-bold ${
            idx === null ? "text-slate-500" : idx <= 10 ? "text-emerald-300" : idx >= 90 ? "text-red-300" : "text-slate-300"
          }`}
          title="COT index, 3-year: 0 = most short it has been, 100 = most long"
        >
          {idx ?? "—"}
        </span>
      </div>

      <div className="mt-0.5 text-[0.7rem] text-slate-400">
        specs{" "}
        <span className={c.spec >= 0 ? "text-emerald-400" : "text-red-400"}>
          {c.spec.toLocaleString()}
        </span>{" "}
        <span className="text-slate-600">({c.spec_pct_oi}% OI)</span>
      </div>
      <div className="text-[0.65rem] text-slate-600">
        4w {c.spec_change_4w >= 0 ? "+" : ""}
        {c.spec_change_4w.toLocaleString()} · comm {c.comm.toLocaleString()} · OI-basis idx{" "}
        {c.cot_index_pct_oi["3y"] ?? "—"}
      </div>

      <Spark vals={c.spark} />

      {c.signal && (
        <div className={`mt-1 text-[0.65rem] ${idx !== null && idx <= 10 ? "text-emerald-300" : "text-red-300"}`}>
          {c.signal}
        </div>
      )}
      <div className="mt-0.5 text-[0.6rem] text-slate-700">
        {c.n_weeks} weeks from {c.history_from}
      </div>
    </div>
  );
}
