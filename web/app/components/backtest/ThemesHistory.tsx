"use client";

import { RunHistory } from "../history/RunHistory";
import history from "./themes_history.json";

/** Themes in play, retroactively (Backtest tab). Shared picker: ../history/RunHistory. */
export function ThemesHistory() {
  return (
    <RunHistory
      data={history}
      title="Themes in play, retroactively"
      nameCol="Theme"
      totalCol="Legs running"
      noun="themes"
      withFullGrid
      caveat={
        <>
          Reconstructed with today&rsquo;s theme legs (extended 2026-10-09), so this is not a stored copy of what CGI showed then. A run starts
          where the current stretch above its 200-day relative-strength trend began, with dips under 15 calendar days merged into it, so a
          one-day dip no longer resets a mature theme&rsquo;s age. Stage cut-offs (55 and 152 days) and the megatrend rule (over 365 days) were
          measured on the full history, so older months are slightly flattered by hindsight.
        </>
      }
    />
  );
}
