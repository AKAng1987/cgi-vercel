"""
macro_data.py — Phase 2 /api/macro/rates data layer.

Ported (not imported live) from ~/market-dashboard/macro_data.py and
fomc_data.py, ADAPTED for this canary:
  - Local parquet caching (_is_stale/_cache_path/to_parquet) is stripped
    entirely. cache.py's S3-backed cache (per PHASE2_PLAN.md Variant C)
    is now the SOLE staleness authority for this endpoint -- every fetch
    function here always hits the live source. Two overlapping cache
    layers with two different TTL sets would be confusing and wrong;
    removing the local layer at the source during the port is the clean
    fix (see canary report for detail).
  - Functions return plain dicts/lists (JSON-serializable), not pandas
    DataFrames, so the endpoint can serialize directly -- pandas is still
    used internally for the merge/interpolation logic where it was
    already doing real work (fed funds range date-merge), matching
    PHASE2_PLAN.md's dependency note that Phase 2, unlike Phase 1, is
    allowed to keep pandas since the data transforms are pandas-idiomatic.
  - DFEDTARU's DynamoDB-price-history-preferred path (present in the
    original fetch_fed_funds_range) is simplified to FRED-only for this
    canary -- same published government series either way, and avoiding
    a DynamoDB dependency keeps this canary's scope tight. Flagged in the
    report as a minor, disclosed divergence, not silently dropped.
"""
from __future__ import annotations

import calendar
import datetime
import math
import os
import re
from typing import Optional

import pandas as pd
import requests

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"

DGS_SERIES = [
    "DGS1MO", "DGS3MO", "DGS1", "DGS2", "DGS3",
    "DGS5", "DGS7", "DGS10", "DGS20", "DGS30",
]
DGS_LABELS = {
    "DGS1MO": "1M", "DGS3MO": "3M",
    "DGS1": "1Y", "DGS2": "2Y", "DGS3": "3Y",
    "DGS5": "5Y", "DGS7": "7Y", "DGS10": "10Y",
    "DGS20": "20Y", "DGS30": "30Y",
}

FOMC_2026 = [
    datetime.date(2026, 1, 28),
    datetime.date(2026, 3, 18),
    datetime.date(2026, 4, 29),
    datetime.date(2026, 6, 17),
    datetime.date(2026, 7, 29),
    datetime.date(2026, 9, 16),
    datetime.date(2026, 10, 28),
]

# Bumped whenever the shape or the METHOD of the fomc_probabilities payload
# changes, and read by cache.SCHEMA_FROM_MODULE so the bump lands in the same
# edit as the change rather than in a table in another file.
SCHEMA_VERSION = 3

# The most a monthly contract quote may be magnified to back out a
# post-meeting rate before we stop trusting the result and reach for the
# following month's contract instead. 3.0 means "no more than a third of the
# month may be doing all the work".
LEVER_CAP = 3.0

_MONTH_CODE = {
    1: "F", 2: "G", 3: "H", 4: "J", 5: "K", 6: "M",
    7: "N", 8: "Q", 9: "U", 10: "V", 11: "X", 12: "Z",
}


def _secret(key: str) -> str:
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.environ.get(key, "")


def _fred_get(series_id: str, observation_start: Optional[str] = None) -> pd.DataFrame:
    params: dict = {
        "series_id": series_id,
        "api_key": _secret("FRED_API_KEY"),
        "file_type": "json",
    }
    if observation_start:
        params["observation_start"] = observation_start
    resp = requests.get(FRED_URL, params=params, timeout=30)
    resp.raise_for_status()
    records = []
    for o in resp.json().get("observations", []):
        try:
            records.append({"date": pd.Timestamp(o["date"]), "value": float(o["value"])})
        except (ValueError, KeyError):
            continue
    return pd.DataFrame(records)


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    out = df.copy()
    if "date" in out.columns:
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    # Outer-merges/joins across series with misaligned dates leave NaN gaps
    # (e.g. DFEDTARU/DFEDTARL don't always update on the same day) -- NaN
    # isn't valid JSON, convert to None so the standard-library json encoder
    # (which FastAPI's default JSONResponse uses) doesn't choke.
    out = out.astype(object).where(pd.notnull(out), None)
    return out.to_dict(orient="records")


# ── fed_funds_range (12h TTL) ─────────────────────────────────────────

def fetch_fed_funds_range() -> list[dict]:
    """DFEDTARU (upper) + DFEDTARL (lower), FRED-only, 5-year lookback."""
    start_5y = (datetime.datetime.now() - datetime.timedelta(days=365 * 5)).strftime("%Y-%m-%d")
    upper_df = _fred_get("DFEDTARU", observation_start=start_5y).rename(columns={"value": "upper"})
    lower_df = _fred_get("DFEDTARL", observation_start=start_5y).rename(columns={"value": "lower"})
    df = pd.merge(upper_df, lower_df, on="date", how="outer").sort_values("date").reset_index(drop=True)
    return _df_to_records(df)


# ── treasury_curve (6h TTL) ───────────────────────────────────────────

def fetch_treasury_curve() -> list[dict]:
    """FRED DGS1MO..DGS30, 20-year lookback, wide by tenor label."""
    start = (datetime.datetime.now() - datetime.timedelta(days=365 * 20)).strftime("%Y-%m-%d")
    frames = {}
    for sid in DGS_SERIES:
        df_s = _fred_get(sid, observation_start=start)
        if not df_s.empty:
            frames[DGS_LABELS[sid]] = df_s.set_index("date")["value"]
    wide = pd.DataFrame(frames).sort_index().reset_index().rename(columns={"index": "date"})
    return _df_to_records(wide)


def _months_ago(d: datetime.date, months: int) -> datetime.date:
    """Port of JS `Date.setMonth(d.getMonth() - months)` semantics used
    by YieldCurvePanel.tsx's monthsAgo(): day is NOT clamped to the
    target month's length, it overflows forward exactly like JS's Date
    normalization does. Implemented by walking to day 1 of the target
    month and adding (day-1) days, which reproduces the same overflow."""
    total_months = d.year * 12 + (d.month - 1) - months
    year, month0 = divmod(total_months, 12)
    return datetime.date(year, month0 + 1, 1) + datetime.timedelta(days=d.day - 1)


def _trim_treasury_curve(records: list[dict]) -> dict:
    """Endpoint-layer trim (2026-09-07, Task 1b): the frontend
    (YieldCurvePanel.tsx) only ever reads 3 snapshot rows (latest/6M
    ago/1Y ago, all tenors) plus the 10Y tenor's full history for its
    two-panel chart -- it never uses the other 9 tenors' full 20-year
    history that fetch_treasury_curve() produces. That unused shape was
    ~730KB of the ~1.2MB /macro payload (overnight-report-20260907.md
    Task 1). This mirrors YieldCurvePanel.tsx's own snapshot/history
    logic exactly (same monthsAgo/find-as-of algorithm, see
    _months_ago) so the rendered chart is byte-for-byte unchanged --
    only what crosses the wire shrinks. The full wide table is still
    fetched and cached as before (fetch_treasury_curve is unchanged);
    this only trims what build_rates_response returns."""
    if not records:
        return {"snapshot": [], "history_10y": []}

    sorted_records = sorted(records, key=lambda r: r["date"])
    latest = sorted_records[-1]
    latest_date = datetime.date.fromisoformat(latest["date"])

    def find_as_of(cutoff: datetime.date) -> Optional[dict]:
        candidates = [r for r in sorted_records if datetime.date.fromisoformat(r["date"]) <= cutoff]
        return candidates[-1] if candidates else None

    ago_6m = find_as_of(_months_ago(latest_date, 6))
    ago_1y = find_as_of(_months_ago(latest_date, 12))

    snapshot = [
        {"label": label, **row}
        for label, row in [("Latest", latest), ("6M Ago", ago_6m), ("1Y Ago", ago_1y)]
        if row is not None
    ]
    history_10y = [
        {"date": r["date"], "value": r["10Y"]}
        for r in sorted_records
        if r.get("10Y") is not None
    ]
    return {"snapshot": snapshot, "history_10y": history_10y}


# ── spreads (12h TTL) ─────────────────────────────────────────────────

def fetch_spreads() -> list[dict]:
    """FRED T10Y2Y (%) + BAMLH0A0HYM2 (bp), 20-year lookback.

    BAMLH0A0HYM2 is published by FRED in percent, not bp (verified
    live 2026-09-10: series units="Percent"). Converted here (x100)
    to match the "(bp)" label the frontend (RatesSection.tsx) and the
    market-dashboard Streamlit twin have always used -- see the
    matching fix + full rationale in market-dashboard/macro_data.py's
    fetch_spreads()."""
    start = (datetime.datetime.now() - datetime.timedelta(days=365 * 20)).strftime("%Y-%m-%d")
    dfs: dict = {}
    for sid, label in [("T10Y2Y", "T10Y2Y"), ("BAMLH0A0HYM2", "HY_Spread")]:
        df_s = _fred_get(sid, observation_start=start)
        if not df_s.empty:
            series = df_s.set_index("date")["value"]
            if label == "HY_Spread":
                series = series * 100.0  # FRED percent -> bp
            dfs[label] = series
    wide = pd.DataFrame(dfs).sort_index().reset_index().rename(columns={"index": "date"})
    return _df_to_records(wide)


# ── fomc_meeting_calendar (7d TTL) ────────────────────────────────────

_MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}

_PANEL_RE = re.compile(r'<a id="[^"]*">\s*(\d{4})\s+FOMC Meetings', re.I)
_ROW_RE = re.compile(
    r'fomc-meeting__month[^>]*>\s*<strong>\s*([A-Za-z]+)\s*</strong>.*?'
    r'fomc-meeting__date[^>]*>\s*([0-9]{1,2})(?:\s*[-–]\s*([0-9]{1,2}))?',
    re.I | re.S,
)


def _parse_fomc_panels(html: str) -> list[datetime.date]:
    """Parse the year panels on fomccalendars.htm.

    This is the only way to see FUTURE meetings. The YYYYMMDD regex below
    matches statement and minutes links, which exist only for meetings that
    have ALREADY happened -- so on its own it can never find the next one,
    which is the entire point of the calendar. That is why the December 8-9
    2026 meeting was missing: it has no statement to link to yet.

    A meeting is a one- or two-day range and the decision lands on the LAST
    day, which is the day the futures have to be split around. A range whose
    second day is smaller than its first (January "31-1") runs into the next
    month.
    """
    out: list[datetime.date] = []
    panels = list(_PANEL_RE.finditer(html))
    for i, pm in enumerate(panels):
        year = int(pm.group(1))
        seg = html[pm.end(): panels[i + 1].start() if i + 1 < len(panels) else len(html)]
        for row in _ROW_RE.finditer(seg):
            month_name, d1, d2 = row.group(1), int(row.group(2)), row.group(3)
            month = _MONTHS.get(month_name.capitalize())
            if not month:
                continue
            day = int(d2) if d2 else d1
            y, m = year, month
            if d2 and int(d2) < d1:          # e.g. January "31-1" -> February 1
                y, m = (y + 1, 1) if m == 12 else (y, m + 1)
            try:
                out.append(datetime.date(y, m, day))
            except ValueError:
                continue
    return out


def _scrape_fomc_dates() -> list[datetime.date]:
    try:
        resp = requests.get(
            "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            timeout=10,
        )
        resp.raise_for_status()
    except Exception:  # noqa: BLE001 -- caller falls back to the hardcoded list
        return []

    dates = set(_parse_fomc_panels(resp.text))
    # Past meetings also appear as YYYYMMDD statement links; keep them as a
    # cross-check so a panel-markup change degrades to the old behaviour
    # rather than to nothing.
    for s in re.findall(r"20[2-9][0-9][01][0-9][0-3][0-9]", resp.text):
        try:
            dates.add(datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8])))
        except ValueError:
            continue
    return sorted(dates)


def _fetch_fomc_meeting_calendar() -> list[dict]:
    """All known FOMC meeting dates as ISO strings, sorted. Deliberately
    NOT filtered by today -- filtering happens at read time in
    build_rates_response so the 7d cache doesn't strand a meeting that
    just passed as still 'upcoming' for up to a week (get_upcoming_meetings
    used to run date.today() at fetch time, then cache the filtered list)."""
    candidates = list(FOMC_2026)
    scraped = _scrape_fomc_dates()
    known = set(candidates)
    # Take EVERY scraped date the hardcoded list does not already have, not
    # just post-2026 ones. The old `d.year > 2026` filter meant the hardcoded
    # FOMC_2026 acted as a ceiling rather than a fallback, and it was missing
    # the Dec 8-9 2026 meeting -- so that meeting could never appear at all.
    # It also left the calendar ending in October, which in turn stopped
    # plan_contracts from proving November empty and forced the Oct 28 meeting
    # onto its own 10.3x-levered contract. One stale list, two wrong numbers.
    for d in scraped:
        if d not in known:
            candidates.append(d)
            known.add(d)
    return [{"date": d.isoformat()} for d in sorted(candidates)]


def _filter_meetings_by_horizon(
    meetings_iso: list[dict],
    today: Optional[datetime.date] = None,
    horizon_months: int = 12,
) -> list[dict]:
    if today is None:
        today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=horizon_months * 31)
    return [
        m for m in meetings_iso
        if today <= datetime.date.fromisoformat(m["date"]) <= cutoff
    ]


def get_upcoming_meetings(today: Optional[datetime.date] = None, horizon_months: int = 12) -> list[dict]:
    """Returns [{"date": "YYYY-MM-DD"}, ...] for meetings from today through
    today+horizon_months. Kept for callers that want a one-shot fresh
    filter without going through the S3 cache."""
    return _filter_meetings_by_horizon(
        _fetch_fomc_meeting_calendar(), today=today, horizon_months=horizon_months
    )


# ── fomc_probabilities (6h TTL, yfinance-dependent) ───────────────────

def fetch_effr() -> list[dict]:
    """FRED DFF, last 30 days."""
    start = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    df = _fred_get("DFF", observation_start=start).sort_values("date").reset_index(drop=True)
    return _df_to_records(df)


def _futures_ticker(year: int, month: int) -> str:
    return f"ZQ{_MONTH_CODE[month]}{str(year)[-2:]}.CBT"


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)


def _lever(mtg: datetime.date) -> float:
    """How much the meeting-month contract has to be magnified to back out the
    post-meeting rate. A meeting on the 28th of a 31-day month leaves 3 days,
    so the quote is multiplied by 10.3x -- and so is any error in it."""
    total = calendar.monthrange(mtg.year, mtg.month)[1]
    days_after = total - mtg.day
    return float("inf") if days_after <= 0 else total / days_after


def plan_contracts(meetings: list[datetime.date]) -> dict[datetime.date, dict]:
    """Which contract prices which meeting, and how.

    The monthly ZQ contract settles on the AVERAGE effective rate over its
    month. For a meeting on day D of a T-day month, the post-meeting rate has
    to be de-averaged out of the (T-D) days that follow it:

        post = (avg*T - pre*D) / (T - D)

    which multiplies the quote -- and every basis point of noise in it -- by
    T/(T-D). Late in the month that factor is enormous: Oct 28 in a 31-day
    month is 10.3x, Jul 29 is 15.5x. A 1bp wobble then becomes ~40 percentage
    points of implied probability, which is how a hike probability can look
    like a market view when it is quote noise.

    CME's own method sidesteps this: when the meeting sits near the end of the
    month, read the post-meeting rate straight off the NEXT month's contract,
    whose entire month is post-meeting. No de-averaging, no lever.

    That substitution is only exact if the next month holds no meeting of its
    own. We only claim that when the meeting calendar demonstrably EXTENDS
    past the next month -- otherwise "no meeting next month" may just mean our
    list stops there, and a silent wrong answer is worse than a levered one.
    """
    known = sorted(meetings)
    horizon = known[-1] if known else None
    by_month = {(m.year, m.month) for m in known}

    plan: dict[datetime.date, dict] = {}
    for mtg in known:
        lever = _lever(mtg)
        ny, nm = _next_month(mtg.year, mtg.month)
        next_has_meeting = (ny, nm) in by_month
        # Does our calendar actually cover the next month, or does it merely
        # stop before it? Only the former lets absence mean absence.
        covered = horizon is not None and (horizon.year, horizon.month) > (ny, nm)

        if lever > LEVER_CAP and not next_has_meeting and covered:
            plan[mtg] = {
                "year": ny, "month": nm, "method": "next_month",
                "lever": 1.0, "own_lever": round(lever, 2), "confident": True,
            }
        else:
            confident = lever <= LEVER_CAP
            plan[mtg] = {
                "year": mtg.year, "month": mtg.month, "method": "de_average",
                "lever": round(lever, 2), "own_lever": round(lever, 2),
                "confident": confident,
            }
    return plan


def fetch_futures_for_meetings(meetings: list[datetime.date]) -> dict[datetime.date, float]:
    """{meeting_date: implied_avg_rate_%} from the ZQ contract that PRICES that
    meeting -- which is not always the meeting's own month. See plan_contracts."""
    import yfinance as yf

    plan = plan_contracts(meetings)
    quotes: dict[str, Optional[float]] = {}
    result: dict[datetime.date, float] = {}
    for mtg in sorted(meetings):
        p = plan.get(mtg)
        if not p:
            continue
        ticker = _futures_ticker(p["year"], p["month"])
        if ticker not in quotes:
            try:
                hist = yf.Ticker(ticker).history(period="5d")
                quotes[ticker] = None if hist.empty else float(hist["Close"].iloc[-1])
            except Exception:  # noqa: BLE001 -- reported as unavailable below
                quotes[ticker] = None
        price = quotes[ticker]
        if price is not None:
            result[mtg] = round(100.0 - price, 6)
    return result


def _buckets(post_rate: float, base: float, increment: float) -> list[dict]:
    """Split the implied move across whole 25bp steps.

    A post-meeting rate 40bp above the base is not "a hike"; it is 60% one
    hike and 40% two. The old code clamped to a single step and hard-zeroed
    the opposite direction, so a second cut could never appear at all no
    matter what the strip said."""
    n = (post_rate - base) / increment
    lo = math.floor(n)
    hi = lo + 1
    w_hi = n - lo
    out = []
    for steps, w in ((lo, 1.0 - w_hi), (hi, w_hi)):
        if w > 1e-9:
            out.append({"steps": steps, "prob": round(w, 4),
                        "label": _move_label(steps, increment)})
    return out


def _move_label(steps: int, increment: float) -> str:
    if steps == 0:
        return "Hold"
    bp = int(round(abs(steps) * increment * 100))
    word = "Hike" if steps > 0 else "Cut"
    return f"{word} {bp}bp"


def compute_fomc_probs(
    meetings: list[datetime.date],
    effr_records: list[dict],
    upper_target: float,
    lower_target: float,
    futures: dict[datetime.date, float],
) -> list[dict]:
    """CME FedWatch methodology.

    Three things this does that the first port did not:

      1. Prices late-month meetings off the FOLLOWING contract rather than
         de-averaging three days of the current one (see plan_contracts).
      2. Carries the expected rate FORWARD. The base for each meeting is the
         level expected to prevail going INTO it, not today's target, so a
         second cut can show up as a second cut. The old code compared every
         meeting to today's midpoint, which made cumulative paths impossible
         to express.
      3. Splits the implied move across whole 25bp steps instead of clamping
         to one and hard-zeroing the other direction.

    A meeting whose contract could not be read is returned with
    available=False rather than dropped, so it cannot vanish silently.
    """
    if effr_records:
        current_effr = float(sorted(effr_records, key=lambda r: r["date"])[-1]["value"])
    else:
        current_effr = (upper_target + lower_target) / 2

    midpoint = (upper_target + lower_target) / 2
    increment = 0.25
    plan = plan_contracts(meetings)

    results = []
    pre_rate = current_effr
    # The base is the TARGET midpoint expected going into each meeting, held on
    # the 25bp grid. pre_rate tracks the expected EFFR, which drifts off the
    # grid as probabilities mix; the base must stay on it.
    base = midpoint

    for mtg in sorted(meetings):
        p = plan.get(mtg, {})
        ticker = _futures_ticker(p.get("year", mtg.year), p.get("month", mtg.month))

        if mtg not in futures:
            results.append({
                "date": mtg.isoformat(), "ticker": ticker, "available": False,
                "reason": f"no quote for {ticker}",
                "method": p.get("method"), "lever": p.get("lever"),
                "base_rate": round(base, 4),
            })
            continue

        implied_avg = futures[mtg]
        method = p.get("method", "de_average")

        if method == "next_month":
            # The whole contract month is post-meeting: read it straight off.
            post_rate = implied_avg
        else:
            total_days = calendar.monthrange(mtg.year, mtg.month)[1]
            days_before = mtg.day
            days_after = total_days - mtg.day
            if days_after <= 0:
                post_rate = implied_avg
            else:
                post_rate = (implied_avg * total_days - pre_rate * days_before) / days_after

        buckets = _buckets(post_rate, base, increment)
        p_cut = round(sum(b["prob"] for b in buckets if b["steps"] < 0), 4)
        p_hold = round(sum(b["prob"] for b in buckets if b["steps"] == 0), 4)
        p_hike = round(sum(b["prob"] for b in buckets if b["steps"] > 0), 4)

        top = max(buckets, key=lambda b: b["prob"])
        results.append({
            "date": mtg.isoformat(),
            "ticker": ticker,
            "available": True,
            "method": method,
            "lever": p.get("lever"),
            "own_lever": p.get("own_lever"),
            "confident": p.get("confident", True),
            "implied_avg": round(implied_avg, 4),
            "base_rate": round(base, 4),
            "pre_rate": round(pre_rate, 4),
            "post_rate": round(post_rate, 4),
            "buckets": buckets,
            "p_cut": p_cut,
            "p_hold": p_hold,
            "p_hike": p_hike,
            "most_likely": top["label"],
            "prob_most_likely": top["prob"],
        })

        # Carry forward: the expected EFFR is the probability-weighted level,
        # while the base moves to the single most likely grid point.
        pre_rate = sum(b["prob"] * (base + b["steps"] * increment) for b in buckets)
        base = base + top["steps"] * increment

    return results


def build_fomc_probabilities(meetings_iso: list[dict]) -> dict:
    """Orchestrates the fomc_probabilities cache key: takes the (possibly
    cached) meeting calendar as input, fetches EFFR + fed funds range
    (for upper/lower target) + yfinance futures, computes probabilities."""
    meetings = [datetime.date.fromisoformat(m["date"]) for m in meetings_iso]

    effr_records = fetch_effr()
    fed_funds = fetch_fed_funds_range()
    latest = fed_funds[-1] if fed_funds else {"upper": None, "lower": None}
    upper_target, lower_target = latest["upper"], latest["lower"]

    futures = fetch_futures_for_meetings(meetings)
    probs = compute_fomc_probs(meetings, effr_records, upper_target, lower_target, futures)

    return {
        "upper_target": upper_target,
        "lower_target": lower_target,
        "effr_latest": effr_records[-1]["value"] if effr_records else None,
        "probabilities": probs,
    }


# ── lending_standards (48h TTL) ────────────────────────────────────────

def fetch_lending_standards() -> list[dict]:
    """FRED DRTSCILM -- Net % Domestic Banks Tightening C&I Loan Standards
    (quarterly). Records: {date, value}."""
    start = (datetime.datetime.now() - datetime.timedelta(days=365 * 15)).strftime("%Y-%m-%d")
    df = _fred_get("DRTSCILM", observation_start=start).sort_values("date").reset_index(drop=True)
    return _df_to_records(df)


# ── challenger (24h TTL) ───────────────────────────────────────────────

def fetch_challenger() -> list[dict]:
    """Challenger, Gray & Christmas announced job cuts (monthly, thousands).
    No free API -- the series lives in price-history as CHALLENGER (loaded
    from TradingView ECONOMICS:USJC, refreshed by hand). Records:
    {date, value} in thousands, 15-year window."""
    import boto3

    ddb = boto3.client("dynamodb", region_name="ap-southeast-1")
    start = (datetime.datetime.now() - datetime.timedelta(days=365 * 15)).strftime("%Y-%m-%d")
    kwargs = dict(
        TableName="cmon-stage-backend-price-history",
        KeyConditionExpression="#s = :s AND #d >= :d",
        ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#c": "close"},
        ExpressionAttributeValues={":s": {"S": "CHALLENGER"}, ":d": {"S": start}},
        ProjectionExpression="#d, #c",
    )
    out = []
    while True:
        page = ddb.query(**kwargs)
        out += [{"date": it["date"]["S"], "value": round(float(it["close"]["N"]) / 1000.0, 3)}
                for it in page["Items"] if "close" in it]
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return sorted(out, key=lambda r: r["date"])


# ── gdp (48h TTL: quarterly BEA print + ALFRED vintages) ───────────────

_BEA_GDP_CALENDAR: dict[str, dict[str, str]] = {
    # quarter_start (ISO) : {vintage_label: release_date (ISO)}
    "2022-01-01": {"Advance": "2022-04-28", "Second": "2022-05-26", "Third": "2022-06-29"},
    "2022-04-01": {"Advance": "2022-07-28", "Second": "2022-08-25", "Third": "2022-09-29"},
    "2022-07-01": {"Advance": "2022-10-27", "Second": "2022-11-30", "Third": "2022-12-22"},
    "2022-10-01": {"Advance": "2023-01-26", "Second": "2023-02-23", "Third": "2023-03-30"},
    "2023-01-01": {"Advance": "2023-04-27", "Second": "2023-05-25", "Third": "2023-06-29"},
    "2023-04-01": {"Advance": "2023-07-27", "Second": "2023-08-30", "Third": "2023-09-28"},
    "2023-07-01": {"Advance": "2023-10-26", "Second": "2023-11-29", "Third": "2023-12-21"},
    "2023-10-01": {"Advance": "2024-01-25", "Second": "2024-02-28", "Third": "2024-03-28"},
    "2024-01-01": {"Advance": "2024-04-25", "Second": "2024-05-30", "Third": "2024-06-27"},
    "2024-04-01": {"Advance": "2024-07-25", "Second": "2024-08-29", "Third": "2024-09-26"},
    "2024-07-01": {"Advance": "2024-10-30", "Second": "2024-11-27", "Third": "2024-12-19"},
    "2024-10-01": {"Advance": "2025-01-30", "Second": "2025-02-27", "Third": "2025-03-27"},
    "2025-01-01": {"Advance": "2025-04-30", "Second": "2025-05-29", "Third": "2025-06-26"},
    "2025-04-01": {"Advance": "2025-07-30", "Second": "2025-08-28", "Third": "2025-09-25"},
    "2025-07-01": {"Advance": "2025-12-23", "Second": "2026-01-22"},  # govt shutdown
    "2025-10-01": {"Advance": "2026-02-20", "Second": "2026-03-13", "Third": "2026-04-09"},
    "2026-01-01": {"Advance": "2026-04-30"},
}


def fetch_gdp_quarterly() -> list[dict]:
    """BEA NIPA T10101 -- QoQ annualized real GDP % change.
    Records: {date, gdp_pct}."""
    data = _bea_get({
        "method": "GetData",
        "DataSetName": "NIPA",
        "TableName": "T10101",
        "Frequency": "Q",
        "Year": "ALL",
    })
    rows = data["BEAAPI"]["Results"]["Data"]
    records = []
    for r in rows:
        if r.get("LineDescription", "").strip() == "Gross domestic product":
            tp = r["TimePeriod"]  # e.g. "2024Q3"
            year, q = int(tp[:4]), int(tp[5])
            month = (q - 1) * 3 + 1
            try:
                val = float(r["DataValue"].replace(",", ""))
            except (ValueError, AttributeError):
                continue
            records.append({"date": pd.Timestamp(year=year, month=month, day=1), "gdp_pct": val})
    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    return _df_to_records(df)


def fetch_gdp_vintages() -> list[dict]:
    """ALFRED vintage history for A191RL1Q225SBEA (Real GDP % chg, SAAR).
    One record per (quarter, vintage_label): {quarter, vintage, value,
    release_date, days_after_qend}. Verbatim port of
    macro_data.fetch_gdp_vintages's ALFRED-lookup logic."""
    params = {
        "series_id": "A191RL1Q225SBEA",
        "api_key": _secret("FRED_API_KEY"),
        "file_type": "json",
        "realtime_start": "1776-07-04",
        "realtime_end": "9999-12-31",
    }
    resp = requests.get(FRED_URL, params=params, timeout=30)
    resp.raise_for_status()

    raw: list[dict] = []
    for o in resp.json().get("observations", []):
        try:
            raw.append({
                "quarter": pd.Timestamp(o["date"]),
                "realtime_start": pd.Timestamp(o["realtime_start"]),
                "value": float(o["value"]),
            })
        except (ValueError, TypeError):
            continue

    if not raw:
        return []

    alfred = pd.DataFrame(raw).sort_values(["quarter", "realtime_start"]).reset_index(drop=True)

    def _qend(q: pd.Timestamp) -> pd.Timestamp:
        return q + pd.DateOffset(months=2) + pd.offsets.MonthEnd(0)

    def _value_as_of(qstart: pd.Timestamp, release_dt: pd.Timestamp):
        sub = alfred[
            (alfred["quarter"] == qstart)
            & (alfred["realtime_start"] <= release_dt + pd.Timedelta(days=3))
        ]
        return float(sub.iloc[-1]["value"]) if not sub.empty else None

    out_rows: list[dict] = []
    for qs, releases in _BEA_GDP_CALENDAR.items():
        qstart = pd.Timestamp(qs)
        qe = _qend(qstart)
        for label, rdate_str in releases.items():
            rdate = pd.Timestamp(rdate_str)
            val = _value_as_of(qstart, rdate)
            if val is None:
                continue
            out_rows.append({
                "quarter": qstart,
                "vintage": label,
                "value": val,
                "release_date": rdate,
                "days_after_qend": int((rdate - qe).days),
            })

    df_out = pd.DataFrame(out_rows).sort_values(["quarter", "release_date"]).reset_index(drop=True)
    out = df_out.copy()
    out["quarter"] = out["quarter"].dt.strftime("%Y-%m-%d")
    out["release_date"] = out["release_date"].dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")


def fetch_gdp() -> dict:
    """Orchestrates the gdp cache key: quarterly BEA print + ALFRED vintages."""
    return {
        "quarterly": fetch_gdp_quarterly(),
        "vintages": fetch_gdp_vintages(),
    }


# ── gdp_nowcast (24h TTL: Atlanta Fed GDPNow only) ──────────────────────

def fetch_gdp_nowcast() -> list[dict]:
    """FRED GDPNOW -- Atlanta Fed real-time GDP estimate.
    Records: {date, gdpnow}. Split from `gdp` into its own cache key per
    PHASE2_PLAN.md's 2026-09-05 addendum -- GDPNow moves faster than the
    quarterly print it was originally bundled with."""
    start = (datetime.datetime.now() - datetime.timedelta(days=365 * 10)).strftime("%Y-%m-%d")
    df = _fred_get("GDPNOW", observation_start=start)
    if df.empty:
        return []
    df = df.rename(columns={"value": "gdpnow"}).sort_values("date").reset_index(drop=True)
    return _df_to_records(df)


def _fred_series_meta(series_id: str) -> dict:
    """FRED's own metadata for a series -- crucially `last_updated`.

    Needed because an observation's DATE and its freshness are different
    facts, and conflating them is how a healthy series gets declared dead.
    GDPNOW is dated by quarter: the row for 2026-07-01 is the CURRENT Q3
    nowcast, not a stale one. A flat "older than 14 days" rule against the
    observation date would blank it for roughly 85% of every quarter.

    What actually goes stale is the UPDATE. Verified against FRED directly
    on 2026-09-27: GDPNOW's last-modified was 2026-09-25, two days old,
    while its newest observation was dated 2026-07-01 -- 88 days old. Those
    two numbers are why this reads last_updated and not the date column.
    """
    params = {"series_id": series_id, "api_key": _secret("FRED_API_KEY"),
              "file_type": "json"}
    resp = requests.get("https://api.stlouisfed.org/fred/series",
                        params=params, timeout=30)
    resp.raise_for_status()
    rows = resp.json().get("seriess") or []
    return rows[0] if rows else {}


def fetch_gdp_nowcast_freshness() -> dict:
    """Is the GDPNow nowcast actually being updated?

    Judged against the cadence of its RELEASES (Atlanta Fed revises it
    roughly weekly through a quarter), never against the quarter its
    observations are dated to. cache.is_stale reports the verdict together
    with its inputs, so the call can be checked rather than believed.
    """
    import cache

    try:
        meta = _fred_series_meta("GDPNOW")
    except Exception as exc:  # noqa: BLE001 -- unavailable is not stale
        return {"available": False,
                "why": f"could not read FRED series metadata: {exc}"}

    raw = meta.get("last_updated")          # "2026-09-25 09:31:02-05"
    if not raw:
        return {"available": False, "why": "FRED returned no last_updated"}
    last_updated_date = raw.split(" ")[0]

    verdict = cache.is_stale(last_updated_date, "weekly")
    newest_obs = None
    try:
        recs = cache.get_or_fetch("gdp_nowcast", fetch_gdp_nowcast)
        if recs:
            newest_obs = recs[-1]["date"]
    except Exception:  # noqa: BLE001 -- the freshness read must not fail the page
        pass

    return {
        "available": True,
        "last_updated": raw,
        "newest_observation": newest_obs,
        **verdict,
        "note": ("Measured against how often GDPNow is REVISED, not against the "
                 "quarter its rows are dated to. The newest row is dated to the "
                 "start of the quarter being nowcast, so it is always months "
                 "'old' by date while being days old in fact."),
    }


# ── inflation (24h TTL) ──────────────────────────────────────────────────

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_SERIES = {
    "CUUR0000SA0": "CPI",
    "CUUR0000SA0L1E": "Core CPI",
    "WPUFD49104": "PPI",
}


def _bls_post(series_ids: list[str], start_year: int, end_year: int) -> dict:
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
        "registrationkey": _secret("BLS_API_KEY"),
    }
    resp = requests.post(BLS_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_inflation() -> list[dict]:
    """BLS CPI/Core CPI/PPI NSA index levels converted to YoY%.
    Records: {date, CPI, Core CPI, PPI}."""
    import time

    series_ids = list(BLS_SERIES.keys())
    current_year = datetime.datetime.now().year
    long_rows: list[dict] = []

    for start, end in [
        (current_year - 39, current_year - 20),
        (current_year - 19, current_year),
    ]:
        result = _bls_post(series_ids, start, end)
        for series in result.get("Results", {}).get("series", []):
            sid = series["seriesID"]
            label = BLS_SERIES.get(sid, sid)
            for obs in series.get("data", []):
                period = obs.get("period", "M00")
                if not period.startswith("M") or period == "M13":
                    continue
                try:
                    month = int(period[1:])
                    val = float(obs["value"])
                except (ValueError, KeyError):
                    continue
                long_rows.append({
                    "date": pd.Timestamp(year=int(obs["year"]), month=month, day=1),
                    "series": label,
                    "value": val,
                })
        time.sleep(0.5)  # respect BLS rate limits

    if not long_rows:
        return []

    long_df = pd.DataFrame(long_rows)
    wide = long_df.pivot_table(index="date", columns="series", values="value", aggfunc="last").sort_index()

    result_df = pd.DataFrame(index=wide.index)
    for col in ["CPI", "Core CPI", "PPI"]:
        if col in wide.columns:
            result_df[col] = wide[col].pct_change(12) * 100

    result_df = result_df.dropna(how="all").reset_index()
    return _df_to_records(result_df)


# ── pce (24h TTL) ────────────────────────────────────────────────────────

BEA_URL = "https://apps.bea.gov/api/data"


def _bea_get(params: dict) -> dict:
    params = dict(params)
    params["UserID"] = _secret("BEA_API_KEY")
    params["ResultFormat"] = "JSON"
    resp = requests.get(BEA_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_pce() -> list[dict]:
    """BEA NIPA T20804 -- Core PCE (ex-food-&-energy) chain-type price
    INDEX level (CL_UNIT="Level", ~127-130 -- NOT a pre-computed rate).
    Bug found 2026-09-06 (this was a verbatim port of a real bug in
    Streamlit's macro_data.py: the raw index level was stored as
    pce_core_pct and compounded as if it were a monthly rate, producing
    ~1.8 million instead of ~2-3% YoY). Fixed here and in
    ~/market-dashboard/macro_data.py with the same math: exact-match the
    "PCE excluding food and energy" line (not the substring match, which
    also caught the different "Market-based" series), YoY = 12-month
    index ratio, not a compounded rate. Validated against FRED PCEPILFE
    for 2026-07: 3.34414% both sides, matches to 4+ decimal places.
    Records: {date, pce_core_yoy}, last 10 years only, NaN-dropped."""
    data = _bea_get({
        "method": "GetData",
        "DataSetName": "NIPA",
        "TableName": "T20804",
        "Frequency": "M",
        "Year": "ALL",
    })
    rows = data["BEAAPI"]["Results"]["Data"]
    records = []
    for r in rows:
        if r.get("LineDescription", "") == "PCE excluding food and energy":
            tp = r["TimePeriod"]  # e.g. "2024M07"
            try:
                year = int(tp[:4])
                month = int(tp[5:7])
                val = float(r["DataValue"].replace(",", ""))
            except (ValueError, AttributeError, IndexError):
                continue
            records.append({"date": pd.Timestamp(year=year, month=month, day=1), "pce_core_index": val})

    df = pd.DataFrame(records).sort_values("date").reset_index(drop=True)
    df = df.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    if df.empty:
        return []

    df["pce_core_yoy"] = (df["pce_core_index"] / df["pce_core_index"].shift(12) - 1) * 100
    cutoff = pd.Timestamp.now() - pd.DateOffset(years=10)
    out = df[df["date"] >= cutoff].dropna(subset=["pce_core_yoy"]).reset_index(drop=True)
    return _df_to_records(out[["date", "pce_core_yoy"]])


# ── dot_plot (7d TTL) ─────────────────────────────────────────────────

import pathlib

DOT_PLOT_PATH = pathlib.Path(__file__).parent / "data_manual" / "dot_plot.csv"


def fetch_dot_plot() -> list[dict]:
    """SEP dot-plot from the static data_manual/dot_plot.csv, bundled with
    the deploy (not a live external fetch). Records: {year, participant_id,
    projected_rate}. Verbatim port of fomc_data.load_dot_plot()."""
    if not DOT_PLOT_PATH.exists():
        return []
    df = pd.read_csv(DOT_PLOT_PATH, comment="#")
    df["year"] = df["year"].astype(str)
    df["participant_id"] = pd.to_numeric(df["participant_id"], errors="coerce")
    df["projected_rate"] = pd.to_numeric(df["projected_rate"], errors="coerce")
    df = df.dropna(subset=["participant_id", "projected_rate"]).reset_index(drop=True)
    df["participant_id"] = df["participant_id"].astype(int)
    return df.to_dict(orient="records")


# ── Endpoint orchestration ────────────────────────────────────────────

def build_rates_response() -> dict:
    import cache

    all_meetings_iso = cache.get_or_fetch("fomc_meeting_calendar", _fetch_fomc_meeting_calendar)
    meetings_iso = _filter_meetings_by_horizon(all_meetings_iso)

    return {
        "fed_funds_range": cache.get_or_fetch("fed_funds_range", fetch_fed_funds_range),
        "fomc_meeting_calendar": meetings_iso,
        "fomc_probabilities": cache.get_or_fetch(
            "fomc_probabilities", lambda: build_fomc_probabilities(meetings_iso)
        ),
        "treasury_curve": _trim_treasury_curve(cache.get_or_fetch("treasury_curve", fetch_treasury_curve)),
        "spreads": cache.get_or_fetch("spreads", fetch_spreads),
    }


def build_growth_response() -> dict:
    import cache

    return {
        "lending_standards": cache.get_or_fetch("lending_standards", fetch_lending_standards),
        "challenger": cache.get_or_fetch("challenger", fetch_challenger),
        "gdp": cache.get_or_fetch("gdp", fetch_gdp),
        "gdp_nowcast": cache.get_or_fetch("gdp_nowcast", fetch_gdp_nowcast),
        "gdp_nowcast_freshness": cache.get_or_fetch(
            "gdp_nowcast_freshness", fetch_gdp_nowcast_freshness),
        "inflation": cache.get_or_fetch("inflation", fetch_inflation),
        "pce": cache.get_or_fetch("pce", fetch_pce),
    }


def build_dot_plot_response() -> dict:
    import cache

    return {
        "dot_plot": cache.get_or_fetch("dot_plot", fetch_dot_plot),
    }
