"""
rate_path.py -- what futures price for the policy rate AFTER each FOMC meeting, and further out than the meetings reach.

Two strips, both free through yfinance (the same source the FedWatch-style odds already use):
  ZQ  30-day fed funds futures, monthly: macro_data.build_fomc_probabilities already backs out the expected rate after each
      meeting (post_rate, carried forward meeting by meeting, de-averaged or read off the next month's contract). Reused here,
      not recomputed.
  SR3 three-month SOFR futures, quarterly: 100 - price is the average SOFR expected over the contract's reference quarter
      (third Wednesday of the contract month to the third Wednesday three months on). Liquid for about three years, so it
      shows the path beyond the last meeting ZQ prices.

Two different rates: ZQ is on EFFR, SR3 on SOFR. They normally sit within a few basis points; the page shows the current
SOFR-EFFR gap and each SR3 point against the ZQ path over the same window where there is one, and never nets them away.
Descriptive display of what is PRICED, not a forecast, and nothing here sets a regime.

The method is our own FedWatch-style arithmetic; no third-party report's text or code is used.
A daily snapshot of the priced path is appended (S3 stir/history.json) so the page can show how the pricing has moved.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

SCHEMA_VERSION = 1
HISTORY_KEY = "stir/history.json"        # under cache.PREFIX
KEEP_DAYS = 400
N_SR3 = 12                               # quarterly SOFR contracts shown (about three years)
QUARTER_MONTHS = (3, 6, 9, 12)
_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}
_MON = {3: "Mar", 6: "Jun", 9: "Sep", 12: "Dec"}
_logger = logging.getLogger("cgi_api.rate_path")


# ── dates ───────────────────────────────────────────────────────────────────

def third_wednesday(year: int, month: int) -> dt.date:
    d = dt.date(year, month, 1)
    first_wed = d + dt.timedelta(days=(2 - d.weekday()) % 7)
    return first_wed + dt.timedelta(days=14)


def sr3_contracts(today: dt.date, n: int = N_SR3) -> list[dict]:
    """The next n quarterly SOFR contracts whose reference quarter has not ended: ticker, label, start, end."""
    out = []
    y = today.year
    while len(out) < n:
        for m in QUARTER_MONTHS:
            ny, nm = (y + (m + 3 > 12), (m + 3 - 1) % 12 + 1)
            start, end = third_wednesday(y, m), third_wednesday(ny, nm)
            if end <= today:
                continue
            out.append({"ticker": f"SR3{_CODE[m]}{str(y)[-2:]}.CME", "label": f"{_MON[m]} {y}",
                        "start": start.isoformat(), "end": end.isoformat()})
            if len(out) >= n:
                break
        y += 1
    return out


def path_average(steps: list[tuple[dt.date, float]], base: float, start: dt.date, end: dt.date) -> Optional[float]:
    """Time-weighted average of the step path over [start, end). `steps` = (meeting date, rate AFTER it), ascending; the rate
    before the first meeting is `base`. A meeting takes effect the day after it (DFEDTARU's effective-date convention)."""
    if end <= start:
        return None
    total = 0.0
    cur = base
    t = start
    pts = [(d + dt.timedelta(days=1), r) for d, r in steps]
    for eff, rate in pts:
        if eff <= start:
            cur = rate
            continue
        if eff >= end:
            break
        total += cur * (eff - t).days
        t, cur = eff, rate
    total += cur * (end - t).days
    return total / (end - start).days


# ── pure assembly (what the check script tests) ─────────────────────────────

def assemble(probs: dict, sr3_quotes: dict[str, Optional[float]], sofr: Optional[dict], history: list[dict],
             today: dt.date) -> dict:
    effr = probs.get("effr_latest")
    meetings, steps = [], []
    for p in probs.get("probabilities", []):
        if p.get("available") is False:
            meetings.append({"date": p["date"], "available": False, "reason": p.get("reason")})
            continue
        step_bp = round((p["post_rate"] - p["pre_rate"]) * 100, 1)
        cum_bp = round((p["post_rate"] - effr) * 100, 1) if effr is not None else None
        meetings.append({"date": p["date"], "available": True, "post_rate": round(p["post_rate"], 3), "step_bp": step_bp,
                         "cum_bp": cum_bp, "p_hike": p["p_hike"], "p_hold": p["p_hold"], "p_cut": p["p_cut"],
                         "most_likely": p["most_likely"], "confident": p.get("confident", True), "ticker": p.get("ticker")})
        steps.append((dt.date.fromisoformat(p["date"]), float(p["post_rate"])))

    sr3 = []
    for c in sr3_contracts(today):
        price = sr3_quotes.get(c["ticker"])
        row = {**c, "price": price, "implied_sofr": round(100 - price, 3) if price is not None else None}
        if price is not None and effr is not None and steps:
            avg = path_average(steps, float(effr), dt.date.fromisoformat(c["start"]), dt.date.fromisoformat(c["end"]))
            # only comparable where the ZQ path covers the whole window
            covered = dt.date.fromisoformat(c["end"]) <= steps[-1][0] + dt.timedelta(days=1)
            row["zq_path_avg"] = round(avg, 3) if (avg is not None and covered) else None
            row["vs_zq_bp"] = round((row["implied_sofr"] - avg) * 100, 1) if (avg is not None and covered) else None
        sr3.append(row)

    # Highest and lowest rate on each strip, kept apart: SOFR futures are the liquid curve, while the later fed funds
    # contracts trade thinly, so mixing them would let one stale far quote set the headline.
    def extreme(pts, fn):
        if not pts:
            return None
        d, r = fn(pts, key=lambda x: x[1])
        return {"date": d, "rate": r, "bp_vs_now": round((r - effr) * 100, 1) if effr is not None else None}

    zq_pts = [(m["date"], m["post_rate"]) for m in meetings if m.get("available")]
    sr_pts = [(s["start"], s["implied_sofr"]) for s in sr3 if s.get("implied_sofr") is not None]
    sofr_gap = round((sofr["value"] - effr) * 100, 1) if (sofr and effr is not None) else None

    out = {"as_of": today.isoformat(), "effr": effr, "target": [probs.get("lower_target"), probs.get("upper_target")],
           "sofr": sofr, "sofr_minus_effr_bp": sofr_gap, "meetings": meetings, "sr3": sr3,
           "peak_sofr": extreme(sr_pts, max), "trough_sofr": extreme(sr_pts, min),
           "peak_fed_funds": extreme(zq_pts, max)}
    out["moved"] = moved(out, history, today)
    return out


def _snap(out: dict) -> dict:
    return {"date": out["as_of"], "effr": out["effr"],
            "meetings": [[m["date"], m["post_rate"]] for m in out["meetings"] if m.get("available")],
            "sr3": [[s["ticker"], s["implied_sofr"]] for s in out["sr3"] if s.get("implied_sofr") is not None]}


def moved(out: dict, history: list[dict], today: dt.date) -> dict:
    """How the priced path changed against the snapshot nearest to 7 and 28 days ago (None when none that old exists)."""
    res = {}
    for label, days in (("week", 7), ("four_weeks", 28)):
        cutoff = (today - dt.timedelta(days=days)).isoformat()
        older = [h for h in history if h["date"] <= cutoff]
        if not older:
            res[label] = None
            continue
        h = max(older, key=lambda x: x["date"])
        prev_m = {d: r for d, r in h["meetings"]}
        prev_s = {t: r for t, r in h["sr3"]}
        per = [{"date": m["date"], "was": prev_m[m["date"]], "now": m["post_rate"],
                "change_bp": round((m["post_rate"] - prev_m[m["date"]]) * 100, 1)}
               for m in out["meetings"] if m.get("available") and m["date"] in prev_m]
        sr = [{"ticker": s["ticker"], "label": s["label"], "was": prev_s[s["ticker"]], "now": s["implied_sofr"],
               "change_bp": round((s["implied_sofr"] - prev_s[s["ticker"]]) * 100, 1)}
              for s in out["sr3"] if s.get("implied_sofr") is not None and s["ticker"] in prev_s]
        res[label] = {"snapshot_date": h["date"], "meetings": per, "sr3": sr}
    return res


# ── data in ─────────────────────────────────────────────────────────────────

def _fetch_sr3(tickers: list[str]) -> dict[str, Optional[float]]:
    import yfinance as yf

    def one(t: str) -> tuple[str, Optional[float]]:
        try:
            h = yf.Ticker(t).history(period="5d")
            return t, (None if h.empty else float(h["Close"].iloc[-1]))
        except Exception:  # noqa: BLE001 -- reported as missing
            return t, None

    with ThreadPoolExecutor(max_workers=6) as ex:
        return dict(ex.map(one, tickers))


def _read_history() -> list[dict]:
    import cache

    try:
        obj = cache._s3.get_object(Bucket=cache.BUCKET, Key=cache.PREFIX + HISTORY_KEY)
        rows = json.loads(obj["Body"].read().decode("utf-8"))
        return rows if isinstance(rows, list) else []
    except Exception:  # noqa: BLE001 -- not written yet is a valid answer
        return []


def _append_history(snap: dict, rows: list[dict]) -> None:
    import cache

    rows = [r for r in rows if r.get("date") != snap["date"]] + [snap]
    rows = sorted(rows, key=lambda r: r["date"])[-KEEP_DAYS:]
    cache._s3.put_object(Bucket=cache.BUCKET, Key=cache.PREFIX + HISTORY_KEY, Body=json.dumps(rows).encode("utf-8"),
                         ContentType="application/json")


def build_rate_path() -> dict:
    import cache
    import macro_data

    today = dt.datetime.now(dt.timezone.utc).date()
    meetings = macro_data._filter_meetings_by_horizon(cache.get_or_fetch("fomc_meeting_calendar", macro_data._fetch_fomc_meeting_calendar))
    probs = cache.get_or_fetch("fomc_probabilities", lambda: macro_data.build_fomc_probabilities(meetings))
    quotes = _fetch_sr3([c["ticker"] for c in sr3_contracts(today)])
    try:
        df = macro_data._fred_get("SOFR", observation_start=(today - dt.timedelta(days=20)).isoformat()).sort_values("date")
        last = df.iloc[-1]
        sofr = {"date": str(last["date"])[:10], "value": float(last["value"])}
    except Exception:  # noqa: BLE001 -- additive
        sofr = None
    history = _read_history()
    out = assemble(probs, quotes, sofr, history, today)
    out["n_sr3_quoted"] = sum(1 for s in out["sr3"] if s.get("implied_sofr") is not None)
    out["n_sr3"] = len(out["sr3"])
    out["history_days"] = len(history)
    out["caveat"] = ("What futures price, not a forecast. Fed funds futures are on EFFR, SOFR futures on SOFR; the gap between "
                     "the two rates is shown, not netted. Meeting rates are the FedWatch-style expected rate after each "
                     "meeting; SOFR points are the average expected over each contract's reference quarter.")
    try:
        if out["n_sr3_quoted"] and any(m.get("available") for m in out["meetings"]):
            _append_history(_snap(out), history)
    except Exception:  # noqa: BLE001 -- the snapshot is a bonus; never fail the page for it
        _logger.warning("[rate_path] could not store the daily snapshot", exc_info=True)
    return out
