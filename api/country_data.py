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
import statistics as st
from typing import Optional

import axis_drivers as ad
import regime_matrix
import themes_data as td

SCHEMA_VERSION = 1

BENCH = "SPY"

# Standard tenors, matching dashboard_data._LOOKBACK so a return on this page
# means the same thing as a return anywhere else on the site.
TENORS = {"1m": 21, "3m": 63, "6m": 126, "1y": 252}

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
]

# Local currency per country, for labelling levels. Getting this wrong is the
# BOJ-balance-sheet error again: a number that is out by a currency still
# looks plausible.
CURRENCY = {"PH": "PHP", "CN": "CNY", "JP": "JPY", "KR": "KRW", "GB": "GBP", "EU": "EUR"}


def _series(sym: str) -> tuple[list[str], list[float]]:
    try:
        return ad._load_close(sym)
    except Exception:  # noqa: BLE001 -- a missing series must not break the page
        return [], []


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
    if sp <= 10:
        return 252      # daily
    if sp <= 45:
        return 12       # monthly
    if sp <= 135:
        return 4        # quarterly
    return 1            # annual


def _cadence_name(dates: list[str]) -> Optional[str]:
    n = _bars_per_year(dates)
    return {252: "daily", 12: "monthly", 4: "quarterly", 1: "annual"}.get(n) if n else None


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
        if kind == "level":
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
    v = r.get("ret_3m")
    if v is not None:
        r["usd_3m"] = "stronger" if v > 0 else "weaker" if v < 0 else "flat"
        r["local_3m"] = "weaker" if v > 0 else "stronger" if v < 0 else "flat"
    r["quoted"] = "USD per local unit (USDXXX): positive = USD strength"
    return r


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


def build_countries(compass_q: Optional[int] = None, grid_q: Optional[int] = None,
                    min_n: int = 5) -> dict:
    """The regime matrix, with a macro and market block attached per country."""
    if compass_q is None or grid_q is None:
        import markov_data
        cur = {m: markov_data._load_model(f"{m}_US")[-1][1] for m in ("compass", "grid")}
        compass_q = compass_q if compass_q is not None else cur["compass"]
        grid_q = grid_q if grid_q is not None else cur["grid"]

    matrix = regime_matrix.build_matrix(compass_q, grid_q, min_n=min_n)

    for c in matrix["countries"]:
        code = c["code"]
        macro = {}
        for key, tmpl, unit, label, kind in MACRO:
            pt = _macro_point(tmpl.format(c=code), kind=kind)
            if pt:
                pt["label"] = label
                pt["unit"] = CURRENCY.get(code, "local") if unit == "local" else unit
                pt["kind"] = kind
                macro[key] = pt
        c["macro"] = macro or None
        c["macro_note"] = (
            "This country's own conditions. It is NOT the regime the trade is "
            "conditioned on -- that is the US Compass/Grid above." if macro else None
        )
        etf = (c.get("equity") or {}).get("symbol")
        c["market"] = {
            "etf": _returns(etf) if etf else None,
            "fx": _fx_symbol_returns(c),
            "rs_vs_spy": _rs(etf) if etf else None,
        }

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


def _fx_symbol_returns(c: dict) -> Optional[dict]:
    cur = c.get("currency")
    return _fx(cur["symbol"]) if cur and cur.get("symbol") else None
