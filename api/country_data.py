"""
COUNTRIES tab: the per-country numbers behind the regime matrix.

The tab shipped first as a regime-only page. This module is the other half
the user asked for -- "a bit more numbers to it, like % returns, so as to see
it quicker and not just a narrative page", and "almost like a CGI model
without the labels and the dates, just rate of change".

So each country gets:
  * the macro block   -- policy rate, CPI YoY, GDP YoY, loan growth, each as
                         a LEVEL plus the change since the prior print
  * the market block  -- country ETF and USD pair returns across the standard
                         tenors, plus relative strength against SPY
  * the regime block  -- supplied by regime_matrix, unchanged

FREQUENCY IS MEASURED, NOT DECLARED
-----------------------------------
Every rate-of-change here derives its lag from the series' own observed bar
spacing. GBLPS publishes QUARTERLY where PHLPS and KRLPS publish monthly, and
reading it with a monthly 12-bar lag returns +11.19% against a true +7.34%.
A declaration can be wrong (that one was, in this repo, until it was checked);
the spacing between observations cannot.

WHAT THIS PAGE IS FOR
---------------------
Monitoring, not signal generation. The country-by-regime edge is not
statistically distinguishable from noise -- 7 of 250 cells clear |t|>2 where
chance alone predicts 12.5 -- so the regime block carries that caveat and the
macro block here is deliberately descriptive. A country's OWN growth/inflation
mix is reported as its own condition and kept visually apart from the US
regime the trade is actually conditioned on. Those are two different
statements and blurring them is the easiest mistake this page could make.
"""

from __future__ import annotations

import datetime as dt
import time
import statistics as st
from typing import Optional

import axis_drivers as ad
import regime_matrix
import themes_data as td

# Bumping this invalidates the "countries" cache automatically -- cache.py's
# SCHEMA_FROM_MODULE points at this constant precisely so the bump lives in the
# same file as the shape change. 2: added the curve block.
SCHEMA_VERSION = 13  # 13: JP/EU central-bank assets read from FRED-fed series; 12: currency_state (managed/pending/untracked) on every country; 11: six new USD pairs

BENCH = "SPY"

# Standard tenors, matching dashboard_data._LOOKBACK so a return on this page
# means the same thing as a return anywhere else on the site. 1d is the
# latest session -- without it the shortest read on the page was a month, and
# "what moved today" had no answer.
TENORS = {"1d": 1, "1m": 21, "3m": 63, "6m": 126, "1y": 252}

# The window the plain-English currency direction describes. Stated in the
# payload and printed on the page: "PHP stronger" with no period attached is
# exactly the ambiguity this label was meant to remove.
FX_DIRECTION_TENOR = "3m"

# symbol suffixes written by scripts/load_country_series.py
# kind decides how a year-on-year change is expressed, and getting it wrong
# produces confident nonsense:
#   "rate"  -- the series IS already a rate (5.0%, 6.1%). A year's change is a
#              DIFFERENCE in percentage points. Taking a ratio instead reports
#              CPI going 1.5 -> 6.1 as "+306%", which is the change in the
#              inflation rate and means nothing anybody wants to know.
#   "level" -- the series is a stock in local currency. A year's change is a
#              percentage.
MACRO = [
    ("policy_rate", "{c}_POLICY_RATE", "%", "policy rate", "rate"),
    ("cpi_yoy", "{c}_CPI_YOY", "%", "CPI YoY", "rate"),
    ("gdp_yoy", "{c}_GDP_YOY", "%", "GDP YoY", "rate"),
    ("loan_growth_yoy", "{c}_LOAN_GROWTH_YOY", "%", "loan growth YoY", "rate"),
    ("loans_level", "{c}_LOANS_PRIVATE", "local", "loans to private sector", "level"),
    ("m2", "{c}_M2", "local", "M2 money supply", "level"),
    # The other half of Howell's pair. Still a PROXY: no collateral
    # multiplier, no repo or dealer data, no cross-border weighting -- just
    # the central bank's own balance sheet in its own currency.
    ("cb_assets", "{c}_CB_ASSETS", "local", "central bank balance sheet", "level"),
]

# Curve tenors, in the existing US03MY / US01Y / US02Y / US10Y naming so they
# land in the FOREIGN RATES group that already declares PH10Y, JP10Y and the
# rest. A yield is reported as the YIELD -- the level is the thing being
# traded, and a "+0.25pp" with no base does not tell you whether 3m sits above
# or below the policy rate, which is the whole "what is priced in" read.
CURVE = [("3m", "{c}03MY"), ("1y", "{c}01Y"), ("2y", "{c}02Y"), ("10y", "{c}10Y")]

# Documented SUBSTITUTES, where no series exists for the country/tenor itself.
# The substitute is stored under its OWN name and named on the page -- storing
# a German yield as "EU10Y" would be the same class of error as a mining stock
# stored as "GOLD", and that one went unnoticed for 1,121 days.
#   (country, tenor) -> (symbol, what it actually is)
CURVE_SUBSTITUTE = {
    ("EU", "10y"): ("DE10Y", "German 10y, as the euro-area benchmark "
                             "(the OECD euro-area series stopped updating 2026-01)"),
    ("GB", "3m"): ("GBSONIA", "SONIA, an OVERNIGHT rate, as the UK front end "
                              "(the OECD UK 3-month series stopped updating 2026-01)"),
}

# Whether this country's policy rate and its front-end market rate are on the
# same footing, which is what makes "3m minus policy" mean anything.
#
# China is excluded: CNINTR is the Loan Prime Rate, a LENDING benchmark banks
# charge borrowers, while CN03MY is an interbank FUNDING rate. The funding rate
# sits structurally below the lending rate, so the gap is permanently negative
# and the naive read prints "market pricing CUTS" forever. That is an artifact
# of comparing two different kinds of rate, not a view about the PBoC.
POLICY_COMPARABLE = {
    "PH": True, "JP": True, "KR": True, "GB": True, "EU": True,
    "CN": False,
}
POLICY_INCOMPARABLE_WHY = {
    "CN": "CNINTR is the Loan Prime Rate (a lending benchmark); CN03MY is an "
          "interbank funding rate. They sit at structurally different levels, "
          "so the gap is not a policy expectation.",
}

# Local currency per country, for labelling levels. Getting this wrong is the
# BOJ-balance-sheet error again: a number that is out by a currency still
# looks plausible.
CURRENCY = {"PH": "PHP", "CN": "CNY", "JP": "JPY", "KR": "KRW", "GB": "GBP", "EU": "EUR"}


# Series that FRED carries in different units than the series CGI used to hold.
# Maintained nightly by fred-data-updater, so they cost no tokens, unlike the
# TradingView-sourced copies. Each factor was asserted equal on shared dates
# (JPNASSETS x1e8 == JP_CB_ASSETS, ECBASSETSW x1e6 == EU_CB_ASSETS) before the
# switch; the old rows stay in price-history as the fallback.
#   our symbol -> (FRED-fed symbol, multiply by)
FRED_SCALED: dict[str, tuple[str, float]] = {
    "JP_CB_ASSETS": ("JPNASSETS", 1e8),    # 100M yen -> yen
    "EU_CB_ASSETS": ("ECBASSETSW", 1e6),   # millions of euro -> euro
}


def _load(sym: str) -> tuple[list[str], list[float]]:
    try:
        return ad._load_close(sym)
    except Exception:  # noqa: BLE001 -- a missing series must not break the page
        return [], []


def _series(sym: str) -> tuple[list[str], list[float]]:
    alt = FRED_SCALED.get(sym)
    if alt:
        dates, vals = _load(alt[0])
        if dates:
            return dates, [v * alt[1] for v in vals]
        # FRED-fed series unavailable: fall back to the held copy rather than
        # showing nothing. It is the same quantity, just fetched by a person.
    return _load(sym)


def _median_spacing_days(dates: list[str]) -> Optional[float]:
    if len(dates) < 4:
        return None
    gaps = [(dt.date.fromisoformat(dates[i]) - dt.date.fromisoformat(dates[i - 1])).days
            for i in range(1, len(dates))]
    return st.median(gaps)


def _bars_per_year(dates: list[str]) -> Optional[int]:
    """Observations in a year, from the data's own spacing. This is the guard
    against the GB quarterly/monthly trap -- see the module docstring."""
    sp = _median_spacing_days(dates)
    if not sp:
        return None
    if sp <= 4:
        return 252      # daily (weekends make the median 1, never above 3)
    if sp <= 10:
        return 52       # weekly -- previously lumped in with daily, so a weekly
                        # series looked back 252 BARS (~5 years) for "a year ago"
    if sp <= 45:
        return 12       # monthly
    if sp <= 135:
        return 4        # quarterly
    return 1            # annual


def _cadence_name(dates: list[str]) -> Optional[str]:
    n = _bars_per_year(dates)
    return {252: "daily", 52: "weekly", 12: "monthly", 4: "quarterly", 1: "annual"}.get(n) if n else None


# Known LEVEL DISCONTINUITIES: dates where a source redefined a series, so the
# step between the two sides is a change of definition rather than of the
# economy. A year-on-year figure computed ACROSS one of these is not a
# measurement of anything.
#
# KR_M2 falls 10.3% between 2026-01 (4,568.7tn KRW) and 2026-02 (4,099.5tn).
# Korean M2 does not contract a tenth in a month; every other month in the
# series back to 2019 is smooth. Left alone this would have printed a large
# false monetary contraction for Korea for twelve months, and dragged the
# money-vs-credit gap with it -- which is the number the gap exists to make
# readable.
SERIES_BREAKS: dict[str, list[tuple[str, str]]] = {
    "KR_M2": [("2026-02-01",
               "the source redefined Korean M2 here: the level drops 10.3% in "
               "one month against a series that is otherwise smooth back to "
               "2019, so this is a definitional step, not a contraction")],
}


def _break_between(sym: str, start: str, end: str) -> Optional[str]:
    """The reason, if a known redefinition falls inside (start, end]."""
    for at, why in SERIES_BREAKS.get(sym, []):
        if start < at <= end:
            return why
    return None


def _macro_point(sym: str, kind: str = "rate") -> Optional[dict]:
    """Latest level, the change since the PRIOR PRINT, and YoY where the series
    is a level rather than an already-YoY rate."""
    dates, vals = _series(sym)
    if not dates:
        return None
    out = {
        "symbol": sym,
        "as_of": dates[-1],
        "latest": round(vals[-1], 4) if abs(vals[-1]) < 1e6 else vals[-1],
        "n_obs": len(dates),
        "cadence": _cadence_name(dates),
        "age_days": (dt.date.today() - dt.date.fromisoformat(dates[-1])).days,
    }
    if len(vals) >= 2:
        out["prior"] = vals[-2]
        out["change_since_prior"] = round(vals[-1] - vals[-2], 4)
        out["direction"] = "up" if vals[-1] > vals[-2] else "down" if vals[-1] < vals[-2] else "flat"
    bpy = _bars_per_year(dates)
    if bpy and len(vals) > bpy:
        prev = vals[-1 - bpy]
        out["yoy_lag_bars"] = bpy       # shown so the lag can be checked, not trusted
        out["a_year_ago"] = prev
        broke = _break_between(sym, dates[-1 - bpy], dates[-1])
        if broke:
            # Withheld rather than printed with a caveat: a number on the page
            # gets read, and a footnote saying to ignore it does not undo that.
            out["yoy_unavailable"] = broke
        elif kind == "level":
            if prev:
                out["yoy_pct"] = round((vals[-1] / prev - 1) * 100, 2)
        else:
            # percentage POINTS, not percent. See MACRO's `kind` note.
            out["yoy_pp"] = round(vals[-1] - prev, 2)
    return out


def _returns(sym: str) -> Optional[dict]:
    dates, vals = _series(sym)
    if len(vals) < 30:
        return None
    out = {"symbol": sym, "as_of": dates[-1], "last": round(vals[-1], 4)}
    for name, n in TENORS.items():
        if len(vals) > n and vals[-1 - n]:
            out[f"ret_{name}"] = round((vals[-1] / vals[-1 - n] - 1) * 100, 2)
    return out


def _fx(sym: Optional[str]) -> Optional[dict]:
    """USDXXX returns, with the direction stated in words at source.

    Same rule as regime_matrix: every pair is quoted USD per local unit, so a
    positive return is DOLLAR strength and local-currency weakness. Deriving
    that downstream from a bare sign is how an FX read gets silently inverted.
    """
    if not sym:
        return None
    r = _returns(sym)
    if not r:
        return None
    v = r.get(f"ret_{FX_DIRECTION_TENOR}")
    if v is not None:
        r["direction_tenor"] = FX_DIRECTION_TENOR
        r["usd_3m"] = "stronger" if v > 0 else "weaker" if v < 0 else "flat"
        r["local_3m"] = "weaker" if v > 0 else "stronger" if v < 0 else "flat"
        r["direction_note"] = (
            f"over {FX_DIRECTION_TENOR}, not today: the word describes the "
            f"{FX_DIRECTION_TENOR} move, and the per-tenor returns beside it "
            f"show every other window.")
    r["quoted"] = "USD per local unit (USDXXX): positive = USD strength"
    return r


def _curve(code: str, policy_rate: Optional[float]) -> dict:
    """Actual yields by tenor, plus the spreads and the policy-rate gap.

    Missing tenors are reported as unavailable rather than omitted, so the
    shape of what is missing is visible -- the FOREIGN RATES group declares
    twelve symbols and currently holds none of them.
    """
    tenors, have = {}, 0
    for label, tmpl in CURVE:
        sym = tmpl.format(c=code)
        sub = CURVE_SUBSTITUTE.get((code, label))
        dates, vals = _series(sym)
        substituted = None
        if not dates and sub:
            sym, substituted = sub[0], sub[1]
            dates, vals = _series(sym)
        if dates:
            have += 1
            tenors[label] = {"symbol": sym, "yield_pct": round(vals[-1], 3),
                             "as_of": dates[-1],
                             "age_days": (dt.date.today() - dt.date.fromisoformat(dates[-1])).days,
                             # Present only when this is NOT the country's own
                             # series for this tenor. The page must say so.
                             "substitute_for": substituted}
        else:
            tenors[label] = {"symbol": sym, "yield_pct": None, "unavailable": True}

    def y(k):
        t = tenors.get(k)
        return t["yield_pct"] if t and t["yield_pct"] is not None else None

    spreads = {}
    if y("10y") is not None and y("2y") is not None:
        spreads["10y_2y"] = round(y("10y") - y("2y"), 3)
    if y("10y") is not None and y("3m") is not None:
        spreads["10y_3m"] = round(y("10y") - y("3m"), 3)

    # The front of the curve against the policy rate IS the "what is priced in"
    # read: a 3m well above the policy rate is the market pricing hikes -- but
    # only where the two rates are comparable. See POLICY_COMPARABLE.
    priced = None
    if not POLICY_COMPARABLE.get(code, True):
        priced = {"unavailable": True, "why": POLICY_INCOMPARABLE_WHY.get(code, "")}
    elif y("3m") is not None and policy_rate is not None:
        gap = round(y("3m") - policy_rate, 3)
        priced = {"three_month_minus_policy_pp": gap,
                  "reads_as": ("market pricing HIKES" if gap > 0.15
                               else "market pricing CUTS" if gap < -0.15
                               else "market pricing roughly no change")}
    return {"tenors": tenors, "spreads": spreads, "priced_in": priced,
            "n_available": have, "n_tenors": len(CURVE)}


def _rs(sym: str) -> Optional[dict]:
    """Relative strength against SPY, reusing themes_data._run unchanged -- it
    takes two plain dicts and is not theme-specific."""
    px, bench = td._load(sym), td._load(BENCH)
    if not px or not bench:
        return None
    try:
        return td._run(px, bench)
    except Exception:  # noqa: BLE001
        return None


# In-process memo of the per-country blocks.
#
# Everything in _country_block depends only on the COUNTRY, never on the
# regime: policy rate, CPI, GDP, loan growth, M2, the curve, and the ETF/FX
# returns are the same numbers whichever Compass x Grid cell is being viewed.
# Only the regime matrix itself, the tide, and excess_vs_tide move.
#
# They used to be rebuilt inside build_countries on every request, so clicking
# a regime -- which bypasses the S3 cache, since only the default cell was
# cached -- rebuilt all twenty countries from scratch. Measured before this
# change: 100 seconds for /countries?compass=2&grid=1 against 1.1 seconds for
# the cached default.
# Matched to the cache TTL rather than kept short: the blocks are the
# expensive half, and re-deriving them inside the window the cached
# payload is still considered fresh would be work with nothing to show
# for it.
_BLOCKS_TTL_SECONDS = 6 * 3600.0
_blocks_cache: dict[str, object] = {"at": 0.0, "data": None}


def _country_block(code: str, equity_symbol: Optional[str], currency: Optional[dict]) -> dict:
    """The regime-independent half: this country's own conditions and its
    instruments' live returns."""
    macro = {}
    for key, tmpl, unit, label, kind in MACRO:
        pt = _macro_point(tmpl.format(c=code), kind=kind)
        if pt:
            pt["label"] = label
            pt["unit"] = CURRENCY.get(code, "local") if unit == "local" else unit
            pt["kind"] = kind
            macro[key] = pt
    # Howell's two halves side by side. Money growing faster than credit is
    # liquidity that is not transmitting into lending; the reverse is credit
    # expansion outrunning the money base. Neither is visible from one leg.
    m2 = macro.get("m2", {}).get("yoy_pct") if macro else None
    credit = None
    if macro:
        lg = macro.get("loan_growth_yoy")
        credit = lg.get("latest") if lg else (macro.get("loans_level") or {}).get("yoy_pct")
    if m2 is not None and credit is not None:
        macro["money_vs_credit"] = {
            "m2_yoy_pct": m2,
            "credit_yoy_pct": credit,
            "gap_pp": round(m2 - credit, 2),
            "reads_as": ("money outrunning credit -- liquidity not transmitting into lending"
                         if m2 - credit > 1.0 else
                         "credit outrunning money -- lending expanding faster than the money base"
                         if m2 - credit < -1.0 else
                         "money and credit growing together"),
        }
    pr = (macro.get("policy_rate") or {}).get("latest") if macro else None
    return {
        "macro": macro or None,
        "macro_note": (
            "This country's own conditions. It is NOT the regime the trade is "
            "conditioned on -- that is the US Compass/Grid above." if macro else None
        ),
        "curve": _curve(code, pr),
        "market": {
            "etf": _returns(equity_symbol) if equity_symbol else None,
            "fx": _fx(currency["symbol"]) if currency and currency.get("symbol") else None,
            "rs_vs_spy": _rs(equity_symbol) if equity_symbol else None,
        },
    }


def build_country_blocks(countries: list[dict]) -> dict[str, dict]:
    """{code: block} for every country, memoised across regimes."""
    hit = _blocks_cache["data"]
    if hit is not None and (time.monotonic() - float(_blocks_cache["at"])) < _BLOCKS_TTL_SECONDS:
        return hit  # type: ignore[return-value]
    blocks = {
        c["code"]: _country_block(
            c["code"], (c.get("equity") or {}).get("symbol"), c.get("currency")
        )
        for c in countries
    }
    _blocks_cache["at"], _blocks_cache["data"] = time.monotonic(), blocks
    return blocks


def resolve_regime(compass_q: Optional[int], grid_q: Optional[int]) -> tuple[int, int]:
    """Fill either axis from the current model. Split out of build_countries so
    the CALLER can resolve before choosing a cache key -- keying on a literal
    None would make one key mean different cells as the regime moves."""
    if compass_q is not None and grid_q is not None:
        return compass_q, grid_q
    import markov_data
    cur = {m: markov_data._load_model(f"{m}_US")[-1][1] for m in ("compass", "grid")}
    return (compass_q if compass_q is not None else cur["compass"],
            grid_q if grid_q is not None else cur["grid"])


def build_countries(compass_q: Optional[int] = None, grid_q: Optional[int] = None,
                    min_n: int = 5) -> dict:
    """The regime matrix, with a macro and market block attached per country."""
    compass_q, grid_q = resolve_regime(compass_q, grid_q)

    matrix = regime_matrix.build_matrix(compass_q, grid_q, min_n=min_n)
    blocks = build_country_blocks(matrix["countries"])

    for c in matrix["countries"]:
        block = blocks.get(c["code"]) or {}
        c["macro"] = block.get("macro")
        c["macro_note"] = block.get("macro_note")
        c["curve"] = block.get("curve")
        c["market"] = block.get("market")

    # The tide: the average across all countries in this regime, so a country's
    # number is read against it rather than in isolation. 64% of the variance in
    # these returns is the regime itself, so without this the reader is looking
    # at the common factor and thinking it is country selection.
    rets = [c["equity"]["avg_return_pct"] for c in matrix["countries"]
            if c.get("equity") and c["equity"].get("occurrences")]
    tide = round(st.mean(rets), 2) if rets else None
    for c in matrix["countries"]:
        e = c.get("equity")
        c["excess_vs_tide"] = (round(e["avg_return_pct"] - tide, 2)
                               if e and e.get("occurrences") and tide is not None else None)

    matrix["tide"] = {
        "avg_return_pct": tide,
        "n_countries": len(rets),
        "explanation": ("The average of every country in this regime. 64.2% of the "
                        "variance in these returns is the regime itself and only 2.5% "
                        "is the country, so a country's number means little except "
                        "against this."),
    }
    matrix["edge_caveat"] = (
        "Country-by-regime differences are NOT distinguishable from noise: 7 of 250 "
        "cells clear |t|>2 where chance alone predicts 12.5. EPHE in C1G1 is the "
        "strongest cell in the matrix (+3.55pp over the tide, t=3.05, n=16) and still "
        "does not survive having looked at 250 of them. Treat this tab as monitoring."
    )
    matrix["schema_version"] = SCHEMA_VERSION
    return matrix


