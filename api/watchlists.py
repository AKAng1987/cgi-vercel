"""
watchlists.py -- The two TradingView watchlists CGI maintains, as data:

  CGI · now            best 20 / worst 20 of the BACKTEST leaderboard, current regime
  CGI · if next flips  same for the regime we land in if the next release flips its axis

Served at /api/watchlists (24h cache) so a scheduled cloud routine with the
TradingView connector can rewrite the lists without AWS access. Symbols
are EXCHANGE:TICKER as TradingView wants them; "###..." entries are
section headers. Mirror of market-dashboard/scripts/cgi_watchlists.py.
"""
from __future__ import annotations

import datetime as dt
import functools
import json
import pathlib
import urllib.request

import backtest_data as bd
import markov_data as md
import release_calendar as cal

TOP, BOTTOM, MIN_OCC = 20, 20, 5
WATCHLIST_IDS = {"CGI · now": "347463015", "CGI · if next flips": "347463028",
                 "CGI · earning it": "348364949"}

# The fundamentals list is capped hard. The regime lists already run to 30
# symbols each and the user asked for the total to stop growing; 15 names is
# enough to see who is actually earning a theme without adding another 30.
EARNING_IT = 15

# CGI ticker -> TradingView symbol. Exchanges follow the user's own lists.
TV = {
    "VIX": "TVC:VIX", "SPX": "TVC:SPX", "SPY": "AMEX:SPY", "QQQ": "NASDAQ:QQQ", "IWM": "AMEX:IWM", "DIA": "AMEX:DIA",
    "RUT": "TVC:RUT", "DXY": "TVC:DXY", "TLT": "NASDAQ:TLT", "IEF": "NASDAQ:IEF", "HYG": "AMEX:HYG", "LQD": "AMEX:LQD",
    "GLD": "AMEX:GLD", "GDX": "AMEX:GDX", "SLV": "AMEX:SLV", "USO": "AMEX:USO", "UNG": "AMEX:UNG", "DBC": "AMEX:DBC",
    "DBA": "AMEX:DBA", "USCI": "AMEX:USCI", "CPER": "AMEX:CPER", "COPPER": "COMEX:HG1!", "NATGAS": "NYMEX:NG1!", "GOLD": "TVC:GOLD", "SILVER": "TVC:SILVER", "USOIL": "TVC:USOIL",
    "BTC": "BITSTAMP:BTCUSD", "ETH": "BITSTAMP:ETHUSD",
    "USDSGD": "OANDA:USDSGD", "USDTHB": "OANDA:USDTHB", "USDCAD": "OANDA:USDCAD", "USDJPY": "FX:USDJPY",
    "USDCHF": "FX:USDCHF", "USDMXN": "FX:USDMXN", "USDTRY": "FX:USDTRY",
}


_TV_FILE = pathlib.Path(__file__).with_name("tv_symbols.json")


@functools.lru_cache(maxsize=1)
def _tv_data() -> dict:
    return json.loads(_TV_FILE.read_text())


def tv_symbol(ticker: str, group: str) -> str | None:
    """EXCHANGE:TICKER for a universe ticker, or None when it cannot be placed.

    This used to end in `return f"AMEX:{ticker}"` for anything unrecognised. 125 of
    the 173 universe tickers reached that line, and a wrong exchange fails silently
    inside TradingView (IBB and SHY are NASDAQ, INDA is CBOE, XAUUSD is gold futures).
    Symbols now come from tv_symbols.json, built by scripts/build_tv_symbols.py from
    TradingView's own search -- FX and crypto included -- and a ticker with no entry is left
    out, never guessed.
    """
    if ticker in TV:
        return TV[ticker]
    sym = _tv_data()["symbols"].get(ticker)
    if sym:
        return sym
    # No group-level fallback. FX -> FX_IDC:<t> and CRYPTO -> BITSTAMP:<t>USD were right for
    # currency pairs and wrong for ETFs filed under those groups (UUP, BITO). Everything is
    # resolved into tv_symbols.json, and a ticker without an entry is left out and reported.
    return None


def placeable(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Rows that can be put on a TradingView list, and the tickers that cannot."""
    ok = [r for r in rows if tv_symbol(r["ticker"], r["group"])]
    return ok, sorted({r["ticker"] for r in rows} - {r["ticker"] for r in ok})


SEC_EXCHANGES_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_UA = "CGI macro-regime research (ang.arvin@ymail.com)"     # same identity sec_xbrl uses
# SEC's exchange name -> TradingView's prefix. Anything else (None, unknown) is
# NOT guessed: see equity_tv_symbol.
SEC_TO_TV = {"Nasdaq": "NASDAQ", "NYSE": "NYSE", "CBOE": "CBOE", "OTC": "OTC"}


def fetch_sec_exchanges() -> dict[str, str]:
    """ticker -> TradingView exchange prefix, for every US-listed ticker the SEC knows.

    Fetched at run time rather than kept as a map: the fundamentals universe is
    derived from the theme ETFs' holdings and changes, so a hand-built table would
    go stale the first time a holding does -- which is exactly how this list ended
    up with every stock on AMEX.
    """
    req = urllib.request.Request(SEC_EXCHANGES_URL, headers={"User-Agent": SEC_UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    ix = {f: i for i, f in enumerate(d["fields"])}
    out = {}
    for row in d["data"]:
        exch = SEC_TO_TV.get(row[ix["exchange"]])
        if exch:
            # SEC writes share classes as BRK-B; TradingView as BRK.B
            out[row[ix["ticker"]].replace("-", ".")] = exch
    return out


def equity_tv_symbol(ticker: str, exchanges: dict[str, str]) -> str | None:
    """EXCHANGE:TICKER for a stock, or None when the exchange is not known.

    The old code answered 'AMEX:' for anything it did not recognise, so MU, NVDA,
    AVGO and the rest of the earning-it list pointed at a venue none of them trade
    on and TradingView would not load them. A symbol we cannot place is left out
    and reported; a wrong one fails silently inside TradingView.
    """
    exch = exchanges.get(ticker.replace("-", "."))
    return f"{exch}:{ticker.replace('-', '.')}" if exch else None


def pick_earning(candidates: list[dict], exchanges: dict[str, str], n: int) -> tuple[list[dict], list[str], list[str]]:
    """First n ranked companies that can be placed on a major exchange.

    Walks down the ranking, so a name that cannot be placed or is excluded costs the next
    one a slot instead of leaving a gap. Returns (picked, unresolved, excluded_otc).
    """
    picked, unresolved, excluded_otc = [], [], []
    for c in candidates:
        sym = equity_tv_symbol(c["symbol"], exchanges)
        if not sym:
            unresolved.append(c["symbol"])
        elif sym.startswith("OTC:"):
            # The user does not trade over-the-counter names, so a revenue-acceleration
            # screen should not surface them (FGRS, 2026-10-04). Reported, not hidden, and not
            # a hard-coded ticker: the exchange is read at run time, so a name that later
            # lists on Nasdaq/NYSE rejoins on its own.
            excluded_otc.append(c["symbol"])
        else:
            picked.append(c)
            if len(picked) == n:
                break
    return picked, unresolved, excluded_otc


def leaderboard(c: int, g: int, min_occ: int) -> list[dict]:
    t = bd.build_table_response(c, g, min_occ=min_occ)
    rows = [r for r in t["rows"] if r.get("edge") is not None]
    rows.sort(key=lambda r: -r["edge"])
    return rows




def next_regimes(today: str) -> tuple[dict, dict, dict]:
    """(current regime, regime if the next release flips its axis, that release).

    One definition, used by the watchlists AND the mixture layer, so the two
    can never disagree about which regime is "next". Each release moves exactly
    one axis, so the destination differs from now in a single quadrant.
    """
    cur = {m: md._load_model(f"{m}_US")[-1][1] for m in ("compass", "grid")}
    nxt = sorted(cal.next_releases(today), key=lambda r: r["date"])[0]
    axis, model = nxt["axis"], nxt["model"]
    s = cal.Q_TO_AXES[cur[model]][cal.SLOT_OF[axis]]
    dest = dict(cur)
    dest[model] = md._quadrant_with(cur[model], axis, 1 - s)
    return cur, dest, nxt


def build_watchlists_response() -> dict:
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    cur, dest, nxt = next_regimes(today)
    axis = nxt["axis"]

    out = []
    for name, reg, note in (
        ("CGI · now", cur, "current regime"),
        ("CGI · if next flips", dest, f"if {nxt['type']} on {nxt['date']} flips {axis}"),
    ):
        min_occ = MIN_OCC
        # Ranked names that cannot be put on a TradingView list (delisted, or no
        # symbol) are dropped BEFORE the top/bottom cut, so the lists still hold 20
        # tradeable names each rather than 20 minus whatever could not load.
        rows, skipped = placeable(leaderboard(reg["compass"], reg["grid"], min_occ))
        if len(rows) < 5 and min_occ > 3:
            min_occ = 3
            rows, skipped = placeable(leaderboard(reg["compass"], reg["grid"], min_occ))
        best = rows[:TOP]
        worst = rows[TOP:][-BOTTOM:] if len(rows) > TOP else []
        label = f"C{reg['compass']}G{reg['grid']}"
        thin = f" (thin: {min_occ}+ occurrences)" if min_occ < MIN_OCC else ""
        keep = lambda rs: [{k: r[k] for k in ("ticker", "group", "occurrences", "hit_rate", "edge", "avg_return_pct")} for r in rs]
        out.append({
            "name": name, "watchlist_id": WATCHLIST_IDS[name], "regime": label, "note": note, "min_occ": min_occ,
            "unplaceable": skipped,
            "symbols": ([f"###{label} · BEST {len(best)} · {note.upper()}{thin}"]
                        + [tv_symbol(r["ticker"], r["group"]) for r in best]
                        + [f"###{label} · WORST {len(worst)}"]
                        + [tv_symbol(r["ticker"], r["group"]) for r in worst]),
            "best": keep(best), "worst": keep(worst),
        })
    # CGI · earning it -- the fundamentals view, top N by revenue acceleration.
    # Annual filers are excluded: their acceleration is measured over a year
    # and ranking them against quarterly names would be comparing two different
    # quantities. Guarded so a fundamentals outage costs this list, not the
    # regime lists beside it.
    try:
        import cache as _cache
        import fundamentals_data as _fd
        fund = _cache.get("fundamentals") or _fd.build_fundamentals_response()
        exchanges = _cache.get_or_fetch("sec_exchanges", fetch_sec_exchanges)
        candidates = sorted(
            (c for c in fund.get("companies", [])
             if not c.get("annual_only")
             and (c.get("revenue") or {}).get("acceleration_pp") is not None),
            key=lambda c: -c["revenue"]["acceleration_pp"])
        # Walk down the ranking until EARNING_IT names that can actually be placed
        # on an exchange, so one unresolvable ticker costs a slot to the next name,
        # not a broken row. What was skipped is returned, not hidden.
        ranked, unresolved, excluded_otc = pick_earning(candidates, exchanges, EARNING_IT)
        if ranked:
            out.append({
                "name": "CGI · earning it",
                "watchlist_id": WATCHLIST_IDS["CGI · earning it"],
                "regime": "fundamentals",
                "note": f"top {len(ranked)} by revenue acceleration, quarterly filers only",
                "min_occ": None,
                "unresolved": unresolved,
                "excluded_otc": excluded_otc,
                "symbols": ([f"###EARNING IT · TOP {len(ranked)} BY REVENUE ACCELERATION"]
                            + [equity_tv_symbol(c["symbol"], exchanges) for c in ranked]),
                "best": [{"ticker": c["symbol"],
                          "acceleration_pp": c["revenue"]["acceleration_pp"],
                          "yoy_pct": c["revenue"].get("yoy_pct"),
                          "verdict": c["read"]["verdict"]} for c in ranked],
                "worst": [],
            })
    except Exception:
        import logging
        logging.getLogger("cgi_api.watchlists").exception(
            "[watchlists] earning-it list unavailable; regime lists unaffected")

    return {"as_of": today, "current": cur, "next_release": {"date": nxt["date"], "type": nxt["type"], "axis": axis},
            "watchlists": out}
