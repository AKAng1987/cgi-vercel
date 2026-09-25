"""
fundamentals_history.py -- remembering what the filings said last quarter.

WHY THIS EXISTS
The fundamentals factor recomputed from scratch on every run and discarded the
previous one, so it could describe a company but never say what had CHANGED
about it. That single gap blocked both things the brief needs: "AMD flipped
from capturing to slowing" and "MU just posted the largest acceleration in the
universe".

Most of CGI's change detection needs no store at all -- themes carry an onset
date, breadth carries its last cross, the Markov layer carries event dates, so
"what changed" is read straight off the data. Fundamentals are the exception:
a filing does not announce that it differs from the last one. Hence this.

APPEND ON A NEW FILING, NOT ON EVERY RUN
The endpoint recomputes on a 24h cache cycle. Writing a row per run would
record the cache schedule, not the company -- dozens of identical rows between
two filings, and a "change" every time a rounding difference appeared. A row
is appended only when a company's `as_of` (its latest filed quarter) differs
from the newest row already stored, which is exactly once per report.

THRESHOLDS ARE MEASURED
"Sudden revenue growth" is not a number anyone picked. The distribution of
quarterly revenue acceleration was measured across the whole universe on
2026-09-25 -- 4,545 company-quarters, 129 companies:

    p1 -111.6   p5 -35.0   p10 -18.0   p25 -5.7   p50 +0.1
    p75 +5.8    p90 +16.8  p95 +32.7   p97.5 +56.8   p99 +120.5

so SURPRISE_UP is p95 and SURPRISE_DOWN is p5. At ~129 companies reporting
quarterly that is roughly two of each per month -- rare enough to be worth a
notification, common enough to be useful. A round number like "+20pp" would
have sat at p91.8 and fired twice as often.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError

REGION = "ap-southeast-1"
BUCKET = "cmon-stage-backend-369568916817-ap-southeast-1-reports"
KEY = "Fundamentals/history.json"

MAX_PER_SYMBOL = 24          # six years of quarters is plenty

# Measured percentiles -- see the module docstring for the sample.
SURPRISE_UP = 32.7           # p95
SURPRISE_DOWN = -35.0        # p5
MEASURED = {"n": 4545, "companies": 129, "on": "2026-09-25",
            "p95": 32.7, "p5": -35.0, "p50": 0.1}

# Verdict transitions worth reporting. A move within the "still fine" band or
# within the "still weak" band is noise; crossing between them is not.
_GOOD = {"capturing", "accelerating"}
_BAD = {"rolling over", "slowing"}

_logger = logging.getLogger("cgi_api.fundamentals_history")
_s3 = boto3.client("s3", region_name=REGION)


def load() -> dict[str, list[dict]]:
    try:
        obj = _s3.get_object(Bucket=BUCKET, Key=KEY)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return {}
        raise
    try:
        return json.loads(obj["Body"].read().decode("utf-8"))
    except json.JSONDecodeError:
        _logger.error("[fund-history] blob is not valid JSON; starting empty")
        return {}


def save(hist: dict[str, list[dict]]) -> None:
    _s3.put_object(Bucket=BUCKET, Key=KEY,
                   Body=json.dumps(hist, allow_nan=False).encode("utf-8"),
                   ContentType="application/json")


def _row(c: dict) -> Optional[dict]:
    r = c.get("revenue") or {}
    if r.get("status") != "ok" or not r.get("as_of"):
        return None
    m = c.get("margin") or {}
    return {
        "as_of": r["as_of"],
        "verdict": (c.get("read") or {}).get("verdict"),
        "yoy_pct": r.get("yoy_pct"),
        "acceleration_pp": r.get("acceleration_pp"),
        "margin_change_yoy_pp": m.get("margin_change_yoy_pp") if m.get("status") == "ok" else None,
        "seen": dt.date.today().isoformat(),
    }


def record(companies: list[dict]) -> list[dict]:
    """Append any newly-filed quarter and return what changed.

    Safe to call on every build: a company whose `as_of` is unchanged writes
    nothing and reports nothing.
    """
    try:
        hist = load()
    except Exception:
        _logger.exception("[fund-history] could not load; skipping this cycle")
        return []

    changes: list[dict] = []
    dirty = False

    for c in companies:
        if c.get("status") != "ok":
            continue
        row = _row(c)
        if row is None:
            continue
        sym = c["symbol"]
        rows = hist.setdefault(sym, [])
        if rows and rows[-1].get("as_of") == row["as_of"]:
            continue                                  # already have this filing

        prev = rows[-1] if rows else None
        rows.append(row)
        del rows[:-MAX_PER_SYMBOL]
        dirty = True

        if prev is None:
            continue                                  # first sighting is not a change

        acc = row.get("acceleration_pp")
        if acc is not None and (acc >= SURPRISE_UP or acc <= SURPRISE_DOWN):
            changes.append({
                "kind": "fundamentals_surprise",
                "symbol": sym, "as_of": row["as_of"],
                "acceleration_pp": acc, "yoy_pct": row.get("yoy_pct"),
                "direction": "up" if acc >= SURPRISE_UP else "down",
                "detail": (f"{sym} revenue {row.get('yoy_pct')}% YoY, "
                           f"acceleration {acc:+.1f}pp "
                           f"({'p95' if acc >= SURPRISE_UP else 'p5'} of the measured distribution)"),
            })

        a, b = prev.get("verdict"), row.get("verdict")
        if a != b and not ({a, b} <= _GOOD or {a, b} <= _BAD):
            changes.append({
                "kind": "fundamentals_verdict",
                "symbol": sym, "as_of": row["as_of"],
                "from": a, "to": b,
                "detail": f"{sym} {a} -> {b} on the {row['as_of']} quarter",
            })

    if dirty:
        try:
            save(hist)
        except Exception:
            _logger.exception("[fund-history] save failed; changes still reported")
    return changes


def recent(days: int = 45) -> list[dict]:
    """Filings first seen within the window, newest first -- what the brief
    reports as 'reported since you last looked'."""
    cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
    out = []
    for sym, rows in load().items():
        for i, r in enumerate(rows):
            if r.get("seen", "") >= cutoff and i > 0:
                out.append({"symbol": sym, **r, "prev_verdict": rows[i - 1].get("verdict")})
    out.sort(key=lambda r: (r.get("seen", ""), r.get("as_of", "")), reverse=True)
    return out
