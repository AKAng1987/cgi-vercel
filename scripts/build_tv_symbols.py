"""
build_tv_symbols.py -- resolve every backtest-universe ticker that has no explicit
TradingView symbol to its real EXCHANGE:TICKER, and write api/tv_symbols.json.

WHY
watchlists.tv_symbol() answered "AMEX:<ticker>" for anything it did not recognise.
125 of the 173 universe tickers fell through to that guess, and a guess that is
wrong fails silently inside TradingView: IBB and SHY are NASDAQ, INDA is CBOE,
XAUUSD is spot gold on OANDA. The earning-it list broke the same way (every stock
on AMEX). This resolves them once, from TradingView's own public symbol search, so
nothing is guessed at run time. No API key, no LLM tokens.

RULES
  * the result's symbol must equal the ticker exactly
  * US ETFs/stocks: first match on a US venue, in TradingView's own relevance order
  * anything else (no US listing, ambiguous) is REPORTED, never defaulted

  python3 scripts/build_tv_symbols.py            # writes api/tv_symbols.json
  python3 scripts/build_tv_symbols.py --check    # offline: every ticker has an entry
"""
from __future__ import annotations

import json
import pathlib
import sys
import time
import types
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
API = ROOT / "api"
OUT = API / "tv_symbols.json"
sys.path.insert(0, str(API))
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))

US_VENUES = ("NASDAQ", "NYSE", "AMEX", "CBOE", "NYSEARCA", "ARCA")
SEARCH = "https://symbol-search.tradingview.com/symbol_search/v3/?"

# Our label is not always a ticker. metrics-source.source_symbol says what each one
# really is, and matching the label by name would land on the wrong instrument.
#
# Set explicitly, each with its evidence. Continuous-futures symbols do not surface
# in plain-text search, so their ROOT was verified through TradingView's own search
# (COMEX:GC "Gold Futures", ICEUS:CT "Cotton No. 2 Futures", CBOT:ZR "Rough Rice
# Futures") and the prefix is mandatory: bare ZR also exists as ICEUS:ZR, which is
# rand futures.
OVERRIDES = {
    "DJI": "TVC:DJI",            # Dow Jones Industrial Average (index)
    "IXIC": "NASDAQ:IXIC",       # NASDAQ Composite (index)
    "XAUUSD": "COMEX:GC1!",      # source GC=F, gold futures (~4,162, not an AMEX security)
    "COTTON": "ICEUS:CT1!",      # source CT=F, cotton futures
    "RICE": "CBOT:ZR1!",         # source ZR=F, rough rice futures (not the AMEX guess)
}
# our label -> the real ETF ticker (metrics-source.source_symbol), resolved normally
SOURCE_TICKER = {"LITHIUM": "LIT", "NICKEL": "NIKL", "URANIUM": "URA"}
# Universe tickers that cannot be put on a TradingView chart. Recorded WITH the reason, so a
# missing entry is a decision and not an oversight, and --check can tell the two apart.
UNPLACEABLE: dict[str, str] = {}
# (empty on purpose: PBS, JJC, JJN, PIN, BJK, VICE and CNCR were the unplaceable names,
# and they were retired from the universe instead -- see dashboard_data.RETIRED_TICKERS.)


def _ensure_api_env() -> None:
    """Re-run under api/.venv if this interpreter cannot import the API (the system
    python3 here has a broken numpy). Same self-locating rule as check_api_imports."""
    import os
    try:
        import pandas  # noqa: F401
    except Exception:
        venv = API / ".venv" / "bin" / "python"
        if venv.exists() and not os.environ.get("_CGI_TV_REEXEC"):
            os.environ["_CGI_TV_REEXEC"] = "1"
            os.execv(str(venv), [str(venv), __file__, *sys.argv[1:]])
        sys.exit("FAIL: cannot import the API and api/.venv was not found -- this check did NOT run")


def needs_resolution() -> list[tuple[str, str]]:
    _ensure_api_env()
    import backtest_data as bd
    import watchlists as wl
    tickers, groups = bd.build_backtest_universe()
    # FX and CRYPTO are NOT excluded: they used to be, with a group-level fallback
    # (FX -> FX_IDC:<t>, CRYPTO -> BITSTAMP:<t>USD) that was right for currency pairs and
    # wrong for ETFs filed under those groups -- UUP became FX_IDC:UUP and BITO became
    # BITSTAMP:BITOUSD, and neither exists.
    return [(t, groups[t]) for t in tickers if t not in wl.TV]


def search(ticker: str) -> list[dict]:
    q = urllib.parse.urlencode({"text": ticker, "hl": "0", "exchange": "", "lang": "en",
                                "search_type": "", "domain": "production"})
    req = urllib.request.Request(SEARCH + q, headers={
        "Origin": "https://www.tradingview.com", "Referer": "https://www.tradingview.com/",
        "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8")).get("symbols", [])


PAIR_VENUES = ("FX_IDC", "OANDA", "FX", "FOREXCOM")


def is_pair(ticker: str) -> bool:
    """A spot currency pair like USDKRW (USD plus a three-letter code), as opposed to
    an ETF that merely sits in the FX group (UUP) or a crypto fund (BITO)."""
    return len(ticker) == 6 and ticker.startswith("USD") and ticker.isalpha()


def resolve(ticker: str) -> tuple[str | None, str]:
    hits = [s for s in search(ticker) if s.get("symbol") == ticker]
    if is_pair(ticker):
        by = {(s.get("prefix") or s.get("exchange")): s for s in hits if s.get("type") == "forex"}
        for v in PAIR_VENUES:
            if v in by:
                return f"{v}:{ticker}", by[v].get("description", "")
        return None, "pair not found on an FX venue"
    us = [s for s in hits if (s.get("prefix") or s.get("exchange")) in US_VENUES
          and s.get("type") in ("fund", "stock", "dr", "etf", None, "")]
    if us:
        s = us[0]
        return f"{s.get('prefix') or s.get('exchange')}:{ticker}", s.get("description", "")
    if hits:
        s = hits[0]
        return None, f"no US listing; first hit {s.get('prefix') or s.get('exchange')}:{ticker} ({s.get('type')}) {s.get('description', '')}"
    return None, "no exact match"


def main() -> int:
    todo = needs_resolution()
    if "--check" in sys.argv:
        have = json.loads(OUT.read_text()) if OUT.exists() else {"symbols": {}, "unplaceable": {}}
        known = set(have["symbols"]) | set(have["unplaceable"])
        missing = [t for t, _ in todo if t not in known]
        if missing:
            print(f"FAIL: {len(missing)} universe tickers have no TradingView symbol: {missing}\n"
                  f"      run: python3 scripts/build_tv_symbols.py")
            return 1
        print(f"OK: all {len(todo)} unmapped universe tickers have a TradingView symbol")
        return 0

    old = json.loads(OUT.read_text()) if OUT.exists() else {}
    out = dict(old.get("symbols", old if "symbols" not in old else {}))
    out.update(OVERRIDES)
    unresolved = {}
    for i, (t, g) in enumerate(todo, 1):
        if t in out or t in UNPLACEABLE:
            continue
        try:
            sym, note = resolve(SOURCE_TICKER.get(t, t))
        except Exception as exc:  # noqa: BLE001
            sym, note = None, f"lookup failed: {exc}"
        if sym:
            out[t] = sym
        else:
            unresolved[t] = f"{g}: {note}"
        print(f"[{i:3d}/{len(todo)}] {t:8s} {g:20s} -> {sym or 'UNRESOLVED':16s} {note[:60]}", flush=True)
        time.sleep(0.25)
    OUT.write_text(json.dumps({"symbols": dict(sorted(out.items())),
                               "unplaceable": dict(sorted(UNPLACEABLE.items()))}, indent=1) + "\n")
    print(f"\nwrote {OUT.name}: {len(out)} resolved, {len(UNPLACEABLE)} unplaceable (recorded), {len(unresolved)} unresolved")
    for t, why in unresolved.items():
        print(f"  UNRESOLVED {t}: {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
