"""
watchlists.py -- The two TradingView watchlists CGI maintains, as data:

  CGI · now            best 20 / worst 10 of the BACKTEST leaderboard, current regime
  CGI · if next flips  same for the regime we land in if the next release flips its axis

Served at /api/watchlists (24h cache) so a scheduled cloud routine with the
TradingView connector can rewrite the lists without AWS access. Symbols
are EXCHANGE:TICKER as TradingView wants them; "###..." entries are
section headers. Mirror of market-dashboard/scripts/cgi_watchlists.py.
"""
from __future__ import annotations

import datetime as dt

import backtest_data as bd
import markov_data as md
import release_calendar as cal

TOP, BOTTOM, MIN_OCC = 20, 10, 5
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


def tv_symbol(ticker: str, group: str) -> str:
    if ticker in TV:
        return TV[ticker]
    g = group.upper()
    if g == "FX":
        return f"FX_IDC:{ticker}"
    if g == "CRYPTO":
        return f"BITSTAMP:{ticker}USD"
    if "ETF" in g or g in ("SECTOR ETF", "COUNTRY ETF", "US EQUITIES"):
        return f"AMEX:{ticker}"
    return f"AMEX:{ticker}"


def leaderboard(c: int, g: int, min_occ: int) -> list[dict]:
    t = bd.build_table_response(c, g, min_occ=min_occ)
    rows = [r for r in t["rows"] if r.get("edge") is not None]
    rows.sort(key=lambda r: -r["edge"])
    return rows




def build_watchlists_response() -> dict:
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    cur = {m: md._load_model(f"{m}_US")[-1][1] for m in ("compass", "grid")}
    nxt = sorted(cal.next_releases(today), key=lambda r: r["date"])[0]
    axis, model = nxt["axis"], nxt["model"]
    s = cal.Q_TO_AXES[cur[model]][cal.SLOT_OF[axis]]
    dest = dict(cur)
    dest[model] = md._quadrant_with(cur[model], axis, 1 - s)

    out = []
    for name, reg, note in (
        ("CGI · now", cur, "current regime"),
        ("CGI · if next flips", dest, f"if {nxt['type']} on {nxt['date']} flips {axis}"),
    ):
        min_occ = MIN_OCC
        rows = leaderboard(reg["compass"], reg["grid"], min_occ)
        if len(rows) < 5 and min_occ > 3:
            min_occ = 3
            rows = leaderboard(reg["compass"], reg["grid"], min_occ)
        best = rows[:TOP]
        worst = rows[TOP:][-BOTTOM:] if len(rows) > TOP else []
        label = f"C{reg['compass']}G{reg['grid']}"
        thin = f" (thin: {min_occ}+ occurrences)" if min_occ < MIN_OCC else ""
        keep = lambda rs: [{k: r[k] for k in ("ticker", "group", "occurrences", "hit_rate", "edge", "avg_return_pct")} for r in rs]
        out.append({
            "name": name, "watchlist_id": WATCHLIST_IDS[name], "regime": label, "note": note, "min_occ": min_occ,
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
        ranked = sorted(
            (c for c in fund.get("companies", [])
             if not c.get("annual_only")
             and (c.get("revenue") or {}).get("acceleration_pp") is not None),
            key=lambda c: -c["revenue"]["acceleration_pp"])[:EARNING_IT]
        if ranked:
            out.append({
                "name": "CGI · earning it",
                "watchlist_id": WATCHLIST_IDS["CGI · earning it"],
                "regime": "fundamentals",
                "note": f"top {len(ranked)} by revenue acceleration, quarterly filers only",
                "min_occ": None,
                "symbols": ([f"###EARNING IT · TOP {len(ranked)} BY REVENUE ACCELERATION"]
                            + [tv_symbol(c["symbol"], "EQUITY") for c in ranked]),
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
