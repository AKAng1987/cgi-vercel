import { apiFetch } from "@/lib/api";
import { NotesResponse, PolicyWatchResponse } from "@/lib/types";
import { PolicyNotes } from "../components/brief/PolicyNotes";
import { Notes } from "../components/brief/Notes";

export default async function NotesPage() {
  const [data, watch] = await Promise.all([
    apiFetch<NotesResponse>("/api/notes"),
    apiFetch<PolicyWatchResponse>("/api/policy-watch").catch(() => null),
  ]);

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="mb-1 text-2xl font-bold">NOTES</h1>
      <p className="mb-5 text-xs leading-relaxed text-slate-400">
        Three registers, kept apart because they decay and are trusted differently.{" "}
        <span className="text-slate-200">Policy</span> is dated announcements by country, each
        naming the themes it should move — meant to work forward, so a policy is on the page before
        the rally rather than explaining it afterwards.{" "}
        <span className="text-slate-200">Narrative</span> is known but not derivable from price.{" "}
        <span className="text-slate-200">Findings</span> are this build&apos;s own test results.
      </p>

      <section className="mb-7">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
          Policy · {data.counts.policy} · {data.countries.join(" ")}
        </div>
        <PolicyNotes notes={data.policy} />
      </section>

      {watch && watch.candidates.length > 0 && (
        <section className="mb-7">
          <div className="mb-2 flex items-baseline gap-3">
            <div className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
              Candidates · last {watch.window_days}d
            </div>
            <div className="text-xs text-slate-500">from central bank feeds — confirm one and it becomes a policy note</div>
          </div>
          <div className="space-y-1">
            {watch.candidates.map((c) => (
              <div key={`${c.announced}-${c.title}`} className="flex flex-wrap items-baseline gap-2 border-l-2 border-slate-800 pl-2 text-[0.72rem]">
                <span className="text-slate-600">{c.announced ?? "?"}</span>
                <span className="rounded bg-slate-800 px-1.5 text-[0.6rem] text-slate-400">{c.country}</span>
                <span className="rounded bg-slate-900 px-1.5 text-[0.6rem] text-slate-500">{c.type}</span>
                {c.link ? (
                  <a href={c.link} target="_blank" rel="noreferrer" className="text-slate-300 underline decoration-slate-700 hover:text-slate-100">
                    {c.title}
                  </a>
                ) : (
                  <span className="text-slate-300">{c.title}</span>
                )}
              </div>
            ))}
          </div>
          {watch.no_feed.length > 0 && (
            <p className="mt-2 text-[0.65rem] text-slate-600">
              No feed, still manual: {watch.no_feed.map((n) => `${n.source} (${n.reason})`).join(" · ")}
            </p>
          )}
        </section>
      )}

      <section className="mb-7">
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
          Narrative · {data.counts.narrative}
        </div>
        <Notes notes={data.narrative.map((n) => ({ ...n, kind: "narrative" as const }))} />
      </section>

      <section>
        <div className="mb-2 text-[0.65rem] font-bold uppercase tracking-[2px] text-[#8b9dc3]">
          Findings · {data.counts.findings}
        </div>
        <Notes notes={data.findings.map((n) => ({ ...n, kind: "data" as const }))} />
      </section>
    </main>
  );
}
