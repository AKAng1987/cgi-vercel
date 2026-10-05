/**
 * The three TradingView watchlists CGI keeps in sync (api/watchlists.py), and how to link to them.
 *
 * Ids are NOT hard-coded here: they come from /api/watchlists, so a re-created list or a new id
 * cannot leave a dead link behind. The names ARE matched, so they must equal WATCHLIST_IDS in
 * api/watchlists.py; a name that does not match simply yields no link rather than a wrong one.
 */
export interface TvList {
  name: string;
  watchlist_id: string;
  regime: string;
  note: string;
}

export interface WatchlistsResponse {
  watchlists: TvList[];
}

export const LIST_NOW = "CGI · now";
export const LIST_FLIP = "CGI · if next flips";
export const LIST_EARN = "CGI · earning it";

export function tvListUrl(id: string): string {
  return `https://www.tradingview.com/watchlists/${id}/`;
}

export function findList(lists: WatchlistsResponse | null | undefined, name: string): TvList | undefined {
  return lists?.watchlists?.find((w) => w.name === name);
}
