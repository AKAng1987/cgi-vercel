import { apiFetch } from "@/lib/api";
import { NotesResponse } from "@/lib/types";
import { PolicyNotes } from "../components/brief/PolicyNotes";
import { Notes } from "../components/brief/Notes";

export default async function NotesPage() {
  const data = await apiFetch<NotesResponse>("/api/notes");

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
