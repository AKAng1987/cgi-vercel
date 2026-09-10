"""
BACKTEST tab data: serve regime-conditioned ticker stats.

Refresh compute moved off Render into cmon-stage-backend-backtest-
refresher (ap-southeast-1 Lambda, daily 03:30 UTC) -- see
PHASE3_LAMBDA_REWRITE.md for the full migration rationale (Render's
~75s TCP-connect delay made refresh's timing budget unworkable there).
This module is now read-only: it serves the single S3 blob the Lambda
writes.

Storage layout (Cache/backtest/):
  occurrences.json  -- {schema_version, last_refreshed_at,
                        tickers: {ticker: {group, combos}}}
                        combos keyed "{grid_q}_{compass_q}" -> list of
                        occurrence dicts.

The chunked/manifest layout (manifest.json + occurrences_chunk_{0-3}.json,
hash-sharded via the now-removed chunk_for_ticker/refresh_chunk/
refresh_tickers machinery) existed only to fit refreshes inside
Render's per-request timing ceiling. A Lambda has no such ceiling, so
it always writes one full blob; there is no longer a reason to shard
reads either.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

import dashboard_data

REGION = "ap-southeast-1"
BUCKET = "cmon-stage-backend-369568916817-ap-southeast-1-reports"
PREFIX = "Cache/backtest/"
BLOB_KEY = f"{PREFIX}occurrences.json"

# Compared against the blob's own schema_version by callers that care;
# bump alongside cmon-stage-backend-backtest-refresher's handler.py if
# the occurrence/stat computation logic ever changes.
SCHEMA_VERSION = 1

BACKTEST_EXCLUDE_GROUPS = frozenset({
    "US INTEREST RATES", "SPREADS", "RATES", "FOREIGN RATES"
})

_logger = logging.getLogger("cgi_api.backtest_data")
_s3 = boto3.client("s3", region_name=REGION)


def _combo_key(grid_q: int, compass_q: int) -> str:
    return f"{grid_q}_{compass_q}"


def build_backtest_universe() -> tuple[list[str], dict[str, str]]:
    """Same derivation as app.py's _build_backtest_universe(), reusing
    dashboard_data.HUD_GROUPS so the universe can't silently drift from
    what the LIVE tab already ports."""
    universe: list[str] = []
    ticker_group: dict[str, str] = {}
    seen: set = set()
    for gname, (tickers, _) in dashboard_data.HUD_GROUPS.items():
        if gname in BACKTEST_EXCLUDE_GROUPS:
            continue
        for t in tickers:
            if t not in seen:
                seen.add(t)
                universe.append(t)
                ticker_group[t] = gname
    return universe, ticker_group


BACKTEST_UNIVERSE, TICKER_GROUP_MAP = build_backtest_universe()


def compute_stats(occurrences: list[dict]) -> Optional[dict]:
    """Direct port of backtest_engine.compute_stats, no pandas. Kept
    here (not just in the Lambda) because build_table_response applies
    it per-ticker after a lookback filter, which is a read-time
    concern -- the Lambda's blob stores raw occurrences, unfiltered."""
    if not occurrences:
        return None
    count = len(occurrences)
    avg_high = sum(o["high_pct"] for o in occurrences) / count
    avg_low = sum(o["low_pct"] for o in occurrences) / count
    hit_count = sum(1 for o in occurrences if o["return_pct"] > 0)
    hit_rate = hit_count / count * 100.0
    edge = (avg_high / abs(avg_low)) if avg_low < 0 else None
    avg_return = sum(o["return_pct"] for o in occurrences) / count
    return {
        "count": count,
        "avg_high_pct": round(avg_high, 2),
        "avg_low_pct": round(avg_low, 2),
        "hit_rate": round(hit_rate, 1),
        "edge": round(edge, 2) if edge is not None else None,
        "avg_return": round(avg_return, 2),
    }


def _s3_get_json(key: str) -> Optional[dict]:
    try:
        obj = _s3.get_object(Bucket=BUCKET, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return None
        raise
    return json.loads(obj["Body"].read().decode("utf-8"))


def _read_blob() -> Optional[dict]:
    return _s3_get_json(BLOB_KEY)


def build_table_response(
    compass_q: int,
    grid_q: int,
    min_occ: int = 5,
    lookback: Optional[str] = None,
) -> dict:
    """Read the single blob once and return the aggregated per-ticker
    stats table for one (compass_q, grid_q) combo, sorted by Edge
    descending. lookback: None/"all" | "10y" | "5y" -- filters
    occurrences by start_date before aggregating, same semantics as
    the Streamlit tab."""
    blob = _read_blob()
    if blob is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "last_refreshed_at": None,
            "compass_q": compass_q,
            "grid_q": grid_q,
            "rows": [],
            "error": "no backtest data refreshed yet",
        }

    cutoff = None
    if lookback in ("10y", "5y"):
        years = 10 if lookback == "10y" else 5
        today = datetime.now(timezone.utc).date()
        cutoff = today.replace(year=today.year - years).isoformat()

    combo_key = _combo_key(grid_q, compass_q)
    rows = []

    for sym, entry in blob["tickers"].items():
        occ = entry["combos"].get(combo_key, [])
        if cutoff:
            occ = [o for o in occ if o["start_date"] >= cutoff]
        stats = compute_stats(occ)
        if stats is None or stats["count"] < min_occ:
            continue
        rows.append({
            "ticker": sym,
            "group": entry["group"],
            "occurrences": stats["count"],
            "avg_high_pct": stats["avg_high_pct"],
            "avg_low_pct": stats["avg_low_pct"],
            "hit_rate": stats["hit_rate"],
            "edge": stats["edge"],
            "avg_return_pct": stats["avg_return"],
        })

    rows.sort(key=lambda r: (r["edge"] is None, -(r["edge"] or 0)))

    return {
        "schema_version": blob.get("schema_version", SCHEMA_VERSION),
        "last_refreshed_at": blob.get("last_refreshed_at"),
        "compass_q": compass_q,
        "grid_q": grid_q,
        "min_occ": min_occ,
        "lookback": lookback or "all",
        "rows": rows,
    }


def build_occurrences_response(ticker: str, compass_q: int, grid_q: int) -> dict:
    """Read the single blob and return raw occurrences for one
    ticker/combo."""
    blob = _read_blob()
    if blob is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "last_refreshed_at": None,
            "ticker": ticker,
            "compass_q": compass_q,
            "grid_q": grid_q,
            "occurrences": [],
            "error": "no backtest data refreshed yet",
        }

    combo_key = _combo_key(grid_q, compass_q)
    entry = blob["tickers"].get(ticker)
    occ = entry["combos"].get(combo_key, []) if entry else []

    return {
        "schema_version": blob.get("schema_version", SCHEMA_VERSION),
        "last_refreshed_at": blob.get("last_refreshed_at"),
        "ticker": ticker,
        "compass_q": compass_q,
        "grid_q": grid_q,
        "occurrences": occ,
    }
