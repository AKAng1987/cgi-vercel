import { apiFetch } from "@/lib/api";
import { ThemesResponse, SignalsResponse, BacktestTableResponse, LiveResponse, TechnicalsResponse } from "@/lib/types";
import { RegimeCard } from "./components/RegimeCard";
import { EdgeStrip } from "./components/brief/EdgeStrip";
import { BreadthStrip } from "./components/brief/BreadthStrip";
import { StandingTheme } from "./components/brief/StandingTheme";
import { ThemesTable } from "./components/brief/ThemesTable";
import { COMPASS_Q_LABELS, GRID_Q_LABELS } from "@/lib/regimeConstants";

/**
 * LIVE -- the brief. Layered by clock speed, slowest on top:
 *   1 standing theme   ~1y, changed only on a deliberate monthly review
 *   2 themes in force  weeks-months, detected from RS persistence
 *   3 edge             per regime, from the backtest
 * The raw overnight scan moved to /tape; this page is what you open first.
 */
export default async function Live() {
  const [themes, signals, live, tech] = await Promise.all([
    apiFetch<ThemesResponse>("/api/themes"),
    apiFetch<SignalsResponse>("/api/signals?limit=1"),
    apiFetch<LiveResponse>("/api/live"),
    apiFetch<TechnicalsResponse>("/api/technicals").catch(() => null),
  ]);

  const sig = signals.signals?.[0];
  const cq = sig?.compass.current ?? null;
  const gq = sig?.grid.current ?? null;

  let edge: BacktestTableResponse | null = null;
  if (cq && gq) {
    try {
      edge = await apiFetch<BacktestTableResponse>(`/api/backtest/${cq}/${gq}?min_occ=5`);
    } catch {
      edge = null;
    }
  }
  const ranked = (edge?.rows ?? []).filter((r) => r.edge !== null);
  const top = ranked.slice(0, 20);
  const worst = ranked.length > 20 ? ranked.slice(-10).reverse() : [];

  return (
    <main className="mx-auto max-w-6xl p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h1 className="text-2xl font-bold">LIVE</h1>
        <div className="text-xs text-slate-500">
          {cq && gq && (
            <>
              regime{" "}
              <span className="font-semibold text-slate-200">
                C{cq}G{gq}
              </span>{" "}
              · {COMPASS_Q_LABELS[cq]} × {GRID_Q_LABELS[gq]} ·{" "}
            </>
          )}
          themes as of {themes.as_of}
        </div>
      </div>

      <section className="mb-5 grid grid-cols-1 gap-4 md:grid-cols-2">
        <RegimeCard kind="compass" data={live.compass} />
        <RegimeCard kind="grid" data={live.grid} />
      </section>

      {tech && <BreadthStrip t={tech} />}

      <StandingTheme themes={themes.standing} />
      <ThemesTable themes={themes.themes} runStats={themes.run_stats} />

      {top.length > 0 && cq && gq && (
        <EdgeStrip best={top} worst={worst} cq={cq} gq={gq} />
      )}

      <p className="text-[0.68rem] leading-relaxed text-slate-600">
        The standing theme does not move when the regime rotates — that is the point. If the
        rotation disagrees with it, the disagreement is the information: either the theme is
        breaking or the rotation is noise. Promotion and removal happen on the monthly review,
        not here. Overnight and weekly moves are on <a href="/tape" className="underline">TAPE</a>.
      </p>
    </main>
  );
}
