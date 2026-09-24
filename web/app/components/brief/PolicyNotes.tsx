import { PolicyNote } from "@/lib/types";

const TYPE: Record<string, string> = {
  monetary: "border-sky-800 bg-sky-950/60 text-sky-300",
  fiscal: "border-emerald-800 bg-emerald-950/60 text-emerald-300",
  trade: "border-amber-800 bg-amber-950/60 text-amber-300",
  geopolitical: "border-red-800 bg-red-950/60 text-red-300",
};

const FLAG: Record<string, string> = {
  US: "🇺🇸", JP: "🇯🇵", KR: "🇰🇷", CN: "🇨🇳", PH: "🇵🇭",
  GB: "🇬🇧", DE: "🇩🇪", FR: "🇫🇷", IT: "🇮🇹", ES: "🇪🇸", PT: "🇵🇹", EU: "🇪🇺", XX: "🌍",
};

export function PolicyNotes({ notes, compact }: { notes: PolicyNote[]; compact?: boolean }) {
  if (!notes.length) return null;
  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      {notes.map((p) => (
        <div
          key={`${p.announced}-${p.title}`}
          className={compact ? "border-l-2 border-slate-800 pl-2" : "rounded border border-slate-800 bg-slate-900/50 p-3"}
        >
          <div className="flex flex-wrap items-baseline gap-2">
            <span title={p.country}>{FLAG[p.country] ?? p.country}</span>
            <span className={`rounded border px-1.5 py-0.5 text-[0.6rem] uppercase tracking-wide ${TYPE[p.type] ?? TYPE.fiscal}`}>
              {p.type}
            </span>
            <span className="text-sm font-semibold text-slate-100">{p.title}</span>
            <span className="text-[0.65rem] text-slate-600">
              announced {p.announced}
              {p.age_days !== null && ` · ${Math.round(p.age_days / 30)}mo ago`}
            </span>
          </div>
          <p className={`mt-1 leading-relaxed text-slate-300 ${compact ? "text-[0.72rem]" : "text-sm"}`}>
            {p.detail}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-1">
            {p.live_themes.length > 0 && (
              <span className="rounded bg-emerald-950/60 px-1.5 py-0.5 text-[0.6rem] text-emerald-300" title="a theme this policy points at is still running on relative strength">
                still running: {p.live_themes.join(", ")}
              </span>
            )}
            {p.tickers.map((t) => (
              <span key={t} className="rounded bg-slate-800 px-1.5 py-0.5 text-[0.65rem] text-slate-400">
                {t}
              </span>
            ))}
          </div>
          <div className="mt-1 text-[0.6rem] text-slate-600">
            {p.source}
            {p.confidence && ` · ${p.confidence}`}
          </div>
        </div>
      ))}
    </div>
  );
}
