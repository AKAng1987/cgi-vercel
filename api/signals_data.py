"""
TRACK RECORD tab data: the Markov signal log, read straight from
cmon-stage-backend-regime-signals.

One Scan per request. The table gets one row per day (Phase 1 writes it at
00:55 UTC; outcome-backfill and the Phase 2 divergence layer UpdateItem
onto the same row), so a full Scan is a few KB per year -- no cache
needed, and a cache would only add staleness to the one page whose whole
point is "this is exactly what was logged."

Nothing here computes a signal. Every field is lifted verbatim from what
the Lambdas wrote; the only derived numbers are the summary counts, and
those are documented inline because "hit rate" is easy to misread.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Optional

import boto3

REGION = "ap-southeast-1"
TABLE = "cmon-stage-backend-regime-signals"
AXES = ("compass", "grid")
HORIZONS = ("1w", "1m", "3m")

_logger = logging.getLogger("cgi_api.signals_data")
_ddb = boto3.client("dynamodb", region_name=REGION)


# ── DynamoDB unmarshal ───────────────────────────────────────────────────────

def _un(v: dict) -> Any:
    if "S" in v:
        return v["S"]
    if "N" in v:
        d = Decimal(v["N"])
        return int(d) if d == d.to_integral_value() else float(d)
    if "BOOL" in v:
        return v["BOOL"]
    if "NULL" in v:
        return None
    if "M" in v:
        return {k: _un(x) for k, x in v["M"].items()}
    if "L" in v:
        return [_un(x) for x in v["L"]]
    return None


def _scan_all() -> list[dict]:
    items: list[dict] = []
    kwargs: dict = {"TableName": TABLE}
    while True:
        page = _ddb.scan(**kwargs)
        items.extend({k: _un(v) for k, v in it.items()} for it in page["Items"])
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return items


# ── Row shaping ──────────────────────────────────────────────────────────────

def _axis_block(row: dict, axis: str) -> dict:
    top3 = (row.get("next_regime_top3") or {}).get(axis) or []
    return {
        "current": (row.get("regime_current_discrete") or {}).get(axis),
        "top1_next_probability": (row.get("top1_next_probability") or {}).get(axis),
        "transition_entropy": (row.get("transition_entropy") or {}).get(axis),
        "next_top3": [
            {"quadrant": t.get("quadrant"), "probability": t.get("probability")}
            for t in top3
        ],
    }


def _outcome_block(row: dict, horizon: str) -> Optional[dict]:
    o = row.get(f"outcome_{horizon}")
    if not o:
        return None
    signal_regime = row.get("regime_current_discrete") or {}
    actual = o.get("actual_regime") or {}
    hit = o.get("top3_hit") or {}
    return {
        "check_date": o.get("check_date"),
        "spx_return_pct": o.get("spx_return_pct"),
        "axes": {
            axis: {
                "actual": actual.get(axis),
                # "changed" is the honest companion to top3_hit: the top-3
                # list only holds *next* states, so a day where the regime
                # stayed put can never be a hit. Readers need both.
                "changed": (
                    actual.get(axis) is not None
                    and signal_regime.get(axis) is not None
                    and actual.get(axis) != signal_regime.get(axis)
                ),
                "top3_hit": hit.get(axis),
            }
            for axis in AXES
        },
    }


def _divergence_block(row: dict) -> Optional[dict]:
    d = row.get("experimental_divergence")
    if not d:
        return None
    axes = d.get("axes") or {}
    return {
        "model_version": d.get("model_version"),
        "features_as_of": d.get("features_as_of"),
        "axes": {
            k: {
                "p_up": v.get("p_up"),
                "discrete_up": v.get("discrete_up"),
                "discrete_quadrant": v.get("discrete_quadrant"),
                "divergence_score": v.get("divergence_score"),
                "direction": v.get("direction"),
            }
            for k, v in axes.items()
        },
    }


def _shape(row: dict) -> dict:
    return {
        "signal_date": row.get("signal_date"),
        "signal_id": row.get("signal_id"),
        "timestamp_utc": row.get("timestamp_utc"),
        "spx_close_at_signal": row.get("spx_close_at_signal"),
        "compass": _axis_block(row, "compass"),
        "grid": _axis_block(row, "grid"),
        "outcomes": {h: _outcome_block(row, h) for h in HORIZONS},
        "divergence": _divergence_block(row),
        # Phase 1.5 pre-registration (from 2026-09-16): stored verbatim.
        "upcoming_releases": row.get("upcoming_releases"),
    }


# ── Summary ──────────────────────────────────────────────────────────────────

def _summary(signals: list[dict]) -> dict:
    """Counts only. hit_rate is over days where the regime actually changed
    within the horizon -- see _outcome_block for why."""
    out: dict = {
        "n_signals": len(signals),
        "first_signal_date": signals[0]["signal_date"] if signals else None,
        "last_signal_date": signals[-1]["signal_date"] if signals else None,
        "n_with_divergence": sum(1 for s in signals if s["divergence"]),
        "horizons": {},
    }
    for h in HORIZONS:
        scored = [s for s in signals if s["outcomes"].get(h)]
        per_axis = {}
        for axis in AXES:
            changed = [s for s in scored if s["outcomes"][h]["axes"][axis]["changed"]]
            hits = [s for s in changed if s["outcomes"][h]["axes"][axis]["top3_hit"]]
            per_axis[axis] = {
                "n_scored": len(scored),
                "n_changed": len(changed),
                "n_top3_hit": len(hits),
                "hit_rate_on_changed": (len(hits) / len(changed)) if changed else None,
            }
        out["horizons"][h] = per_axis
    return out


# ── Public ───────────────────────────────────────────────────────────────────

def build_signals_response(limit: Optional[int] = None) -> dict:
    rows = _scan_all()
    # Latest-first for display; summary works on chronological order.
    rows.sort(key=lambda r: (r.get("signal_date") or "", r.get("timestamp_utc") or ""))
    signals = [_shape(r) for r in rows]
    summary = _summary(signals)
    signals.reverse()
    if limit:
        signals = signals[:limit]
    return {"summary": summary, "signals": signals}
