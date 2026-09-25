"""
liquidity_data.py -- global liquidity, in the spirit of Michael Howell.

WHAT HOWELL ARGUES, AND WHY IT BELONGS HERE
Markets are driven by the QUANTITY of liquidity rather than the price of it.
The dominant use of that liquidity is refinancing existing debt, not funding
new investment -- roughly $350tn of world debt on a ~5-year average maturity
means something like $70tn must be rolled every year, which is why the
quantity outranks the interest rate. And the dollar is the transmission
channel: a stronger dollar makes offshore dollar debt harder to service and
drains global liquidity.

CGI's LIQUIDITY axis is the domestic policy rate (DFEDTARU) and the front of
the curve. That is the price of money. This module is the quantity, and the
two are meant to be read together rather than one replacing the other.

WHAT THIS IS NOT
It is NOT Howell's index. CrossBorder Capital's collateral multiplier and
private-liquidity series are assembled from licensed dealer, repo and custody
data that cannot be reconstructed from public sources. Everything here is free
FRED data, and it is labelled a proxy everywhere it appears. Treating it as
his number would be borrowing an authority this does not have.

THE MEASURES
  net liquidity     WALCL - WTREGEN - RRPONTSYD. The Fed's balance sheet less
                    the Treasury's cash box and the reverse-repo drain --
                    what is actually available to the system rather than what
                    the Fed nominally holds.
  reserves          WRESBAL, the banking system's own cushion.
  global CB assets  Fed + ECB + BOJ, each converted to USD. The conversion is
                    not an inconvenience, it is the mechanism: a stronger
                    dollar shrinks the rest of the world's balance sheets in
                    dollar terms, which is Howell's point expressed in
                    arithmetic.
  collateral proxy  SOFR - IORB. When secured funding trades above what the
                    Fed pays on reserves, collateral is scarce. It is a
                    stress gauge, not the multiplier.

UNITS, WHICH ARE A REAL TRAP
FRED publishes WALCL and WRESBAL in millions of USD, ECBASSETSW in millions of
EUR, and JPNASSETS in hundred-millions of JPY. They are normalised to USD
billions here. The sum is therefore only as good as that normalisation, which
is why each component is reported alongside the total rather than folded away.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

import axis_drivers as ad

_logger = logging.getLogger("cgi_api.liquidity_data")

# series -> (multiplier to USD billions, needs FX conversion from)
SCALE = {
    "WALCL": (1e-3, None),        # USD millions -> USD bn
    "WTREGEN": (1e-3, None),
    "RRPONTSYD": (1.0, None),     # already USD bn
    "WRESBAL": (1e-3, None),
    "ECBASSETSW": (1e-3, "USDEUR"),   # EUR millions -> EUR bn -> USD bn
    # FRED publishes JPNASSETS in HUNDRED-MILLIONS of yen, so the step to yen
    # billions is x1e8/1e9 = x0.1. An earlier 1e-4 here put the BOJ's balance
    # sheet at $4.1bn instead of $4.1tn -- a thousand-fold error that would
    # have quietly made the global aggregate meaningless while still looking
    # like a number.
    "JPNASSETS": (1e-1, "USDJPY"),
}


def _load(sym: str) -> dict[str, float]:
    try:
        d, c = ad._load_close(sym)
        return {k: v for k, v in zip(d, c) if v is not None}
    except Exception:
        _logger.warning("[liquidity] %s unavailable", sym)
        return {}


def _latest(s: dict[str, float]) -> Optional[tuple[str, float]]:
    return (max(s), s[max(s)]) if s else None


def _asof(s: dict[str, float], date: str) -> Optional[float]:
    ds = [d for d in s if d <= date]
    return s[max(ds)] if ds else None


def _chg(s: dict[str, float], days: int) -> Optional[float]:
    if not s:
        return None
    last = max(s)
    prior = (dt.date.fromisoformat(last) - dt.timedelta(days=days)).isoformat()
    a, b = s[last], _asof(s, prior)
    return None if (b is None or not b) else (a - b)


def build_liquidity_response() -> dict:
    raw = {k: _load(k) for k in SCALE}
    fx = {"USDEUR": _load("USDEUR"), "USDJPY": _load("USDJPY")}

    # Convert to USD billions on each series' own dates.
    usd: dict[str, dict[str, float]] = {}
    for sym, (mult, fx_sym) in SCALE.items():
        out = {}
        for d, v in raw[sym].items():
            x = v * mult
            if fx_sym:
                rate = _asof(fx[fx_sym], d)
                if not rate:
                    continue
                # USDEUR / USDJPY are quoted as units of foreign per USD, so a
                # foreign-currency balance sheet is DIVIDED to reach USD.
                x = x / rate
            out[d] = x
        usd[sym] = out

    # Net liquidity, on the Fed's own weekly dates.
    net = {}
    for d, walcl in usd["WALCL"].items():
        tga = _asof(usd["WTREGEN"], d)
        rrp = _asof(usd["RRPONTSYD"], d)
        if tga is None or rrp is None:
            continue
        net[d] = walcl - tga - rrp

    # Global central bank assets, on the Fed's dates.
    glob = {}
    for d in usd["WALCL"]:
        parts = [usd["WALCL"].get(d), _asof(usd["ECBASSETSW"], d), _asof(usd["JPNASSETS"], d)]
        if all(p is not None for p in parts):
            glob[d] = sum(parts)

    sofr, iorb = _load("SOFR"), _load("IORB")
    spread = {d: (sofr[d] - iorb[d]) * 100 for d in set(sofr) & set(iorb)}  # bp

    def block(name, s, unit):
        l = _latest(s)
        return {
            "name": name, "unit": unit,
            "as_of": l[0] if l else None,
            "latest": round(l[1], 1) if l else None,
            "chg_30d": round(_chg(s, 30), 1) if _chg(s, 30) is not None else None,
            "chg_90d": round(_chg(s, 90), 1) if _chg(s, 90) is not None else None,
            "chg_365d": round(_chg(s, 365), 1) if _chg(s, 365) is not None else None,
            "n_points": len(s),
        }

    return {
        "as_of": dt.date.today().isoformat(),
        "proxy_notice": ("A PROXY built from free FRED data, not Michael Howell's index. "
                         "CrossBorder Capital's collateral multiplier and private-liquidity "
                         "series use licensed dealer, repo and custody data that cannot be "
                         "reconstructed from public sources."),
        "reading": ("CGI's LIQUIDITY axis is the PRICE of money (the policy rate and the front "
                    "of the curve). This is the QUANTITY. Read them together: hikes into a "
                    "shrinking balance sheet are a different regime from hikes into an "
                    "expanding one."),
        "us_net_liquidity": block("US net liquidity (WALCL - TGA - RRP)", net, "USD bn"),
        "reserve_balances": block("Reserve balances (WRESBAL)", usd["WRESBAL"], "USD bn"),
        "global_cb_assets": block("Fed + ECB + BOJ assets, in USD", glob, "USD bn"),
        "components": {k: block(k, usd[k], "USD bn") for k in SCALE},
        "collateral_stress": block("SOFR - IORB", spread, "bp"),
        "dollar_channel": ("A stronger dollar shrinks foreign balance sheets in USD terms and "
                           "makes offshore dollar debt harder to service -- which is why the "
                           "FX conversion above is the mechanism, not a units chore."),
        "limits": [
            "FRED units differ per series (USD millions, EUR millions, JPY hundred-millions); each component is shown beside the total so the normalisation can be checked.",
            "The PBoC is absent -- it publishes no usable free series -- so 'global' means Fed + ECB + BOJ only.",
            "Weekly and monthly series are carried forward to the Fed's weekly dates, so the newest value of a monthly series can be up to a month old.",
        ],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
