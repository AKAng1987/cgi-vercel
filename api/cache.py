"""
cache.py — S3-backed cache for Phase 2 MACRO endpoints (PHASE2_PLAN.md
Variant C). One object per cache key under Cache/macro/, storing the
finished computed response payload as JSON. Staleness is decided by
comparing the object's S3 LastModified against a per-key TTL.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import threading

import boto3
from botocore.exceptions import ClientError

import sanity_checks

REGION = "ap-southeast-1"
BUCKET = "cmon-stage-backend-369568916817-ap-southeast-1-reports"
PREFIX = "Cache/macro/"

_s3 = boto3.client("s3", region_name=REGION)
_logger = logging.getLogger("cgi_api.cache")

# Locked TTLs per PHASE2_PLAN.md's final table (2026-09-05/06 addenda,
# including the GDP/GDPNow split). This is the single source of truth
# for every cache key across all 3 /api/macro/* endpoints.
TTL_HOURS: dict[str, float] = {
    "fed_funds_range": 12.0,
    "fomc_probabilities": 6.0,
    "fomc_meeting_calendar": 168.0,  # 7d
    "treasury_curve": 6.0,
    "spreads": 12.0,
    "lending_standards": 48.0,
    "challenger": 24.0,  # macro: Challenger job cuts from price-history (manual monthly load)
    "gdp": 48.0,
    "gdp_nowcast": 24.0,
    "inflation": 24.0,
    "pce": 24.0,
    "dot_plot": 168.0,  # 7d
    "axis_drivers": 24.0,  # markov: what-moves-each-axis event study (~14 DDB pulls)
    "hud_extra": 6.0,  # HUD rows computed from price-history for tickers the workbook lacks
    "policy_watch": 6.0,  # central bank feeds; 6h so an announcement lands same-day
    "cot": 12.0,  # COT publishes Friday 15:30 ET; 12h keeps it fresh without hammering CFTC
    "technicals": 12.0,  # LIVE: breadth glance (net new highs + participation gauges)
    "themes": 24.0,  # LIVE brief: theme onset/age from RS persistence
    "watchlists": 24.0,  # TradingView list contents for the cloud routine
    "fundamentals": 24.0,  # quarterly data; 24h is ample and halves the SEC load
    "etf_constituents": 168.0,  # ETF books move slowly; 7d, and the pull is ~90s
    "brief_daily": 6.0,
    "brief_weekly": 24.0,
}

# Bump a key's entry whenever the fetch/compute logic feeding that
# cache key changes shape or fixes a correctness bug -- forces an
# immediate refetch on next read regardless of remaining TTL, so a
# deployed fix isn't masked by an already-cached bad value for up to
# TTL_HOURS[key] more hours. Added 2026-09-11 after a bug class (Core
# PCE, then fetch_spreads) where a code fix alone didn't change what
# was being served until the stale cache object happened to expire.
CACHE_SCHEMA_VERSIONS: dict[str, int] = {
    "fed_funds_range": 1,
    "fomc_probabilities": 1,
    "fomc_meeting_calendar": 2,  # 2026-09-12: now caches unfiltered dates; filtering moved to read-time
    "treasury_curve": 1,
    "spreads": 2,  # 2026-09-11: fetch_spreads bp/percent fix (see macro_data.py)
    "lending_standards": 1,
    "challenger": 1,
    "gdp": 1,
    "gdp_nowcast": 1,
    "inflation": 1,
    "pce": 1,
    "dot_plot": 1,
    "hud_extra": 1,
    "policy_watch": 1,
    "cot": 1,
    "technicals": 2,  # 2026-09-24: Nasdaq universe, 3-day rule, per-day bands
    "themes": 5,  # 2026-09-25: MOO added to agriculture.  # 2026-09-25: megatrend by >365d rule, dollar standing theme, AI capex rename  # 2026-09-24: standing themes, DXJ-led Japan, Korea/DRAM, megatrend class  # 2026-09-24: empirical stages + survival replace invented age cut-offs
    "watchlists": 1,
    "etf_constituents": 2,  # 2026-09-25: MOO for agriculture + unreachable fall-through
    "brief_daily": 1,
    "brief_weekly": 1,
    "fundamentals": 5,  # 2026-09-26: seasonal QoQ + SPCX.  # 2026-09-25: bank concept, IFRS, annual mode, PLTR in models.  # 2026-09-25: constituents derived from real ETF holdings.  # 2026-09-25: merge XBRL concept chains + STALE_DAYS guard --
                        # v1 read dead concepts for 48 of 65 names (NVDA reported FY2020)
    "axis_drivers": 10,  # 2026-09-23: Empire prices paid, Philly future activity (free FRED; ISM frozen by TradingView MCP bug), ISM svc activity back as inverted context. v9 2026-09-19: inflation + growth lists from user framework + sweep. v8 2026-09-18: back to DFEDTARU (v7 tried DFF, user rejected). v6 2026-09-17: calendar-aware yoy (CPI 3.33 not 3.73); credit: 10-2 back, 10-5, HYG/LQD, curve regime categorical; SPY out; Challenger m/m out
}


def _key(cache_key: str) -> str:
    return f"{PREFIX}{cache_key}.json"


def get(cache_key: str) -> Optional[dict]:
    """Return the cached payload if it exists, is within its TTL, AND
    matches CACHE_SCHEMA_VERSIONS[cache_key] -- else None (caller
    should fetch fresh and call set()).

    cache_version travels as S3 object metadata, not inside the JSON
    body -- a version check piggybacks on the existing head_object()
    staleness check at no extra GetObject cost, and the cached
    payload's own shape stays exactly what callers already expect (no
    envelope wrapping). An object written before this field existed,
    or under a since-bumped version, has no matching metadata and is
    correctly treated as a miss."""
    ttl_hours = TTL_HOURS[cache_key]
    s3_key = _key(cache_key)

    try:
        head = _s3.head_object(Bucket=BUCKET, Key=s3_key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return None
        raise

    last_modified: datetime = head["LastModified"]
    age_hours = (datetime.now(timezone.utc) - last_modified).total_seconds() / 3600.0
    if age_hours > ttl_hours:
        return None

    cached_version = head.get("Metadata", {}).get("cache_version")
    expected_version = str(CACHE_SCHEMA_VERSIONS[cache_key])
    if cached_version != expected_version:
        _logger.info(
            "[cache] version mismatch for %r (cached=%r, expected=%r) -- "
            "treating as a miss, forcing a fresh fetch",
            cache_key, cached_version, expected_version,
        )
        return None

    obj = _s3.get_object(Bucket=BUCKET, Key=s3_key)
    body = obj["Body"].read().decode("utf-8")
    return json.loads(body)


def set(cache_key: str, value: dict) -> None:
    """Write the finished response payload for cache_key to S3, tagged
    with its current CACHE_SCHEMA_VERSIONS entry.

    allow_nan=False deliberately: json.dumps defaults to allow_nan=True,
    which silently writes non-compliant NaN/Infinity tokens that round-trip
    back on the next cache read and then blow up FastAPI's own response
    serializer (Starlette's JSONResponse.render uses allow_nan=False) --
    caught exactly this happening during this canary's own testing (a
    stale S3 object from a pre-fix run kept serving bad floats well after
    the source bug was fixed). Fail fast here instead of persisting bad
    data silently.
    """
    s3_key = _key(cache_key)
    _s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=json.dumps(value, allow_nan=False).encode("utf-8"),
        ContentType="application/json",
        Metadata={"cache_version": str(CACHE_SCHEMA_VERSIONS[cache_key])},
    )


def _get_raw(cache_key: str) -> Optional[dict]:
    """Read whatever is in S3 for cache_key regardless of TTL -- used as
    the stale-but-known-good fallback when a fresh fetch fails its
    sanity check. Returns None if nothing has ever been cached.

    Deliberately bypasses the cache_version check in get(): this is a
    last-resort "serve anything rather than nothing" path, called only
    after a fresh fetch already failed its sanity check. Refusing a
    same-shape-but-lower-version object here would remove the one
    fallback this path exists to provide, for no benefit -- if the
    version bumped because the fetch logic changed, whatever's here
    was still produced by the last known-good run of some version."""
    s3_key = _key(cache_key)
    try:
        obj = _s3.get_object(Bucket=BUCKET, Key=s3_key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return None
        raise
    return json.loads(obj["Body"].read().decode("utf-8"))


# A dict, not a set: this module defines its own set() for cache writes, which
# shadows the builtin at module scope.
_refreshing: dict[str, bool] = {}
_refresh_lock = threading.Lock()


def get_or_fetch_bg(cache_key: str, fetch_fn) -> dict:
    """Like get_or_fetch, but a STALE value is served immediately while the
    refresh runs in a background thread.

    Exists because the fundamentals universe grew from 65 hand-picked names to
    ~116 derived from real ETF holdings, and ~116 SEC fetches take ~30s. The
    page is rendered by a Vercel server component, whose function has a hard
    timeout well under that -- so a synchronous recompute would not merely be
    slow, it would fail the page outright. Serving the previous value and
    refreshing behind it keeps every request fast at the cost of the data
    being one cycle old, which for quarterly filings is immaterial.

    Only the FIRST ever call blocks, because nothing exists to serve yet.
    """
    fresh = get(cache_key)
    if fresh is not None:
        return fresh

    stale = _get_raw(cache_key)
    if stale is None:
        return get_or_fetch(cache_key, fetch_fn)   # nothing to serve; must block

    with _refresh_lock:
        if cache_key in _refreshing:
            return stale
        _refreshing[cache_key] = True

    def _work():
        try:
            get_or_fetch(cache_key, fetch_fn)
        except Exception:
            _logger.exception("[cache] background refresh failed for %r", cache_key)
        finally:
            with _refresh_lock:
                _refreshing.pop(cache_key, None)

    threading.Thread(target=_work, daemon=True).start()
    return stale


def get_or_fetch(cache_key: str, fetch_fn) -> dict:
    """Cache hit (fresh, within TTL) returns immediately. Cache miss/stale
    calls fetch_fn() (must return a JSON-serializable dict), runs it
    through sanity_checks.check() per PHASE2_PLAN.md's tiered spec
    (2026-09-06 addendum):

      - 12h/6h TTL keys: no check, fail-fast-on-JSON (allow_nan=False) is
        considered sufficient.
      - 24h+ TTL keys: sanity_checks.check() must pass before the fresh
        value is persisted.

    If the check FAILS: log an ERROR, do NOT overwrite the existing cache
    object, and return whatever is still in S3 even if it's past its
    nominal TTL (stale-but-known-good beats fresh-but-corrupt). If
    nothing has ever been cached for this key (first-ever fetch fails
    its own sanity check, no fallback exists), log a second, more severe
    error and return the fresh value anyway as a last resort -- there is
    nothing better to fall back to, and refusing to answer the request at
    all would be a worse failure mode than surfacing already-logged,
    flagged data once.
    """
    cached = get(cache_key)
    if cached is not None:
        return cached

    fresh = fetch_fn()

    if not sanity_checks.check(cache_key, fresh):
        _logger.error(
            "[cache] sanity check FAILED for %r -- not overwriting cache, "
            "falling back to stale-but-known-good if available",
            cache_key,
        )
        stale = _get_raw(cache_key)
        if stale is not None:
            return stale
        _logger.error(
            "[cache] sanity check FAILED for %r and NO prior cache exists "
            "to fall back to -- returning the failed-check value as a "
            "last resort, already flagged above",
            cache_key,
        )
        return fresh

    set(cache_key, fresh)
    return fresh
