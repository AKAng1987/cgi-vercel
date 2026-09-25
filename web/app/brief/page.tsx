import { apiFetch } from "@/lib/api";
import {
  BriefResponse,
  BriefChange,
  BriefSection,
  TechnicalsResponse,
  ThemeRow,
  RunStats,
  StandingTheme as ST,
  CotResponse,
  PolicyCandidate,
  FundRollup,
} from "@/lib/types";
import { BreadthStrip } from "../components/brief/BreadthStrip";
import { ThemesTable } from "../components/brief/ThemesTable";
import { StandingTheme } from "../components/brief/StandingTheme";
import Link from "next/link";

/** Rarity is already computed server-side from measured firing rates, so the
 *  visual weight here is derived, not decided: a compass flip at 2.5/yr reads
 *  louder than a breadth colour change at 32.1/yr because it IS rarer. */
function weight(c: BriefChange) {
  if (c.push) return "border-amber-500 bg-amber-950/20";
  if ((c.rate_per_year ?? 99) <= 12) return "border-slate-600";
  return "border-slate-800";
}

function ChangeRow({ c }: { c: BriefChange }) {
  return (
    <div className={`border-l-2 py-1.5 pl-3 ${weight(c)}`}>
      <div className="flex flex-wrap items-baseline gap-2">
        {c.push && (
          <span className="rounded bg-amber-500 px-1.5 text-[0.58rem] font-bold text-amber-950">
            ACT
          </span>
        )}
        <span className="text-[0.82rem] font-medium text-slate-100">{c.title}</span>
        {c.rate_per_year && (
          <span
            className="text-[0.6rem] tabular-nums text-slate-500"
            title={`This kind of event fires about ${c.rate_per_year} times a year, measured from CGI's own history`}
          >
            {c.rate_per_year}/yr
          </span>
        )}
        {c.when && <span className="text-[0.6rem] text-slate-600">{c.when}</span>}
      </div>
      <div className="mt-0.5 text-[0.72rem] leading-relaxed text-slate-400">{c.detail}</div>
    </div>
  );
}

function Panel({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="mb-6">
      <div className="mb-2 flex flex-wrap items-baseline gap-3">
        <h2 className="text-[0.65rem] font-bold uppercase tracking-[2px] text-[color:var(--cgi-accent)]">
          {title}
        </h2>
        {note && <span className="text-[0.66rem] text-slate-500">{note}</span>}
      </div>
      {children}
    </section>
  );
}

function Unavailable({ s }: { s: BriefSection }) {
  return (
    <div className="rounded border border-rose-900 bg-rose-950/30 p-3 text-[0.72rem] text-rose-300">
      {s.name} unavailable — {s.error}
      <div className="mt-1 text-slate-500">Every other section is unaffected.</div>
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
  const get = (n: string) => d.sections.find((s) => s.name === n);

  const regime = get("regime");
  const breadth = get("breadth");
  const themes = get("themes");
  const fundamentals = get("fundamentals");
  const positioning = get("positioning");
  const policy = get("policy");

  const themeBody = themes?.body as
    | { started?: ThemeRow[]; standing?: ST[]; running?: ThemeRow[]; run_stats?: RunStats }
    | undefined;
  const fundBody = fundamentals?.body as
    | {
        changes?: { symbol: string; detail: string }[];
        ai_layers?: ({ layer: string } & FundRollup)[];
      }
    | undefined;
  const cotBody = positioning?.body as Pick<CotResponse, "extremes" | "caveat"> | undefined;
  const polBody = policy?.body as { candidates?: PolicyCandidate[] } | undefined;

  return (
    <main className="mx-auto max-w-4xl p-6">
      {/* The headline is the page. */}
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-3">
        <h1 className="text-2xl font-bold">BRIEF</h1>
        <div className="flex gap-2 text-[0.7rem]">
          {(["daily", "weekly"] as const).map((c) => (
            <Link
              key={c}
              href={`/brief?cadence=${c}`}
              className={`rounded px-2 py-0.5 ${
                cadence === c ? "bg-slate-800 text-slate-100" : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {c}
            </Link>
          ))}
        </div>
      </div>
      <p className="mb-5 text-xs text-slate-500">
        {d.as_of} · covers {d.covers}
      </p>

      {regime?.status === "ok" && (
        <div className="mb-5 rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="text-lg font-semibold text-slate-100">{regime.headline}</div>
        </div>
      )}

      {d.nothing_crossed ? (
        <div className="mb-6 rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="text-base font-medium text-slate-100">Nothing crossed.</div>
          <p className="mt-1 max-w-2xl text-[0.74rem] leading-relaxed text-slate-400">
            No rule changed state in this window — and that is the normal outcome. A brief that
            finds something to say every morning is how a weeks-to-months process gets traded
            daily, which is the thing CGI exists to prevent. What follows is where things stand,
            not what changed.
          </p>
        </div>
      ) : (
        <Panel
          title={d.headline}
          note="ranked by how rarely each rule fires — measured, not judged"
        >
          <div className="space-y-1">
            {d.changes.map((c, i) => (
              <ChangeRow key={i} c={c} />
            ))}
          </div>
        </Panel>
      )}

      {/* BreadthStrip renders its own heading, so no Panel wrapper here --
          wrapping it printed "BREADTH · net new highs is the primary" twice. */}
      {breadth &&
        (breadth.status === "ok" ? (
          <BreadthStrip t={breadth.body as TechnicalsResponse} />
        ) : (
          <Panel title="Breadth">
            <Unavailable s={breadth} />
          </Panel>
        ))}

      {themes &&
        (themes.status === "ok" ? (
          <>
            {themeBody?.standing && themeBody.standing.length > 0 && (
              <Panel title="Standing themes" note="the slow layer — held, not re-decided">
                <StandingTheme themes={themeBody.standing} />
              </Panel>
            )}
            <Panel title="Themes in force" note={themes.headline}>
              <ThemesTable themes={themeBody?.running ?? []} runStats={themeBody?.run_stats} />
            </Panel>
          </>
        ) : (
          <Panel title="Themes">
            <Unavailable s={themes} />
          </Panel>
        ))}

      {/* Fundamentals sit BELOW the tape on purpose: quarterly filings lag
          price by three to six weeks, so they confirm, they never break news. */}
      {fundamentals &&
        (fundamentals.status === "ok" ? (
          <Panel title="Who is earning it" note="quarterly filings — confirmation, not news">
            {fundBody?.changes && fundBody.changes.length > 0 && (
              <div className="mb-2 space-y-1">
                {fundBody.changes.map((c, i) => (
                  <div key={i} className="border-l-2 border-slate-700 pl-2 text-[0.74rem] text-slate-300">
                    <span className="font-mono text-slate-200">{c.symbol}</span> {c.detail}
                  </div>
                ))}
              </div>
            )}
            <div className="rounded border border-slate-800 bg-slate-900/40 p-3">
              <div className="mb-1 text-[0.62rem] uppercase tracking-wider text-slate-500">
                AI layer cake — median revenue acceleration
              </div>
              {(fundBody?.ai_layers ?? []).map((l) => (
                <div
                  key={l.layer}
                  className="flex flex-wrap items-baseline gap-3 border-b border-slate-900 py-1 text-[0.74rem] last:border-0"
                >
                  <span className="w-28 shrink-0 text-slate-300">{l.layer}</span>
                  <span
                    className={`w-16 shrink-0 text-right tabular-nums ${
                      (l.median_revenue_acceleration_pp ?? 0) > 0.5
                        ? "text-emerald-400"
                        : (l.median_revenue_acceleration_pp ?? 0) < -0.5
                        ? "text-rose-400"
                        : "text-slate-400"
                    }`}
                  >
                    {l.median_revenue_acceleration_pp === null ||
                    l.median_revenue_acceleration_pp === undefined
                      ? "—"
                      : `${l.median_revenue_acceleration_pp > 0 ? "+" : ""}${l.median_revenue_acceleration_pp.toFixed(1)}pp`}
                  </span>
                  <span className="text-[0.66rem] text-slate-500">
                    {l.leaders?.length ? `lead ${l.leaders.join(" ")}` : "nothing listable yet"}
                  </span>
                </div>
              ))}
            </div>
          </Panel>
        ) : (
          <Panel title="Who is earning it">
            <Unavailable s={fundamentals} />
          </Panel>
        ))}

      {positioning && positioning.status === "ok" && (cotBody?.extremes?.length ?? 0) > 0 && (
        <Panel title="Positioning" note="a condition, not a trigger — extremes persist">
          <div className="space-y-1">
            {cotBody!.extremes.map((e) => (
              <div
                key={e.contract}
                className="flex flex-wrap items-baseline gap-2 border-l-2 border-slate-800 pl-2 text-[0.74rem]"
              >
                <span className="w-36 shrink-0 text-slate-200">{e.contract}</span>
                <span className="tabular-nums text-slate-400">{e.cot_index_3y}</span>
                <span className="text-[0.68rem] text-slate-500">{e.signal}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}

      {policy && policy.status === "ok" && (polBody?.candidates?.length ?? 0) > 0 && (
        <Panel title="Policy candidates" note="confirm one and it becomes a policy note">
          <div className="space-y-1">
            {polBody!.candidates!.map((c, i) => (
              <div
                key={i}
                className="flex flex-wrap items-baseline gap-2 border-l-2 border-slate-800 pl-2 text-[0.74rem]"
              >
                <span className="text-slate-600">{c.announced ?? "?"}</span>
                <span className="rounded bg-slate-800 px-1.5 text-[0.6rem] text-slate-400">
                  {c.country}
                </span>
                {c.link ? (
                  <a
                    href={c.link}
                    target="_blank"
                    rel="noreferrer"
                    className="text-slate-300 underline decoration-slate-700 hover:text-slate-100"
                  >
                    {c.title}
                  </a>
                ) : (
                  <span className="text-slate-300">{c.title}</span>
                )}
              </div>
            ))}
          </div>
        </Panel>
      )}

      {d.unavailable.length > 0 && (
        <p className="text-[0.68rem] text-rose-400">
          Degraded: {d.unavailable.join(", ")} — the rest of the brief is unaffected.
        </p>
      )}
      <p className="mt-3 text-[0.62rem] leading-relaxed text-slate-600">{d.note}</p>
    </main>
  );
}
