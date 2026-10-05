"""
tv_symbols.py -- CGI ticker -> TradingView EXCHANGE:TICKER, in one place.

Used by the watchlists (which symbols to write into TradingView) and by the LIVE page's
click-to-chart (which instrument to chart). Both must agree, and both used to guess.
It is its own module because backtest_data and mixture need it and must not import
watchlists (watchlists imports backtest_data).

The data is api/tv_symbols.json, built by scripts/build_tv_symbols.py from TradingView's
own symbol search. A ticker with no entry returns None: callers leave it out or fall back
to the bare ticker, they never guess an exchange.
"""
from __future__ import annotations

import functools
import json
import pathlib

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
