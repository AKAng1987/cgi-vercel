"""
US consensus for the releases that decide the growth and inflation axes: what the market expected, set against the
previous print, kept as a growing history so the actual can be filled in later.

Why. research/consensus_gap (2026-10-30, cold-audited): on advance GDP prints 2013-2026 the growth axis flipped 24 of 27
times when the consensus implied a flip and 4 of 27 when it did not (Brier 0.259 -> 0.157, CI below zero). That is close to
mechanical (the axis is the sign of new minus previous print and the consensus estimates the new print) and says nothing
about markets. For CPI the direction is the same but the sample is too thin to claim (8 of 14 vs 4 of 147; 12 flips in 13
years). So: GDP advance gets the figure with its track record; CPI gets it labelled thin; nothing else gets it.

Where it comes from. The same weekly TradingView calendar post as country_calendar (the routine adds US to its country list
and an 11th field, the actual). country_calendar.clean drops US rows; ingest() takes them. Rows are UPSERTED on
(date, kind, title), so a later post fills in the actual rather than duplicating, and the history keeps growing.

Row (stored): {date, kind, title, period, previous, forecast, actual}   kind: gdp | cpi
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any, Optional

KEY = "calendar/us_consensus.json"
MAX_KEEP = 400          # rows kept (about 6 years of GDP + CPI)
MAX_IN = 600
PAST_DAYS = 60          # a post may carry rows this far back (so an actual can arrive late) ...
FUTURE_DAYS = 45        # ... and this far ahead
MAX_TITLE = 80

TRACK = {
    "gdp": "Advance GDP 2013-2026: when the consensus implied a flip the growth axis flipped 24 of 27 times, when it implied none 4 of 27 (consensus_gap study). Close to mechanical; says nothing about markets.",
    "cpi": "Thin: CPI YoY 2013-2026 flipped 8 of 14 when implied vs 4 of 147 when not, but there are only 12 inflation flips in 13 years. No claim.",
}


def classify(indicator: Any, title: Any) -> Optional[str]:
    """gdp for a US quarter-on-quarter GDP row, cpi for headline CPI year-on-year; None for everything else."""
    ind, ttl = str(indicator or "").strip(), str(title or "").strip()
    if ind == "GDP Growth Rate" and "QoQ" in ttl:
        return "gdp"
    if ind == "Inflation Rate" and ttl == "Inflation Rate YoY":
        return "cpi"
    return None


def _num(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 4) if abs(f) < 1e6 else None


def parse(rows: Any, today: Optional[dt.date] = None) -> tuple[list[dict], dict]:
    """Keep the valid US rows from a country_calendar post (compact lists, FIELDS plus an optional 11th: actual)."""
    today = today or dt.datetime.now(dt.timezone.utc).date()
    report = {"received": 0, "kept": 0, "dropped": {}}

    def drop(why: str) -> None:
        report["dropped"][why] = report["dropped"].get(why, 0) + 1

    if not isinstance(rows, list):
        return [], report
    lo, hi = today - dt.timedelta(days=PAST_DAYS), today + dt.timedelta(days=FUTURE_DAYS)
    out = []
    for r in rows[:MAX_IN]:
        if not isinstance(r, (list, tuple)) or len(r) < 10 or r[0] != "US":
            continue
        report["received"] += 1
        date_s, title, indicator, period, prev, fc = r[1], r[2], r[3], r[5], r[6], r[7]
        actual = r[10] if len(r) > 10 else None
        kind = classify(indicator, title)
        if kind is None:
            drop("not gdp/cpi")
            continue
        try:
            d = dt.date.fromisoformat(str(date_s)[:10])
        except ValueError:
            drop("date")
            continue
        if not lo <= d <= hi:
            drop("outside window")
            continue
        out.append({"date": d.isoformat(), "kind": kind, "title": str(title).strip()[:MAX_TITLE],
                    "period": (str(period)[:12] if period else None), "previous": _num(prev), "forecast": _num(fc),
                    "actual": _num(actual)})
    report["kept"] = len(out)
    return out, report


def merge(old: list[dict], new: list[dict]) -> list[dict]:
    """Upsert on (date, kind, title). A value the new post lacks never erases one already stored (forecasts disappear from
    the calendar once a release prints; the stored forecast is the record)."""
    by = {(r["date"], r["kind"], r["title"]): dict(r) for r in old}
    for r in new:
        k = (r["date"], r["kind"], r["title"])
        cur = by.get(k)
        if cur is None:
            by[k] = dict(r)
        else:
            for f in ("period", "previous", "forecast", "actual"):
                if r.get(f) is not None:
                    cur[f] = r[f]
    rows = sorted(by.values(), key=lambda x: (x["date"], x["kind"]))
    return rows[-MAX_KEEP:]


def read() -> dict:
    import cache

    try:
        obj = cache._s3.get_object(Bucket=cache.BUCKET, Key=cache.PREFIX + KEY)
        body = json.loads(obj["Body"].read().decode("utf-8"))
        return {"at": body.get("at"), "rows": body.get("rows") if isinstance(body.get("rows"), list) else []}
    except Exception as exc:  # noqa: BLE001 -- never written is a valid answer
        return {"at": None, "rows": [], "why": f"no US consensus stored ({type(exc).__name__})"}


def ingest(rows: Any) -> dict:
    """Parse the US rows of a calendar post and merge them into the stored history. Never raises into the caller."""
    try:
        import cache

        new, report = parse(rows)
        if not new:
            return {**report, "stored": 0}
        old = read().get("rows", [])
        merged = merge(old, new)
        body = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "rows": merged}
        cache._s3.put_object(Bucket=cache.BUCKET, Key=cache.PREFIX + KEY, Body=json.dumps(body).encode("utf-8"),
                             ContentType="application/json")
        return {**report, "stored": len(merged)}
    except Exception as exc:  # noqa: BLE001 -- additive; the country calendar must still be stored
        return {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}


def implied(kind: str, release_date: str, state: int, snapshot: dict) -> Optional[dict]:
    """What the consensus implies for the axis at this release, or None when no row with a forecast and a previous exists.

    The axis is the sign of (new print - previous print), so with the axis UP (state 1) a flip needs the new print BELOW
    the previous one, and with it DOWN a print ABOVE. The consensus is the estimate of the new print."""
    d0 = dt.date.fromisoformat(release_date)
    best = None
    for r in snapshot.get("rows", []):
        if r.get("kind") != kind or r.get("forecast") is None or r.get("previous") is None:
            continue
        gap_days = abs((dt.date.fromisoformat(r["date"]) - d0).days)
        if gap_days <= 3 and (best is None or gap_days < best[0]):
            best = (gap_days, r)
    if best is None:
        return None
    r = best[1]
    fc, prev = float(r["forecast"]), float(r["previous"])
    g = (prev - fc) if state == 1 else (fc - prev)
    return {"kind": kind, "forecast": fc, "previous": prev, "implied_flip": bool(g > 0), "gap": round(g, 4),
            "tie": bool(g == 0), "row_date": r["date"], "as_of": snapshot.get("at"), "track": TRACK.get(kind)}


def missing_forecasts(today: dt.date, snapshot: dict, releases: list[dict], days: int = 4) -> list[str]:
    """Release dates (CPI, GDP advance) in the next `days` days for which no forecast has been stored yet. TradingView
    posts the consensus only a few days before a print, so a weekly calendar pull can miss it; the routine uses this
    to fetch the calendar again while one is outstanding, so the figure is pre-registered before the release."""
    out = []
    end = today + dt.timedelta(days=days)
    for r in releases:
        if not (r["type"] == "CPI" or (r["type"] == "GDP" and r.get("subtype") == "advance")):
            continue
        d = dt.date.fromisoformat(r["date"])
        if not today <= d <= end:
            continue
        kind = "cpi" if r["type"] == "CPI" else "gdp"
        have = any(x.get("kind") == kind and x.get("forecast") is not None and x.get("previous") is not None
                   and abs((dt.date.fromisoformat(x["date"]) - d).days) <= 3 for x in snapshot.get("rows", []))
        if not have:
            out.append(r["date"])
    return out
