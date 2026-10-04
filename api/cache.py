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
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    "gdp_nowcast_freshness": 6.0,
    "freshness": 1.0,
    "inflation": 24.0,
    "pce": 24.0,
    "dot_plot": 168.0,  # 7d
    "axis_drivers": 24.0,  # markov: what-moves-each-axis event study (~14 DDB pulls)
    "hud_extra": 6.0,  # HUD rows computed from price-history for tickers the workbook lacks
    "policy_watch": 6.0,  # central bank feeds; 6h so an announcement lands same-day
    "cot": 12.0,  # COT publishes Friday 15:30 ET; 12h keeps it fresh without hammering CFTC
    "technicals": 12.0,  # LIVE: breadth glance (net new highs + participation gauges)
    "themes": 24.0,  # LIVE brief: theme onset/age from RS persistence
    "sec_exchanges": 168.0,  # SEC ticker -> exchange, for TradingView symbols; listings change slowly
    "watchlists": 34.0,  # TradingView list contents for the cloud routine
    "mixture": 6.0,  # probability-weighted returns across now / if-next-flips; moves with p_flip
    "fundamentals": 24.0,  # quarterly data; 24h is ample and halves the SEC load
    "etf_constituents": 168.0,  # ETF books move slowly; 7d, and the pull is ~90s
    "brief_daily": 6.0,
    "liquidity": 12.0,  # weekly Fed data; 12h is ample
    "customer_links": 168.0,  # 10-Ks change once a year; each is 2-10MB
    "brief_weekly": 24.0,
    "countries": 6.0,        # FX and ETF legs move daily; macro prints monthly
    "context_tables": 24.0,  # decades of history; only the tail ever changes
}

# Bump a key's entry whenever the fetch/compute logic feeding that
# cache key changes shape or fixes a correctness bug -- forces an
# immediate refetch on next read regardless of remaining TTL, so a
# deployed fix isn't masked by an already-cached bad value for up to
# TTL_HOURS[key] more hours. Added 2026-09-11 after a bug class (Core
# PCE, then fetch_spreads) where a code fix alone didn't change what
# was being served until the stale cache object happened to expire.
# Modules whose cache version is taken from the MODULE ITSELF rather than from
# the table below. Map cache_key -> "module:CONSTANT".
#
# Why this exists: five separate times in this build a correct code change was
# deployed and then served stale, because the response shape changed here and
# the number in the table below did not. A note in BUILD.md did not fix it; the
# two things are in different files, and the one you edit is not the one you
# have to remember. Pointing the version at a constant that lives BESIDE the
# code being changed makes the bump land in the same edit as the change.
#
# The referenced module must define that integer constant, and its build
# function must be the thing whose shape is versioned.
SCHEMA_FROM_MODULE: dict[str, str] = {
    "countries": "country_data:SCHEMA_VERSION",
    "context_tables": "context_tables:SCHEMA_VERSION",
    # BOTH fomc keys point at the same constant. The scrape fix changed the
    # CALENDAR, and the probability method depends on how far that calendar
    # reaches -- bumping only fomc_probabilities left a 168h-TTL calendar
    # holding the old 7-date list, so the new method silently could not
    # engage and the page still showed the levered October contract.
    "fomc_probabilities": "macro_data:SCHEMA_VERSION",
    "fomc_meeting_calendar": "macro_data:SCHEMA_VERSION",
    "freshness": "freshness:SCHEMA_VERSION",
    "mixture": "mixture:SCHEMA_VERSION",
    "axis_drivers": "axis_drivers:SCHEMA_VERSION",
}


def _family(cache_key: str) -> str:
    """The registered key a variant belongs to.

    Some payloads are the same shape computed for different inputs -- the 16
    Compass x Grid cells of COUNTRIES, for instance. Writing those as
    "countries@3-3" lets each be cached separately while the TTL and the
    schema version stay registered once, against "countries". Without this
    every variant would need its own row in two tables, which is exactly the
    kind of bookkeeping that has gone stale here before.
    """
    return cache_key.split("@", 1)[0]


def _expected_version(cache_key: str) -> str:
    """The version a cached object must carry to be considered a hit."""
    cache_key = _family(cache_key)
    ref = SCHEMA_FROM_MODULE.get(cache_key)
    if ref:
        mod_name, const = ref.split(":")
        try:
            mod = __import__(mod_name)
            return str(getattr(mod, const))
        except Exception:  # noqa: BLE001 -- fall through to the table
            _logger.warning("[cache] could not read %s; using table version", ref)
    return str(CACHE_SCHEMA_VERSIONS[cache_key])


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
    "gdp_nowcast_freshness": 1,
    "freshness": 1,
    "inflation": 1,
    "pce": 1,
    "dot_plot": 1,
    "hud_extra": 1,
    "policy_watch": 1,
    "cot": 3,  # 2026-10-03: dead E-mini names fixed; 22 -> 39 contracts
    "technicals": 2,  # 2026-09-24: Nasdaq universe, 3-day rule, per-day bands
    "themes": 5,  # 2026-09-25: MOO added to agriculture.  # 2026-09-25: megatrend by >365d rule, dollar standing theme, AI capex rename  # 2026-09-24: standing themes, DXJ-led Japan, Korea/DRAM, megatrend class  # 2026-09-24: empirical stages + survival replace invented age cut-offs
    "sec_exchanges": 1,
    "watchlists": 7,  # URA retired (duplicate of URANIUM). v6: 2026-10-04: retired tickers (PBS JJC JJN PIN BJK VICE CNCR) out of the universe. v5: 2026-10-04: symbols from tv_symbols.json, never guessed; unplaceable names dropped before the cut. v4: earning-it stocks on their real exchange (were all AMEX:); 2026-10-03: worst 10 -> 20, and no overlap with best
    "etf_constituents": 2,  # 2026-09-25: MOO for agriculture + unreachable fall-through
    "brief_daily": 4,  # 2026-10-04: feed-integrity problems in the freshness section; 3: markov market lagged + relabelled
    "liquidity": 1,
    "customer_links": 1,
    "brief_weekly": 4,  # 2026-10-04: same
    "countries": 1,
    "context_tables": 4,  # 2026-09-26: NameError fix; v3 never actually served.  # 2026-09-26: Warsh added + chair carries a confirmation date.  # fed_episodes -> derived rate_cycles + balance_sheet
    "fundamentals": 10,  # 2026-09-26: traded data removed from the public response.  # 2026-09-26: proper median + n.  # 2026-09-26: traded universe unioned.  # 2026-09-26: cadence-aware reads.  # 2026-09-26: sector per company.  # 2026-09-26: seasonal QoQ + SPCX.  # 2026-09-25: bank concept, IFRS, annual mode, PLTR in models.  # 2026-09-25: constituents derived from real ETF holdings.  # 2026-09-25: merge XBRL concept chains + STALE_DAYS guard --
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
    body -- so the version check rides along with the object itself and
    the cached payload's shape stays exactly what callers already expect
    (no envelope wrapping). An object written before this field existed,
    or under a since-bumped version, has no matching metadata and is
    correctly treated as a miss.

    ONE round trip, not two. This used to head_object for the metadata and
    then get_object for the body. get_object already returns LastModified
    and Metadata alongside the body, so the head was pure latency -- and
    the API runs on Render's free tier in Oregon while this bucket is in
    ap-southeast-1, making every one of those a ~250ms cross-Pacific hop.
    /macro alone reads 13 keys, so the second trip was costing seconds per
    page for information the first trip already carried.

    The cost of merging them: on a stale or version-mismatched object we
    download a body we then discard. That is the rarer path by construction
    -- a hit is the common case, and a miss is about to spend far more than
    one download rebuilding the payload anyway."""
    ttl_hours = TTL_HOURS[_family(cache_key)]
    s3_key = _key(cache_key)

    try:
        obj = _s3.get_object(Bucket=BUCKET, Key=s3_key)
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return None
        raise

    last_modified: datetime = obj["LastModified"]
    age_hours = (datetime.now(timezone.utc) - last_modified).total_seconds() / 3600.0
    if age_hours > ttl_hours:
        return None

    cached_version = obj.get("Metadata", {}).get("cache_version")
    expected_version = _expected_version(cache_key)
    if cached_version != expected_version:
        _logger.info(
            "[cache] version mismatch for %r (cached=%r, expected=%r) -- "
            "treating as a miss, forcing a fresh fetch",
            cache_key, cached_version, expected_version,
        )
        return None

    return json.loads(obj["Body"].read().decode("utf-8"))


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
        Metadata={"cache_version": _expected_version(cache_key)},
    )


def _cached_version(cache_key: str) -> Optional[str]:
    """The cache_version metadata on whatever is stored, without fetching the
    body. None if nothing is stored."""
    try:
        head = _s3.head_object(Bucket=BUCKET, Key=_key(cache_key))
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "403"):
            return None
        raise
    return head.get("Metadata", {}).get("cache_version")


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


def get_many(jobs: dict) -> dict:
    """Resolve several cache keys CONCURRENTLY.

    {result_name: (cache_key, fetch_fn)} -> {result_name: payload}.

    Every cache read is a round trip to S3 in ap-southeast-1, and the API
    runs on Render's free tier in Oregon, so each one costs ~250ms of pure
    latency. Built as a dict literal, /api/macro/growth resolved its seven
    keys one after another -- nearly all of that endpoint's wall-clock time
    was spent waiting on a socket, serially, for payloads that have nothing
    to do with each other.

    Threads rather than asyncio because the work is boto3, which is
    blocking, and because get_or_fetch may fall through to a real rebuild
    that is also blocking. The GIL is not the constraint here; the Pacific
    is.

    A failure is re-raised rather than swallowed, so this changes the timing
    of these calls and nothing about their behaviour.
    """
    if not jobs:
        return {}
    out: dict = {}
    with ThreadPoolExecutor(max_workers=min(8, len(jobs))) as pool:
        futures = {pool.submit(get_or_fetch, key, fn): name
                   for name, (key, fn) in jobs.items()}
        for fut in as_completed(futures):
            out[futures[fut]] = fut.result()
    return out


def invalidate(cache_key: str) -> list[str]:
    """Delete a cached payload so the next request rebuilds it.

    Used after a WRITE to price-history: the bar is in DynamoDB but the
    payload that reads it is not, and until the TTL expires the dashboard
    shows the old number. From the outside that is indistinguishable from
    the write having failed.

    Deletes every VARIANT of a family too -- "countries" is stored as
    countries@3-3 and fifteen siblings, and invalidating only the bare key
    would leave the fifteen the page actually serves.

    Returns the keys removed. Safe to call for a key that was never
    written.
    """
    prefix = f"{PREFIX}{_family(cache_key)}"
    removed = []
    try:
        page = _s3.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
        for obj in page.get("Contents", []):
            k = obj["Key"]
            base = k[len(PREFIX):-len(".json")] if k.endswith(".json") else None
            # Only this family: "countries" and "countries@2-1", never
            # "context_tables" from a prefix collision.
            if base and (base == cache_key or base.startswith(cache_key + "@")):
                _s3.delete_object(Bucket=BUCKET, Key=k)
                removed.append(base)
    except ClientError:
        _logger.exception("[cache] invalidate failed for %r", cache_key)
        raise
    if removed:
        _logger.info("[cache] invalidated %s", ", ".join(removed))
    return removed


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

    # Serving stale is only safe when the stale thing is the SHAPE the caller
    # expects. _get_raw deliberately ignores cache_version, which is right for
    # its original purpose -- a last-resort fallback after a fresh fetch failed
    # its sanity check -- but wrong here, where this is the routine path. A
    # schema bump exists precisely to stop a payload of the old shape being
    # served, and without this check the background refresh would quietly
    # defeat it: /api/countries returned a version-9 payload, missing the
    # fields version 10 had just added, and looked simply not-deployed.
    if _cached_version(cache_key) != _expected_version(cache_key):
        return get_or_fetch(cache_key, fetch_fn)   # wrong shape; must block

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


# ── staleness, measured against a series' own cadence ───────────────────
#
# The obvious guard -- "blank any input older than N days" -- is wrong for
# anything that is not daily, and dangerously so. GDPNOW is QUARTERLY: FRED
# dates each observation to the quarter START, so 2026-07-01 is the label for
# Q3, and its value (5.0163) is revised continuously through the quarter. Its
# FRED last_updated is 2026-09-25. A flat 14-day rule would blank a perfectly
# live input for about 85% of every quarter, and the growth axis would quietly
# lose its nowcast.
#
# So staleness is judged against the EXPECTED cadence, with a grace margin for
# publication lag. The same reasoning as sec_xbrl.STALE_BY_CADENCE and
# country_data._bars_per_year, which derives cadence from observed spacing
# rather than trusting a declaration.
CADENCE_DAYS = {"daily": 1, "weekly": 7, "monthly": 31, "quarterly": 92, "annual": 366}
STALE_GRACE = 2.0   # a print may be this many cadences late before it is stale


def is_stale(as_of: str, cadence: str, today: Optional[str] = None) -> dict:
    """Whether an observation dated `as_of` is overdue for its cadence.

    Returns the verdict WITH its inputs, because a staleness call that cannot
    be checked is just another opinion.
    """
    from datetime import date
    t = date.fromisoformat(today) if today else date.today()
    age = (t - date.fromisoformat(as_of)).days
    period = CADENCE_DAYS.get(cadence)
    if period is None:
        return {"stale": False, "age_days": age, "cadence": cadence,
                "reason": "unknown cadence; not judging"}
    limit = period * (1 + STALE_GRACE)
    return {"stale": age > limit, "age_days": age, "cadence": cadence,
            "expected_every_days": period, "stale_after_days": round(limit),
            "reason": (f"{age}d old against a {cadence} cadence"
                       + (" -- overdue" if age > limit else " -- within tolerance"))}
