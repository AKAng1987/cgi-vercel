import { Note } from "@/lib/types";

const KIND: Record<string, { badge: string; label: string }> = {
  data: { badge: "border-sky-800 bg-sky-950/60 text-sky-300", label: "data" },
  narrative: { badge: "border-violet-800 bg-violet-950/60 text-violet-300", label: "narrative" },
  policy: { badge: "border-amber-800 bg-amber-950/60 text-amber-300", label: "policy" },
};

/** A note list. Used standalone on /notes and inline under a scoped object. */
export function Notes({ notes, compact }: { notes: Note[]; compact?: boolean }) {
  if (!notes.length) return null;
  return (
    <div className={compact ? "space-y-1.5" : "space-y-3"}>
      {notes.map((n) => {
        const k = KIND[n.kind ?? "data"] ?? KIND.data;
        return (
          <div
            key={`${n.date}-${n.title}`}
            className={compact ? "border-l-2 border-slate-800 pl-2" : "rounded border border-slate-800 bg-slate-900/50 p-3"}
          >
            <div className="flex flex-wrap items-baseline gap-2">
              <span className={`rounded border px-1.5 py-0.5 text-[0.6rem] uppercase tracking-wide ${k.badge}`}>
                {k.label}
              </span>
              <span className="text-sm font-semibold text-slate-100">{n.title}</span>
              <span className="text-[0.65rem] text-slate-600">
                {n.date}
                {n.age_days !== null && n.age_days !== undefined && ` · ${n.age_days}d ago`}
                {!compact && ` · ${n.scope}`}
              </span>
            </div>
            <p className={`mt-1 leading-relaxed text-slate-300 ${compact ? "text-[0.72rem]" : "text-sm"}`}>{n.body}</p>
            <div className="mt-1 text-[0.62rem] text-slate-600">
              {n.source}
              {n.confidence && ` · ${n.confidence}`}
            </div>
          </div>
        );
      })}
    </div>
  );
}
