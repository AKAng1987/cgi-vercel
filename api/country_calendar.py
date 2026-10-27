"""
Country release calendar: central-bank decisions, inflation and GDP prints for the countries on the Countries page.

Where it comes from. The API cannot reach TradingView; the refresh routine (a Claude session, see scripts/cgi_refresh.py)
reads TradingView's economic calendar once a week, forwards each event as a compact row, and POSTs them to
POST /api/country_calendar. Classification and validation happen HERE, in code, so the model never decides what a row
is. The stored blob is a snapshot of the next ~30 days (TradingView looks ahead about 31 days).

What it is for. A release date turns "ask the source monthly" into "ask on the day it prints": the routine's planner
(cgi_refresh.py plan) uses these rows to make a series due once its release has passed, and to leave it alone until then.
The Countries page shows the same rows, so a print that has happened but is not yet loaded is visible as such.

Row (stored): {country, date, title, kind, series, period, previous, forecast, importance}
  kind   rate | cpi | gdp
  series the CGI series the release feeds (PH_POLICY_RATE ...) or None when CGI does not track it
"""
from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any, Optional

COUNTRIES = ("PH", "CN", "JP", "KR", "GB", "EU", "IN", "ID", "TW", "HK", "SG", "MY", "VN", "AU", "CA", "CH", "BR", "MX", "ZA")
MAX_ROWS = 600
MAX_TITLE = 80
PAST_DAYS = 7      # keep a week of past rows so "released, not yet loaded" can be shown
FUTURE_DAYS = 45
KEY = "calendar/country_calendar.json"

# Compact row as the routine sends it (a list, so each row costs few tokens):
#   [country, date_iso, title, indicator, category, period, previous, forecast, importance, ticker]
FIELDS = ("country", "date", "title", "indicator", "category", "period", "previous", "forecast", "importance", "ticker")

# TradingView files many things under the indicator "Interest Rate": votes, speeches, minutes, survey read-outs, council meetings.
# A row is a rate DECISION only if its title says so (a decision, or China's loan prime rate) and says nothing of the others.
_IS_A_DECISION = re.compile(r"decision|loan prime rate|policy rate", re.I)
_NOT_A_DECISION = re.compile(
    r"minutes|accounts|press conference|report|speech|statement|summary|testimony|projections|outlook|vote|appearance|"
    r"readout|read-out|focus|council|senate|\b5y\b|deposit|facility", re.I)


def classify(indicator: str, title: str, category: str) -> Optional[str]:
    """rate | cpi | gdp, or None for everything else (PMI, trade, retail, jobs, confidence, minutes, press conferences)."""
    ind, ttl, cat = (indicator or "").strip(), (title or ""), (category or "").lower()
    if ind == "Interest Rate" and _IS_A_DECISION.search(ttl) and not _NOT_A_DECISION.search(ttl):
        return "rate"
    if ind == "Inflation Rate":
        return "cpi"
    if ind in ("GDP Annual Growth Rate", "GDP Growth Rate"):
        return "gdp"
    return None


def series_for(ticker: Optional[str]) -> Optional[str]:
    """CGI symbol for a TradingView ticker such as ECONOMICS:PHINTR, from series_write.ALLOWED (one source of truth)."""
    if not ticker:
        return None
    import series_write

    for sym, spec in series_write.ALLOWED.items():
        if len(spec) >= 5 and spec[0] == "tradingview" and spec[4] == ticker:
            return sym
    return None


def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 4) if abs(f) < 1e9 else None


def clean(rows: Any, today: Optional[dt.date] = None) -> tuple[list[dict], dict]:
    """Validate what an unauthenticated caller sent. Returns (rows, report). Never raises on a bad row: it drops it and
    counts why, so one malformed event cannot lose the week's calendar."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    report = {"received": 0, "kept": 0, "dropped": {}}

    def drop(why: str) -> None:
        report["dropped"][why] = report["dropped"].get(why, 0) + 1

    if not isinstance(rows, list):
        return [], {**report, "error": "rows must be a list"}
    rows = rows[:MAX_ROWS]
    report["received"] = len(rows)
    lo, hi = today - dt.timedelta(days=PAST_DAYS), today + dt.timedelta(days=FUTURE_DAYS)
    out, seen = [], set()
    for r in rows:
        if not isinstance(r, (list, tuple)) or len(r) < len(FIELDS):
            drop("malformed")
            continue
        country, date_s, title, indicator, category, period, prev, fc, imp, ticker = (r + [None] * 10)[:10]
        if country not in COUNTRIES:
            drop("country")
            continue
        try:
            d = dt.date.fromisoformat(str(date_s)[:10])
        except ValueError:
            drop("date")
            continue
        if not lo <= d <= hi:
            drop("outside window")
            continue
        kind = classify(str(indicator or ""), str(title or ""), str(category or ""))
        if kind is None:
            drop("not rate/cpi/gdp")
            continue
        importance = imp if isinstance(imp, int) and not isinstance(imp, bool) else -1
        if importance < 0:
            drop("importance")
            continue
        tk = ticker if isinstance(ticker, str) and re.fullmatch(r"[A-Z0-9_]{2,12}:[A-Z0-9_.!]{2,24}", ticker) else None
        key = (country, d.isoformat(), kind, str(title)[:MAX_TITLE])
        if key in seen:
            drop("duplicate")
            continue
        seen.add(key)
        out.append({"country": country, "date": d.isoformat(), "title": str(title).strip()[:MAX_TITLE], "kind": kind,
                    "series": series_for(tk), "period": (str(period)[:12] if period else None),
                    "previous": _num(prev), "forecast": _num(fc), "importance": importance})
    out.sort(key=lambda x: (x["date"], x["country"], x["kind"]))
    report["kept"] = len(out)
    return out, report


def write(rows: list[dict]) -> dict:
    import cache

    body = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "rows": rows}
    cache._s3.put_object(Bucket=cache.BUCKET, Key=cache.PREFIX + KEY, Body=json.dumps(body).encode("utf-8"),
                         ContentType="application/json")
    return body


def read() -> dict:
    """The stored snapshot, or an empty one with the reason. Never raises: a missing calendar must not break a page."""
    import cache

    try:
        obj = cache._s3.get_object(Bucket=cache.BUCKET, Key=cache.PREFIX + KEY)
        body = json.loads(obj["Body"].read().decode("utf-8"))
        rows = body.get("rows") if isinstance(body.get("rows"), list) else []
        return {"at": body.get("at"), "rows": rows}
    except Exception as exc:  # noqa: BLE001 -- never written is a valid answer
        return {"at": None, "rows": [], "why": f"no calendar stored ({type(exc).__name__})"}


def for_country(snapshot: dict, code: str, today: Optional[dt.date] = None, loaded: Optional[dict[str, str]] = None) -> list[dict]:
    """This country's events, nearest first, each with days_to_go and, for a release that has already passed, whether CGI
    has loaded it. `loaded` maps a CGI series symbol to the date of its newest stored observation."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    out = []
    for r in snapshot.get("rows", []):
        if r.get("country") != code:
            continue
        d = dt.date.fromisoformat(r["date"])
        e = dict(r, days_to_go=(d - today).days)
        if e["days_to_go"] < 0 and r.get("series") and loaded is not None:
            # A monthly series is stamped with the 1st of the period it describes; it is current once its stamp reaches
            # the month of the release, minus one for a release that describes the previous period (CPI, GDP lag).
            have = loaded.get(r["series"])
            e["loaded"] = bool(have and have >= _period_stamp(r, d))
        out.append(e)
    out.sort(key=lambda x: (x["date"], x["kind"]))
    return out


def _period_stamp(row: dict, release: dt.date) -> str:
    """The date stamp the stored series should reach once this release has been loaded."""
    kind = row.get("kind")
    if kind == "rate":
        return release.replace(day=1).isoformat()          # the rate in force from that month
    # inflation / GDP describe the period before the release: previous month, or previous quarter start
    first = release.replace(day=1)
    if kind == "gdp":
        # stamped with the first day of the quarter's LAST month (Q2 -> 06-01, Q3 -> 09-01); the quarter is the latest one
        # that closed strictly before the release month
        ends = [m for m in (3, 6, 9, 12) if m < release.month]
        return (dt.date(release.year, ends[-1], 1) if ends else dt.date(release.year - 1, 12, 1)).isoformat()
    return (first - dt.timedelta(days=1)).replace(day=1).isoformat()
