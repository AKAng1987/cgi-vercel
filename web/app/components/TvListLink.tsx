import { TvList, tvListUrl } from "@/lib/tvLists";

/**
 * A link to one of CGI's TradingView watchlists. Renders nothing when the list is unknown
 * (the API was unreachable, or the name changed) so a missing list never becomes a dead link.
 * `regime` is shown for the two regime lists ("C3G2"); the fundamentals list has none.
 */
export function TvListLink({ list, label }: { list?: TvList; label?: string }) {
  if (!list) return null;
  const showRegime = list.regime && list.regime !== "fundamentals";
  return (
    <a
      href={tvListUrl(list.watchlist_id)}
      target="_blank"
      rel="noopener noreferrer"
      title={`${list.name} in TradingView: ${list.note}`}
      className="underline hover:text-slate-300"
    >
      {label ?? list.name}
      {showRegime ? ` · ${list.regime}` : ""} ↗
    </a>
  );
}
