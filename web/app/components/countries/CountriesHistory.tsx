"use client";

import { RunHistory } from "../history/RunHistory";
import history from "./countries_history.json";

/** Countries in force, retroactively (Countries tab). Same detector and picker as the themes history. */
export function CountriesHistory() {
  return (
    <RunHistory
      data={history}
      title="Countries in force, retroactively"
      nameCol="Country"
      totalCol="ETFs running"
      noun="countries"
      caveat={
        <>
          The same detector as Themes in force, run on each country&rsquo;s equity ETFs against SPY as of each month end. A country is in
          force while any of its ETFs is in a run, and its age is the oldest running ETF&rsquo;s. Reconstructed with today&rsquo;s ETF list,
          using the full-history stage cut-offs (55 and 152 days) and the megatrend rule (over 365 days), so older months are slightly
          flattered by hindsight.
        </>
      }
    />
  );
}
