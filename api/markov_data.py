"""
Event-driven Markov layer (Phase 1.5).

The discrete regime only moves on data releases, and each release moves
exactly one axis (FOMC->liquidity, SLOOS->credit, CPI->inflation,
GDP->growth). So the forecast object is not "top-3 next quadrants"; it is,
for each upcoming release, P(that axis flips | its current state). The
track record scores one row per release as it lands.

Everything is estimated from model-history:
  flips(axis, from_state)     transitions attributed to that axis
  expected_releases(axis, s)  dwell_days_in_state / 365 * releases_per_year
  p_flip = flips / expected_releases   (clamped away from 0 and 1)

Attribution: compass has never double-flipped (0/54). Grid has 22
historical double-flip rows, all on GDP days -- the older model batched a
prior CPI move into the next GDP run. Each such row is split into two
axis events on the same date so neither axis loses its flip.

This module is read-only over DynamoDB and holds no state. The daily
Phase 1 row remains the pre-registered audit trail; this layer changes
what is *displayed and scored*, not what is written. Writing the event
forecast onto the daily row (true pre-registration of p_flip) is the v2
follow-up and needs a regime-signal-updater change.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Optional

import boto3

import release_calendar as cal
import signals_data

REGION = "ap-southeast-1"
MODEL_TABLE = "cmon-stage-backend-model-history"
TRACK_START = "2026-09-06"
P_MIN, P_MAX = 0.02, 0.98

_ddb = boto3.client("dynamodb", region_name=REGION)

AXES_OF_MODEL = {"compass": ("liquidity", "credit"), "grid": ("growth", "inflation")}
TYPE_OF_AXIS = {v: k for k, v in cal.AXIS_OF.items()}


# ── model-history ────────────────────────────────────────────────────────────

def _load_model(model_name: str) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    kwargs = dict(
        TableName=MODEL_TABLE,
        KeyConditionExpression="model_name = :m",
        ExpressionAttributeValues={":m": {"S": model_name}},
        ProjectionExpression="metrics_date, quadrant",
    )
    while True:
        page = _ddb.query(**kwargs)
        rows.extend((it["metrics_date"]["S"], int(it["quadrant"]["N"])) for it in page["Items"])
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return sorted(rows)


def _axis_state(q: int, axis: str) -> int:
    return cal.Q_TO_AXES[q][cal.SLOT_OF[axis]]


def _quadrant_with(q: int, axis: str, new_state: int) -> int:
    a = list(cal.Q_TO_AXES[q])
    a[cal.SLOT_OF[axis]] = new_state
    return cal.AXES_TO_Q[tuple(a)]


def _events_and_dwell(model: str, rows: list[tuple[str, int]], today: str) -> tuple[list[dict], dict]:
    """Per-axis flip events + dwell days per axis state, from event rows."""
    axes = AXES_OF_MODEL[model]
    events: list[dict] = []
    dwell = {a: {0: 0.0, 1: 0.0} for a in axes}
    for i, (d, q) in enumerate(rows):
        end = rows[i + 1][0] if i + 1 < len(rows) else today
        days = (dt.date.fromisoformat(end) - dt.date.fromisoformat(d)).days
        for a in axes:
            dwell[a][_axis_state(q, a)] += days
        if i > 0:
            pq = rows[i - 1][1]
            for a in axes:
                s0, s1 = _axis_state(pq, a), _axis_state(q, a)
                if s0 != s1:
                    events.append({"date": d, "model": model, "axis": a, "from": s0, "to": s1})
    return events, dwell


def _flip_rates(events: list[dict], dwell: dict) -> dict:
    """p_flip[axis][from_state]."""
    out: dict = {}
    for axis, states in dwell.items():
        out[axis] = {}
        per_year = cal.PER_YEAR[TYPE_OF_AXIS[axis]]
        for s in (0, 1):
            n_flips = sum(1 for e in events if e["axis"] == axis and e["from"] == s)
            expected = states[s] / 365.0 * per_year
            p = (n_flips / expected) if expected > 0 else 0.5
            out[axis][s] = {
                "p_flip": min(P_MAX, max(P_MIN, p)),
                "n_flips": n_flips,
                "expected_releases": round(expected, 1),
                "dwell_days": round(states[s], 1),
            }
    return out


# ── public ───────────────────────────────────────────────────────────────────

def build_markov_response() -> dict:
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    hist = {m: _load_model(f"{m}_US") for m in ("compass", "grid")}
    events, dwell, rates, current = [], {}, {}, {}
    for m, rows in hist.items():
        ev, dw = _events_and_dwell(m, rows, today)
        events.extend(ev)
        dwell.update(dw)
        rates.update(_flip_rates(ev, dw))
        current[m] = rows[-1][1] if rows else None
    events.sort(key=lambda e: e["date"])

    # ── upcoming: one forecast per next release ─────────────────────────
    upcoming = []
    for r in cal.next_releases(after=today):
        axis, model = r["axis"], r["model"]
        q = current[model]
        s = _axis_state(q, axis)
        p = rates[axis][s]["p_flip"]
        upcoming.append({
            "date": r["date"],
            "type": r["type"],
            "axis": axis,
            "model": model,
            "current_quadrant": q,
            "current_state": s,
            "p_flip": round(p, 3),
            "if_flip_quadrant": _quadrant_with(q, axis, 1 - s),
            "basis": rates[axis][s],
        })

    # ── event log since track-record start ──────────────────────────────
    # For each release on/after TRACK_START up to today: state before, the
    # p_flip we would have quoted, and what happened. Unscheduled transitions
    # (no calendar entry that day) are appended and labelled.
    def state_before(model: str, date: str) -> Optional[int]:
        q = None
        for d, qq in hist[model]:
            if d < date:
                q = qq
            else:
                break
        return q

    flips_by_date_axis = {(e["date"], e["axis"]): e for e in events}
    log = []
    for r in cal.releases_between(TRACK_START, today):
        if r["date"] < TRACK_START:
            continue
        axis, model = r["axis"], r["model"]
        q0 = state_before(model, r["date"])
        if q0 is None:
            continue
        s0 = _axis_state(q0, axis)
        p = rates[axis][s0]["p_flip"]
        flipped = (r["date"], axis) in flips_by_date_axis
        y = 1 if flipped else 0
        log.append({
            "date": r["date"],
            "type": r["type"],
            "axis": axis,
            "model": model,
            "scheduled": True,
            "quadrant_before": q0,
            "state_before": s0,
            "p_flip": round(p, 3),
            "flipped": flipped,
            "quadrant_after": _quadrant_with(q0, axis, 1 - s0) if flipped else q0,
            "brier": round((p - y) ** 2, 4),
            "hit": (p >= 0.5) == flipped,
        })
    scheduled_keys = {(e["date"], e["axis"]) for e in log}
    for e in events:
        if e["date"] >= TRACK_START and e["date"] <= today and (e["date"], e["axis"]) not in scheduled_keys:
            log.append({
                "date": e["date"], "type": TYPE_OF_AXIS[e["axis"]], "axis": e["axis"], "model": e["model"],
                "scheduled": False, "quadrant_before": None, "state_before": e["from"],
                "p_flip": None, "flipped": True, "quadrant_after": None, "brier": None, "hit": None,
            })
    log.sort(key=lambda x: x["date"], reverse=True)

    scored = [x for x in log if x["brier"] is not None]
    summary = {
        "n_events": len(scored),
        "n_unscheduled": len(log) - len(scored),
        "n_flips": sum(1 for x in scored if x["flipped"]),
        "brier": round(sum(x["brier"] for x in scored) / len(scored), 4) if scored else None,
        "hit_rate": round(sum(1 for x in scored if x["hit"]) / len(scored), 3) if scored else None,
        "track_start": TRACK_START,
    }

    # ── daily audit collapsed into runs ─────────────────────────────────
    daily = signals_data.build_signals_response()["signals"]
    daily_asc = list(reversed(daily))
    runs: list[dict] = []
    for s in daily_asc:
        key = (s["compass"]["current"], s["grid"]["current"])
        if runs and runs[-1]["key"] == key:
            runs[-1]["end"] = s["signal_date"]
            runs[-1]["days"] += 1
        else:
            runs.append({"key": key, "compass": key[0], "grid": key[1], "start": s["signal_date"], "end": s["signal_date"], "days": 1})
    for r in runs:
        del r["key"]
    runs.reverse()
    latest = daily[0] if daily else None

    return {
        "as_of": today,
        "current": current,
        "upcoming": upcoming,
        "flip_rates": rates,
        "event_log": log,
        "summary": summary,
        "runs": runs,
        "latest_daily": latest,
        "n_daily_rows": len(daily),
    }
