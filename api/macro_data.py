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
    """FRED T10Y2Y + BAMLH0A0HYM2, 20-year lookback."""
    start = (datetime.datetime.now() - datetime.timedelta(days=365 * 20)).strftime("%Y-%m-%d")
    dfs: dict = {}
    for sid, label in [("T10Y2Y", "T10Y2Y"), ("BAMLH0A0HYM2", "HY_Spread")]:
        df_s = _fred_get(sid, observation_start=start)
        if not df_s.empty:
            dfs[label] = df_s.set_index("date")["value"]
    wide = pd.DataFrame(dfs).sort_index().reset_index().rename(columns={"index": "date"})
    return _df_to_records(wide)


# ── fomc_meeting_calendar (7d TTL) ────────────────────────────────────

def _scrape_fomc_dates() -> list[datetime.date]:
    try:
        resp = requests.get(
            "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            timeout=10,
        )
        resp.raise_for_status()
        raw = re.findall(r"20[2-9][0-9][01][0-9][0-3][0-9]", resp.text)
        dates = []
        for s in sorted(set(raw)):
            try:
                dates.append(datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8])))
            except ValueError:
                continue
        return dates
    except Exception:
        return []


def get_upcoming_meetings(today: Optional[datetime.date] = None, horizon_months: int = 12) -> list[dict]:
    """Returns [{"date": "YYYY-MM-DD"}, ...] for meetings from today through
    today+horizon_months."""
    if today is None:
        today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=horizon_months * 31)

    candidates = list(FOMC_2026)
    scraped = _scrape_fomc_dates()
    known = set(candidates)
    for d in scraped:
        if d.year > 2026 and d not in known:
            candidates.append(d)
            known.add(d)

    meetings = sorted(d for d in candidates if today <= d <= cutoff)
    return [{"date": d.isoformat()} for d in meetings]


# ── fomc_probabilities (6h TTL, yfinance-dependent) ───────────────────

def fetch_effr() -> list[dict]:
    """FRED DFF, last 30 days."""
    start = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    df = _fred_get("DFF", observation_start=start).sort_values("date").reset_index(drop=True)
    return _df_to_records(df)


def _futures_ticker(year: int, month: int) -> str:
    return f"ZQ{_MONTH_CODE[month]}{str(year)[-2:]}.CBT"


def fetch_futures_for_meetings(meetings: list[datetime.date]) -> dict[datetime.date, float]:
    """{meeting_date: implied_avg_rate_%} from ZQ monthly contracts via yfinance."""
    import yfinance as yf

    result: dict[datetime.date, float] = {}
    for mtg in meetings:
        ticker = _futures_ticker(mtg.year, mtg.month)
        try:
            hist = yf.Ticker(ticker).history(period="5d")
            if hist.empty:
                continue
            price = float(hist["Close"].iloc[-1])
            result[mtg] = round(100.0 - price, 6)
        except Exception:
            continue
    return result


def compute_fomc_probs(
    meetings: list[datetime.date],
    effr_records: list[dict],
    upper_target: float,
    lower_target: float,
    futures: dict[datetime.date, float],
) -> list[dict]:
    """CME FedWatch methodology -- verbatim port of fomc_data.compute_fomc_probs,
    adapted to take/return plain dicts instead of a DataFrame."""
    if effr_records:
        current_effr = float(sorted(effr_records, key=lambda r: r["date"])[-1]["value"])
    else:
        current_effr = (upper_target + lower_target) / 2

    midpoint = (upper_target + lower_target) / 2
    increment = 0.25

    results = []
    pre_rate = current_effr

    for mtg in sorted(meetings):
        if mtg not in futures:
            continue

        implied_avg = futures[mtg]
        total_days = calendar.monthrange(mtg.year, mtg.month)[1]
        days_before = mtg.day
        days_after = total_days - mtg.day

        if days_after <= 0:
            post_rate = implied_avg
        else:
            post_rate = (implied_avg * total_days - pre_rate * days_before) / days_after

        current_mid = midpoint

        if post_rate <= current_mid:
            p_cut = min(1.0, max(0.0, (current_mid - post_rate) / increment))
            p_hold = 1.0 - p_cut
            p_hike = 0.0
        else:
            p_hike = min(1.0, max(0.0, (post_rate - current_mid) / increment))
            p_hold = 1.0 - p_hike
            p_cut = 0.0

        if p_hold >= max(p_cut, p_hike):
            most_likely, prob_ml = "Hold", p_hold
        elif p_cut > p_hike:
            most_likely, prob_ml = "Cut 25bp", p_cut
        else:
            most_likely, prob_ml = "Hike 25bp", p_hike

        results.append({
            "date": mtg.isoformat(),
            "ticker": _futures_ticker(mtg.year, mtg.month),
            "implied_avg": round(implied_avg, 4),
            "pre_rate": round(pre_rate, 4),
            "post_rate": round(post_rate, 4),
            "p_cut": round(p_cut, 4),
            "p_hold": round(p_hold, 4),
            "p_hike": round(p_hike, 4),
            "most_likely": most_likely,
            "prob_most_likely": round(prob_ml, 4),
        })

        pre_rate = p_cut * (current_mid - increment) + p_hold * current_mid + p_hike * (current_mid + increment)

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

    meetings_iso = cache.get_or_fetch("fomc_meeting_calendar", get_upcoming_meetings)

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
        "gdp": cache.get_or_fetch("gdp", fetch_gdp),
        "gdp_nowcast": cache.get_or_fetch("gdp_nowcast", fetch_gdp_nowcast),
        "inflation": cache.get_or_fetch("inflation", fetch_inflation),
        "pce": cache.get_or_fetch("pce", fetch_pce),
    }


def build_dot_plot_response() -> dict:
    import cache

    return {
        "dot_plot": cache.get_or_fetch("dot_plot", fetch_dot_plot),
    }
