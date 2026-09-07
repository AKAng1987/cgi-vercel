"""
BACKTEST tab data: precompute + serve regime-conditioned ticker stats.

Ported from ~/market-dashboard/backtest_engine.py (build_regime_periods,
get_occurrences, compute_stats) and app.py's BACKTEST_UNIVERSE derivation
(HUD_GROUPS minus rate/macro groups). See PHASE3_PLAN.md for the design
rationale, and PHASE3_PLAN.md's chunked-refresh addendum (2026-09-08) for
why this is sharded rather than a single blob: a full-universe refresh
measured at 127.56s against production DynamoDB, well past the ~100s
Cloudflare hard limit Render free tier sits behind. Chunking keeps every
single refresh call comfortably under that ceiling.

Storage layout (Cache/backtest/):
  manifest.json               -- schema_version, chunk_count,
                                  ticker_to_chunk, last_refreshed_at (per
                                  chunk, keyed by str(chunk_index))
  occurrences_chunk_{N}.json  -- one file per chunk: {tickers: {...}}

Ticker->chunk assignment is a stable hash (hashlib md5, NOT Python's
built-in hash() -- that's salted per-process since 3.3 and would give a
different assignment on every cold start, breaking the "same ticker
always maps to same chunk" guarantee across the refresh process and the
read process).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

import dashboard_data

REGION = "ap-southeast-1"
PRICE_TABLE = "cmon-stage-backend-price-history"
MODEL_TABLE = "cmon-stage-backend-model-history"
BUCKET = "cmon-stage-backend-369568916817-ap-southeast-1-reports"
PREFIX = "Cache/backtest/"
MANIFEST_KEY = f"{PREFIX}manifest.json"

# Bump whenever the occurrence/stat computation logic changes -- callers
# compare this against their own expected version and treat a mismatch
# as "stale, needs refresh" regardless of last_refreshed_at.
SCHEMA_VERSION = 1

# Finalized 2026-09-08 from real hash-sharded chunk profiling (not a
# naive linear extrapolation from a small sample -- that earlier
# estimate, based on 5 large-cap ETFs, predicted ~3.35s/ticker; the real
# worst-case chunk across chunk_count candidates 13/6/4/3 measured
# 0.73-1.05s/ticker instead). At chunk_count=4, the worst real chunk (38
# tickers, hash-sharded) completed in 27.88s -- ~2.1x margin under the
# 60s per-chunk budget, comfortably under Cloudflare's ~100s hard limit,
# and only 4 cron-job.org jobs to configure. chunk_count=3's worst case
# (46 tickers, 48.42s) was rejected for cutting the margin too thin.
CHUNK_COUNT = 4

BACKTEST_EXCLUDE_GROUPS = frozenset({
    "US INTEREST RATES", "SPREADS", "RATES", "FOREIGN RATES"
})

_logger = logging.getLogger("cgi_api.backtest_data")
_s3 = boto3.client("s3", region_name=REGION)
_ddb = boto3.client("dynamodb", region_name=REGION)


def _combo_key(grid_q: int, compass_q: int) -> str:
    return f"{grid_q}_{compass_q}"


def chunk_for_ticker(ticker: str, chunk_count: int = CHUNK_COUNT) -> int:
    """Deterministic, cross-process-stable ticker->chunk assignment.
    Do NOT use Python's built-in hash() here -- it's salted per-process
    (PYTHONHASHSEED) since 3.3, so the same ticker would land in a
    different chunk on every cold start."""
    digest = hashlib.md5(ticker.encode("utf-8")).hexdigest()
    return int(digest, 16) % chunk_count


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


def _fetch_model_history(model_name: str) -> list[dict]:
    """Full event log for one model (grid_US / compass_US). Mirrors
    data_cache._fetch_model_raw but returns plain dicts, no pandas."""
    paginator = _ddb.get_paginator("query")
    rows = []
    for page in paginator.paginate(
        TableName=MODEL_TABLE,
        KeyConditionExpression="model_name = :m",
        ExpressionAttributeValues={":m": {"S": model_name}},
        ScanIndexForward=True,
    ):
        for item in page["Items"]:
            rows.append({
                "metrics_date": item["metrics_date"]["S"],
                "quadrant": int(item["quadrant"]["N"]),
            })
    return rows


def _fetch_price_history(symbol: str) -> list[dict]:
    """Full price history for one symbol. Mirrors data_cache._fetch_price_raw."""
    paginator = _ddb.get_paginator("query")
    rows = []
    for page in paginator.paginate(
        TableName=PRICE_TABLE,
        KeyConditionExpression="#sym = :s",
        ExpressionAttributeNames={"#sym": "symbol"},
        ExpressionAttributeValues={":s": {"S": symbol}},
    ):
        for item in page["Items"]:
            close = item.get("close", {}).get("N")
            if close is None:
                continue
            high = item.get("high", {}).get("N", close)
            low = item.get("low", {}).get("N", close)
            rows.append({
                "date": item["date"]["S"],
                "close": float(close),
                "high": float(high),
                "low": float(low),
            })
    rows.sort(key=lambda r: r["date"])
    return rows


def build_regime_periods(grid_rows: list[dict], compass_rows: list[dict]) -> list[dict]:
    """Direct port of backtest_engine.build_regime_periods, no pandas.
    Each grid/compass row means "on metrics_date the model changed TO
    quadrant X". Walk all change-event dates chronologically, carry the
    last-known value for each model, emit one period per interval."""
    today = datetime.now(timezone.utc).date().isoformat()

    grid_map = {r["metrics_date"]: r["quadrant"] for r in grid_rows}
    compass_map = {r["metrics_date"]: r["quadrant"] for r in compass_rows}

    all_dates = sorted(set(grid_map) | set(compass_map))
    if not all_dates:
        return []

    periods = []
    gq: Optional[int] = None
    cq: Optional[int] = None

    for i, date in enumerate(all_dates):
        if date in grid_map:
            gq = grid_map[date]
        if date in compass_map:
            cq = compass_map[date]
        if gq is None or cq is None:
            continue

        if i + 1 < len(all_dates):
            next_date = all_dates[i + 1]
        else:
            next_date = today

        # end = day before next_date (string date arithmetic via datetime)
        from datetime import date as _date, timedelta
        end_dt = _date.fromisoformat(next_date) - timedelta(days=1)
        end = end_dt.isoformat()
        if date <= end:
            periods.append({"start": date, "end": end, "grid_q": gq, "compass_q": cq})

    return periods


def get_occurrences(prices: list[dict], periods: list[dict], grid_q: int, compass_q: int) -> list[dict]:
    """Direct port of backtest_engine.get_occurrences, no pandas."""
    if not prices or not periods:
        return []

    matching = [p for p in periods if p["grid_q"] == grid_q and p["compass_q"] == compass_q]
    if not matching:
        return []

    results = []
    for period in matching:
        pp = [r for r in prices if period["start"] <= r["date"] <= period["end"]]
        if len(pp) < 1:
            continue

        entry_close = pp[0]["close"]
        if not entry_close:
            continue

        exit_close = pp[-1]["close"]
        max_high = max(r["high"] for r in pp)
        min_low = min(r["low"] for r in pp)

        start_d = pp[0]["date"]
        end_d = pp[-1]["date"]
        from datetime import date as _date
        duration_days = (_date.fromisoformat(end_d) - _date.fromisoformat(start_d)).days

        results.append({
            "start_date": start_d,
            "end_date": end_d,
            "duration_days": duration_days,
            "entry_close": round(entry_close, 4),
            "exit_close": round(exit_close, 4),
            "high_pct": round((max_high / entry_close - 1.0) * 100.0, 2),
            "low_pct": round((min_low / entry_close - 1.0) * 100.0, 2),
            "return_pct": round((exit_close / entry_close - 1.0) * 100.0, 2),
        })

    return results


def compute_stats(occurrences: list[dict]) -> Optional[dict]:
    """Direct port of backtest_engine.compute_stats, no pandas."""
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


def _chunk_key(chunk_index: int) -> str:
    return f"{PREFIX}occurrences_chunk_{chunk_index}.json"


def _s3_get_json(key: str) -> Optional[dict]:
    try:
        obj = _s3.get_object(Bucket=BUCKET, Key=key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return None
        raise
    return json.loads(obj["Body"].read().decode("utf-8"))


def _s3_put_json(key: str, payload: dict) -> None:
    _s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=json.dumps(payload, allow_nan=False).encode("utf-8"),
        ContentType="application/json",
    )


def _read_manifest() -> dict:
    """Read manifest.json, bootstrapping a fresh one (not written yet)
    if it doesn't exist. Bootstrapping assigns every BACKTEST_UNIVERSE
    ticker to a chunk up front so the mapping is stable from the first
    refresh call, even though no chunk has been populated yet."""
    manifest = _s3_get_json(MANIFEST_KEY)
    if manifest is not None:
        return manifest

    ticker_to_chunk = {t: chunk_for_ticker(t) for t in BACKTEST_UNIVERSE}
    return {
        "schema_version": SCHEMA_VERSION,
        "chunk_count": CHUNK_COUNT,
        "ticker_to_chunk": ticker_to_chunk,
        "last_refreshed_at": {},  # str(chunk_index) -> ISO timestamp
    }


def _write_manifest(manifest: dict) -> None:
    _s3_put_json(MANIFEST_KEY, manifest)


def _read_chunk(chunk_index: int) -> dict:
    chunk = _s3_get_json(_chunk_key(chunk_index))
    return chunk if chunk is not None else {"tickers": {}}


def _write_chunk(chunk_index: int, chunk: dict) -> None:
    _s3_put_json(_chunk_key(chunk_index), chunk)


def _refresh_tickers_into_chunk(
    tickers: list[str],
    chunk_index: int,
    periods: list[dict],
) -> tuple[list[str], list[dict]]:
    """Recompute the given tickers (all belonging to chunk_index) and
    merge them into that chunk's existing S3 object. Returns
    (refreshed, failed) for the caller's summary."""
    chunk = _read_chunk(chunk_index)
    ticker_data: dict = chunk["tickers"]

    refreshed: list[str] = []
    failed: list[dict] = []
    for sym in tickers:
        try:
            if sym not in TICKER_GROUP_MAP:
                raise ValueError(f"{sym} is not in BACKTEST_UNIVERSE")

            prices = _fetch_price_history(sym)
            if not prices:
                raise ValueError(f"no price data found for {sym}")

            combos: dict[str, list[dict]] = {}
            for gq in range(1, 5):
                for cq in range(1, 5):
                    occ = get_occurrences(prices, periods, gq, cq)
                    if occ:
                        combos[_combo_key(gq, cq)] = occ

            ticker_data[sym] = {
                "group": TICKER_GROUP_MAP[sym],
                "combos": combos,
            }
            refreshed.append(sym)
        except Exception as exc:
            _logger.error("[backtest_data] failed to refresh %s: %s", sym, exc)
            failed.append({"ticker": sym, "error": str(exc)})
            continue

    _write_chunk(chunk_index, {"tickers": ticker_data})
    return refreshed, failed


def refresh_chunk(chunk_index: int) -> dict:
    """Primary refresh path (cron-job.org): recompute every ticker
    assigned to this chunk by the manifest's hash sharding, write just
    this chunk's S3 object, and update only this chunk's manifest
    timestamp. Fast, bounded, independent of every other chunk."""
    manifest = _read_manifest()
    if chunk_index < 0 or chunk_index >= manifest["chunk_count"]:
        raise ValueError(f"chunk {chunk_index} out of range (chunk_count={manifest['chunk_count']})")

    # New tickers added to BACKTEST_UNIVERSE since the manifest was last
    # written won't be in ticker_to_chunk yet -- backfill any missing
    # assignments using the manifest's own chunk_count before selecting
    # this chunk's tickers, so nothing silently falls through the cracks.
    for t in BACKTEST_UNIVERSE:
        if t not in manifest["ticker_to_chunk"]:
            manifest["ticker_to_chunk"][t] = chunk_for_ticker(t, manifest["chunk_count"])

    target_tickers = [
        t for t, c in manifest["ticker_to_chunk"].items() if c == chunk_index
    ]

    grid_rows = _fetch_model_history("grid_US")
    compass_rows = _fetch_model_history("compass_US")
    periods = build_regime_periods(grid_rows, compass_rows)

    refreshed, failed = _refresh_tickers_into_chunk(target_tickers, chunk_index, periods)

    now_iso = datetime.now(timezone.utc).isoformat()
    manifest["last_refreshed_at"][str(chunk_index)] = now_iso
    manifest["schema_version"] = SCHEMA_VERSION
    _write_manifest(manifest)

    return {
        "schema_version": SCHEMA_VERSION,
        "chunk_index": chunk_index,
        "last_refreshed_at": now_iso,
        "tickers_refreshed": refreshed,
        "tickers_failed": failed,
        "tickers_in_chunk": len(target_tickers),
    }


def refresh_tickers(tickers: list[str]) -> dict:
    """Secondary, ad-hoc refresh path: an arbitrary subset of tickers
    (single-ticker rebuild, or any custom set), NOT necessarily all
    belonging to one chunk. Groups them by their assigned chunk, updates
    only the affected chunks + their manifest timestamps.

    Invalid tickers (not in BACKTEST_UNIVERSE) are rejected immediately
    and NEVER written into manifest.ticker_to_chunk -- otherwise a single
    bad ticker permanently pollutes the manifest, and every subsequent
    refresh_chunk() call for whatever chunk it hashed to would keep
    re-attempting (and re-failing on) it forever."""
    manifest = _read_manifest()

    valid_tickers: list[str] = []
    immediate_failures: list[dict] = []
    for t in tickers:
        if t not in TICKER_GROUP_MAP:
            immediate_failures.append({"ticker": t, "error": f"{t} is not in BACKTEST_UNIVERSE"})
            continue
        valid_tickers.append(t)
        if t not in manifest["ticker_to_chunk"]:
            manifest["ticker_to_chunk"][t] = chunk_for_ticker(t, manifest["chunk_count"])

    by_chunk: dict[int, list[str]] = {}
    for t in valid_tickers:
        by_chunk.setdefault(manifest["ticker_to_chunk"][t], []).append(t)

    grid_rows = _fetch_model_history("grid_US")
    compass_rows = _fetch_model_history("compass_US")
    periods = build_regime_periods(grid_rows, compass_rows)

    now_iso = datetime.now(timezone.utc).isoformat()
    all_refreshed: list[str] = []
    all_failed: list[dict] = list(immediate_failures)
    for chunk_index, chunk_tickers in by_chunk.items():
        refreshed, failed = _refresh_tickers_into_chunk(chunk_tickers, chunk_index, periods)
        all_refreshed.extend(refreshed)
        all_failed.extend(failed)
        manifest["last_refreshed_at"][str(chunk_index)] = now_iso

    manifest["schema_version"] = SCHEMA_VERSION
    _write_manifest(manifest)

    return {
        "schema_version": SCHEMA_VERSION,
        "last_refreshed_at": now_iso,
        "tickers_refreshed": all_refreshed,
        "tickers_failed": all_failed,
        "chunks_touched": sorted(by_chunk.keys()),
    }


def build_table_response(
    compass_q: int,
    grid_q: int,
    min_occ: int = 5,
    lookback: Optional[str] = None,
) -> dict:
    """Read the manifest once, then every chunk (a full-universe table
    query necessarily spans all tickers, hence all chunks), and return
    the aggregated per-ticker stats table for one (compass_q, grid_q)
    combo, sorted by Edge descending. lookback: None/"all" | "10y" |
    "5y" -- filters occurrences by start_date before aggregating, same
    semantics as the Streamlit tab. last_refreshed_at reported is the
    MINIMUM across chunks actually contributing rows -- an honest
    freshness signal when chunks refresh on staggered schedules."""
    manifest = _read_manifest()
    timestamps = manifest.get("last_refreshed_at", {})
    if not timestamps:
        return {
            "schema_version": manifest["schema_version"],
            "last_refreshed_at": None,
            "compass_q": compass_q,
            "grid_q": grid_q,
            "rows": [],
            "error": "no chunks refreshed yet",
        }

    cutoff = None
    if lookback in ("10y", "5y"):
        years = 10 if lookback == "10y" else 5
        today = datetime.now(timezone.utc).date()
        cutoff = today.replace(year=today.year - years).isoformat()

    combo_key = _combo_key(grid_q, compass_q)
    rows = []
    contributing_timestamps: list[str] = []

    for chunk_index in range(manifest["chunk_count"]):
        chunk_ts = timestamps.get(str(chunk_index))
        chunk = _read_chunk(chunk_index)
        for sym, entry in chunk["tickers"].items():
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
            if chunk_ts:
                contributing_timestamps.append(chunk_ts)

    rows.sort(key=lambda r: (r["edge"] is None, -(r["edge"] or 0)))

    return {
        "schema_version": manifest["schema_version"],
        "last_refreshed_at": min(contributing_timestamps) if contributing_timestamps else None,
        "compass_q": compass_q,
        "grid_q": grid_q,
        "min_occ": min_occ,
        "lookback": lookback or "all",
        "rows": rows,
    }


def build_occurrences_response(ticker: str, compass_q: int, grid_q: int) -> dict:
    """Read the manifest once to look up which single chunk holds
    `ticker`, then read only that chunk -- no need to touch every chunk
    like build_table_response does, since this is scoped to one ticker."""
    manifest = _read_manifest()
    chunk_index = manifest["ticker_to_chunk"].get(ticker)
    if chunk_index is None:
        chunk_index = chunk_for_ticker(ticker, manifest["chunk_count"])

    chunk_ts = manifest.get("last_refreshed_at", {}).get(str(chunk_index))
    combo_key = _combo_key(grid_q, compass_q)

    chunk = _read_chunk(chunk_index)
    entry = chunk["tickers"].get(ticker)
    occ = entry["combos"].get(combo_key, []) if entry else []

    return {
        "schema_version": manifest["schema_version"],
        "last_refreshed_at": chunk_ts,
        "ticker": ticker,
        "compass_q": compass_q,
        "grid_q": grid_q,
        "occurrences": occ,
    }
