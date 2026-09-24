import { apiFetch } from "@/lib/api";
import { NotesResponse } from "@/lib/types";
import { Notes } from "../components/brief/Notes";

/**
 * The accumulation. Everything CGI has established, dated and attributed --
 * tested numbers and narrative context side by side, neither pretending to
 * be the other.
 */
export default async function NotesPage() {
  const data = await apiFetch<NotesResponse>("/api/notes");

  return (
    <main className="mx-auto max-w-4xl p-6">
      <h1 className="mb-1 text-2xl font-bold">NOTES</h1>
      <p className="mb-4 text-xs text-slate-400">
        What we have established, dated and attributed.{" "}
        <span className="text-sky-300">data</span> is something a test found, with its numbers;{" "}
        <span className="text-violet-300">narrative</span> is something known but not derivable from
        price; <span className="text-amber-300">policy</span> is a dated event and its read-through.
        Every note keeps its date, so a claim that ages badly is visibly old rather than quietly
        wrong.
      </p>

      <div className="mb-4 flex flex-wrap gap-3 text-[0.7rem] text-slate-500">
        <span>{data.count} notes</span>
        {Object.entries(data.by_kind).map(([k, n]) => (
          <span key={k}>
            {k} {n}
          </span>
        ))}
      </div>

      <Notes notes={data.notes} />
    </main>
  );
}
