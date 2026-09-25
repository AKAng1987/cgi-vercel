import { apiFetch } from "@/lib/api";
import { BriefResponse, BriefChange, BriefSection } from "@/lib/types";
import Link from "next/link";

function rate(c: BriefChange) {
  if (!c.rate_per_year) return "—";
  return `${c.rate_per_year}/yr`;
}

/** Rarity is the whole ranking: a compass flip at 2.5/yr outranks a breadth
 *  colour change at 32.1/yr by ~13x, without anyone deciding it should. */
function ChangeRow({ c }: { c: BriefChange }) {
  return (
    <div
      className={`flex flex-wrap items-baseline gap-2 border-l-2 py-1 pl-2 text-[0.75rem] ${
        c.push ? "border-amber-600" : "border-slate-800"
      }`}
    >
      {c.push && (
        <span className="rounded bg-amber-950 px-1.5 text-[0.58rem] font-bold text-amber-300">
          PUSH
        </span>
      )}
      <span className="w-14 shrink-0 text-right text-[0.62rem] tabular-nums text-slate-600">
        {rate(c)}
      </span>
      <span className="text-slate-200">{c.title}</span>
      <span className="text-slate-500">{c.detail}</span>
      {c.when && <span className="text-[0.62rem] text-slate-600">{c.when}</span>}
    </div>
  );
}

function Section({ s }: { s: BriefSection }) {
  return (
    <div className="border-b border-slate-900 py-2">
      <div className="flex flex-wrap items-baseline gap-3">
        <span className="w-24 shrink-0 text-[0.62rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
          {s.name}
        </span>
        {s.status === "unavailable" ? (
          <span className="text-[0.72rem] text-rose-400">
            unavailable — {s.error}
          </span>
        ) : (
          <span className="text-[0.75rem] text-slate-300">{s.headline}</span>
        )}
      </div>
    </div>
  );
}

export default async function BriefPage({
  searchParams,
}: {
  searchParams: Promise<{ cadence?: string }>;
}) {
  const sp = await searchParams;
  const cadence = sp.cadence === "weekly" ? "weekly" : "daily";
  const d = await apiFetch<BriefResponse>(`/api/brief?cadence=${cadence}`);

  return (
    <main className="mx-auto max-w-4xl p-6">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-2xl font-bold">BRIEF</h1>
        <div className="flex gap-2 text-[0.7rem]">
          {(["daily", "weekly"] as const).map((c) => (
            <Link
              key={c}
              href={`/brief?cadence=${c}`}
              className={`rounded px-2 py-0.5 ${
                cadence === c
                  ? "bg-slate-800 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {c}
            </Link>
          ))}
        </div>
      </div>
      <p className="mb-4 text-xs leading-relaxed text-slate-400">
        {d.as_of} · covers {d.covers}. Importance is{" "}
        <span className="text-slate-200">a diff against rules already written down</span>, ranked
        by how rarely each one fires — not a judgement made each morning.
      </p>

      <section className="mb-6">
        {d.nothing_crossed ? (
          <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
            <div className="text-sm font-medium text-slate-200">Nothing crossed.</div>
            <p className="mt-1 text-[0.72rem] leading-relaxed text-slate-500">
              No rule changed state in this window. That is the normal outcome and it is the
              point — a brief that finds something to say every morning is how a weeks-to-months
              process gets traded daily.
            </p>
          </div>
        ) : (
          <>
            <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
              {d.headline}
            </div>
            <div>
              {d.changes.map((c, i) => (
                <ChangeRow key={i} c={c} />
              ))}
            </div>
          </>
        )}
      </section>

      <section className="mb-6">
        <div className="mb-1 text-[0.65rem] font-bold uppercase tracking-[2px] text-slate-600">
          Where things stand
        </div>
        {d.sections.map((s) => (
          <Section key={s.name} s={s} />
        ))}
      </section>

      {d.unavailable.length > 0 && (
        <p className="text-[0.68rem] text-rose-400">
          Degraded: {d.unavailable.join(", ")} — the rest of the brief is unaffected.
        </p>
      )}
      <p className="mt-3 text-[0.62rem] text-slate-600">{d.note}</p>
    </main>
  );
}
