"""
sanity_checks.py — tiered validation for Phase 2 MACRO cache writes.

Per PHASE2_PLAN.md's 2026-09-06 addendum:
  - 12h TTL keys (fed_funds_range, treasury_curve, spreads): no check --
    fail-fast-on-invalid-JSON (cache.set()'s allow_nan=False) is
    considered sufficient at this TTL.
  - 6h TTL keys (fomc_probabilities): also no check, explicitly skipped.
  - 24h TTL keys (inflation, pce, gdp_nowcast): presence + type +
    non-empty-series check.
  - 48h TTL keys (gdp, lending_standards): 24h check PLUS value-range
    plausibility (GDP growth in [-15, 15], lending standards in
    [-100, 100]).
  - 7d TTL keys (dot_plot, fomc_meeting_calendar): the above PLUS a
    structural check (participant count / valid meeting dates).

check(cache_key, value) returns True if the value is OK to persist,
False if the caller (cache.get_or_fetch) should reject it and fall back
to whatever's already cached instead.
"""
from __future__ import annotations

import datetime
from typing import Any

# Keys where cache.set()'s allow_nan=False write-time check is already
# considered sufficient -- no additional sanity check.
_NO_CHECK_KEYS = frozenset({
    "fed_funds_range", "treasury_curve", "spreads",  # 12h
    "fomc_probabilities",  # 6h
})


def _is_nonempty_series(value: Any) -> bool:
    if isinstance(value, list):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    return value is not None


def _check_24h_generic(value: Any) -> bool:
    """Presence + type + non-empty-series -- the 24h tier's whole check."""
    return _is_nonempty_series(value)


def _check_gdp(value: Any) -> bool:
    """value is {"quarterly": [...], "vintages": [...]} -- fetch_gdp()'s
    shape, not a flat list.

    The [-15, 15] plausibility range applies ONLY to the most recent
    quarterly print, not the full historical series: fetch_gdp_quarterly()
    returns the complete BEA history back to ~1950, which legitimately
    contains real outliers outside [-15, 15] (the 2020 COVID crash:
    -28.0% in 2020Q2, +34.9% in 2020Q3; also 1950/1978 prints near 16.5%)
    -- these are correct, immutable historical data, not corruption.
    Checking the whole series against this range was this check's own
    bug, caught during Phase 2 growth-endpoint testing (2026-09-06) when
    it rejected real data on the very first live fetch. The actual intent
    is "is the newest print plausible," which only ever needs the latest
    row.
    """
    if not isinstance(value, dict):
        return False
    quarterly = value.get("quarterly")
    if not _is_nonempty_series(quarterly):
        return False
    latest = quarterly[-1]
    v = latest.get("gdp_pct")
    if v is not None and not (-15.0 <= v <= 15.0):
        return False
    # vintages is allowed to be empty (e.g. ALFRED lag), quarterly is the
    # required part of this key.
    return True


def _check_lending_standards(value: Any) -> bool:
    """Same latest-row-only reasoning as _check_gdp -- DRTSCILM's full
    15-year history could in principle contain a legitimate extreme
    quarter; only the newest print needs to look plausible."""
    if not _is_nonempty_series(value):
        return False
    latest = value[-1]
    v = latest.get("value")
    if v is not None and not (-100.0 <= v <= 100.0):
        return False
    return True


def _check_pce(value: Any) -> bool:
    """Added 2026-09-06 alongside the Core PCE unit-conversion bug fix
    (see macro_data.py's fetch_pce() docstring -- the old code stored a
    raw BEA index level as if it were already a rate, and compounded it,
    producing ~1.8 million instead of ~2-3% YoY). This check exists
    specifically to catch that class of error instantly if it recurs
    (e.g. a future BEA schema change reintroducing an index-vs-rate
    mismatch), rather than relying on generic presence/type checks that
    would have happily accepted the corrupt 1.8-million value. Range is
    deliberately wide -- real Core PCE YoY has stayed roughly 0-11% since
    1960 -- this guards against gross unit errors, not tight plausibility.
    Same latest-row-only reasoning as _check_gdp/_check_lending_standards."""
    if not _is_nonempty_series(value):
        return False
    latest = value[-1]
    v = latest.get("pce_core_yoy")
    if v is not None and not (-5.0 <= v <= 20.0):
        return False
    return True


def _check_fomc_meeting_calendar(value: Any) -> bool:
    if not _is_nonempty_series(value):
        return False
    for row in value:
        try:
            datetime.date.fromisoformat(row["date"])
        except (KeyError, ValueError, TypeError):
            return False
    # A real FOMC calendar always has at least one upcoming meeting within
    # the 12-month horizon get_upcoming_meetings() queries -- near
    # year-end with the hardcoded FOMC_2026 list this can legitimately be
    # as low as 1-2 (see overnight-report-20260906.md), so this only
    # guards against a total-failure empty result, not a strict minimum.
    return len(value) >= 1


def _check_dot_plot(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    participant_ids = {row.get("participant_id") for row in value}
    horizons = {row.get("year") for row in value}
    # Real SEP dot plot has ~19 participants (verified against the live
    # data_manual/dot_plot.csv, 2026-09-06) -- guard against a badly
    # truncated/corrupted file without hardcoding an exact count that
    # would break the next time a participant leaves/joins the FOMC.
    if len(participant_ids) < 10:
        return False
    # Always multiple horizons (current year, +1, +2, longer-run).
    if len(horizons) < 2:
        return False
    return True


_CHECKS = {
    "gdp": _check_gdp,
    "lending_standards": _check_lending_standards,
    "pce": _check_pce,
    "fomc_meeting_calendar": _check_fomc_meeting_calendar,
    "dot_plot": _check_dot_plot,
}

# 24h-tier keys that only need the generic presence/type/non-empty check.
# "pce" moved out of this set 2026-09-06 -- it now has its own range check
# (_check_pce) on top of the generic one, since presence/type/non-empty
# alone would have happily accepted the ~1.8-million corrupt value.
_GENERIC_24H_KEYS = frozenset({"inflation", "gdp_nowcast"})


def check(cache_key: str, value: Any) -> bool:
    if cache_key in _NO_CHECK_KEYS:
        return True
    if cache_key in _GENERIC_24H_KEYS:
        return _check_24h_generic(value)
    specific = _CHECKS.get(cache_key)
    if specific is not None:
        return specific(value)
    # Unknown key -- shouldn't happen given cache.TTL_HOURS is the single
    # source of truth for valid keys, but default permissive rather than
    # silently blocking an endpoint that hasn't been wired up here yet.
    return True
