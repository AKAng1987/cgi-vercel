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

import cache
import macro_data
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


# ── market-implied P(flip) per axis ──────────────────────────────────────────
# The historical rate is the print-confirmed prior. The market-implied read
# is the other half of the thesis; the gap between them is the signal. Only
# Liquidity has a direct market price of the exact event (fed funds futures,
# same FedWatch computation the MACRO tab caches). Credit and Inflation use
# the experimental Phase 2 classifier's daily P(axis up); Growth has no
# market read yet (GDPNow is shown as context, not as a probability).

def _market_liquidity(fomc_date: str, state: int) -> Optional[dict]:
    try:
        meetings = macro_data._filter_meetings_by_horizon(
            cache.get_or_fetch("fomc_meeting_calendar", macro_data._fetch_fomc_meeting_calendar)
        )
        probs = cache.get_or_fetch("fomc_probabilities", lambda: macro_data.build_fomc_probabilities(meetings))
    except Exception:  # noqa: BLE001 -- market read is additive; never break the page
        return None
    for p in probs.get("probabilities", []):
        if p.get("date") == fomc_date:
            # Liquidity up = easing trend. A hike flips it; a hold or cut keeps it.
            p_flip = p["p_hike"] if state == 1 else p["p_cut"]
            return {
                "p_flip": round(float(p_flip), 3),
                "source": "fed funds futures (FedWatch method)",
                "detail": f"{p.get('most_likely')} {round(float(p.get('prob_most_likely', 0)) * 100)}% · hike {round(p['p_hike']*100)} / hold {round(p['p_hold']*100)} / cut {round(p['p_cut']*100)}",
                "experimental": False,
            }
    return None


def _market_from_classifier(latest_daily: Optional[dict], axis: str, state: int) -> Optional[dict]:
    d = (latest_daily or {}).get("divergence") or {}
    a = (d.get("axes") or {}).get(axis)
    if not a or a.get("p_up") is None:
        return None
    p_up = float(a["p_up"])
    return {
        "p_flip": round(1.0 - p_up if state == 1 else p_up, 3),
        "source": f"experimental classifier ({d.get('model_version')}, as of {d.get('features_as_of')})",
        "detail": f"P(up)={p_up:.2f}",
        "experimental": True,
    }


def _market_from_drivers(drv: Optional[dict], axis: str) -> Optional[dict]:
    """Driver-conditioned flip rate from axis_drivers (see that module):
    mean of P(flip | current tercile) across the axis's leading drivers.
    A table you can read, not a fitted model."""
    a = ((drv or {}).get("axes") or {}).get(axis)
    if not a or a["current"].get("conditioned_p_flip") is None:
        return None
    c = a["current"]
    top = [d for d in c["drivers"] if d.get("p_current") is not None]
    top.sort(key=lambda d: abs((d["p_current"] or 0) - (c["base_rate"] or 0)), reverse=True)
    lead = top[0] if top else None
    return {
        "p_flip": c["conditioned_p_flip"],
        "source": f"nowcast: flip rate conditioned on current driver terciles ({c['n_drivers_used']} drivers, {c['n_windows']} windows)",
        "detail": (f"{lead['name']} {lead['current_value']:+g} → {round(lead['p_current']*100)}% vs base {round(c['base_rate']*100)}%" if lead else f"base {round(c['base_rate']*100)}%"),
        "experimental": True,
    }


def _gdpnow_context() -> Optional[dict]:
    try:
        rows = cache.get_or_fetch("gdp_nowcast", macro_data.fetch_gdp_nowcast)
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    last = rows[-1]
    return {"gdpnow": last.get("gdpnow"), "as_of": last.get("date")}


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

    daily = signals_data.build_signals_response()["signals"]
    latest = daily[0] if daily else None
    try:
        import axis_drivers
        drivers = cache.get_or_fetch("axis_drivers", axis_drivers.compute_axis_drivers)
    except Exception:  # noqa: BLE001 -- additive; never break the page
        drivers = None

    # ── upcoming: one forecast per next release, history + market side by side
    upcoming = []
    for r in cal.next_releases(after=today):
        axis, model = r["axis"], r["model"]
        q = current[model]
        s = _axis_state(q, axis)
        p = rates[axis][s]["p_flip"]
        if axis == "liquidity":
            market = _market_liquidity(r["date"], s)
        else:
            market = _market_from_drivers(drivers, axis) or _market_from_classifier(latest, axis, s)
        gap = round(market["p_flip"] - p, 3) if market else None
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
            "market": market,
            "gap": gap,
            "context": _gdpnow_context() if axis == "growth" else None,
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

    # A release settles into model-history with a lag: the compass dates Fed
    # moves by DFEDTARU's *effective* date (the day after the decision) and
    # the models run at 00:25 UTC, so a flip can land 1-3 days after the
    # release. Match flips within SETTLE_DAYS of the release; until that
    # window closes with no flip, the event is pending, not a scored hold.
    SETTLE_DAYS = 3

    def flip_within(release_date: str, axis: str) -> Optional[dict]:
        d0 = dt.date.fromisoformat(release_date)
        for k in range(SETTLE_DAYS + 1):
            e = flips_by_date_axis.get(((d0 + dt.timedelta(days=k)).isoformat(), axis))
            if e:
                return e
        return None

    def stored_call(release_date: str, rtype: str) -> Optional[dict]:
        """Most recent daily row written BEFORE the release that pre-registered
        this exact release. Rows are latest-first in `daily`."""
        for s in daily:
            if s["signal_date"] > release_date:  # same-day 00:55 row is before the print
                continue
            for u in s.get("upcoming_releases") or []:
                if u.get("date") == release_date and u.get("type") == rtype:
                    return {"row_date": s["signal_date"], "written_at": s.get("upcoming_releases_written_at"),
                            "note": s.get("upcoming_releases_note"), **u}
            return None  # the nearest prior row didn't carry it -> not pre-registered
        return None

    # A release is scorable only from the day after: the model records the
    # transition at 00:25 UTC the next morning, so today's print is pending.
    yesterday = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()
    log = []
    pending: list[dict] = []
    for r in cal.releases_between(TRACK_START, yesterday):
        if r["date"] < TRACK_START:
            continue
        axis, model = r["axis"], r["model"]
        q0 = state_before(model, r["date"])
        if q0 is None:
            continue
        s0 = _axis_state(q0, axis)
        matched = flip_within(r["date"], axis)
        settle_by = (dt.date.fromisoformat(r["date"]) + dt.timedelta(days=SETTLE_DAYS)).isoformat()
        if matched is None and today <= settle_by:
            pending.append({"date": r["date"], "type": r["type"], "axis": axis, "model": model,
                            "quadrant_before": q0, "state_before": s0, "settle_by": settle_by})
            continue
        flipped = matched is not None
        y = 1 if flipped else 0
        stored = stored_call(r["date"], r["type"])
        if stored:
            p_hist = float(stored["history"]["p_flip"])
            p_mkt = float(stored["market"]["p_flip"]) if stored.get("market") else None
            mkt_src = stored["market"]["source"] if stored.get("market") else None
            registered = stored.get("written_at") or stored["row_date"]
        else:
            p_hist, p_mkt, mkt_src, registered = rates[axis][s0]["p_flip"], None, None, None
        log.append({
            "date": r["date"],
            "type": r["type"],
            "axis": axis,
            "model": model,
            "scheduled": True,
            "quadrant_before": q0,
            "state_before": s0,
            "p_flip": round(p_hist, 3),
            "p_market": round(p_mkt, 3) if p_mkt is not None else None,
            "market_source": mkt_src,
            "pre_registered_on": registered,  # null = history recomputed after the fact
            "pre_registration_note": stored.get("note") if stored else None,
            "flipped": flipped,
            "flip_recorded_on": matched["date"] if matched else None,
            "quadrant_after": _quadrant_with(q0, axis, 1 - s0) if flipped else q0,
            "brier": round((p_hist - y) ** 2, 4),
            "brier_market": round((p_mkt - y) ** 2, 4) if p_mkt is not None else None,
            "hit": (p_hist >= 0.5) == flipped,
            "hit_market": ((p_mkt >= 0.5) == flipped) if p_mkt is not None else None,
        })
    claimed = {(e["flip_recorded_on"], e["axis"]) for e in log if e.get("flip_recorded_on")}
    for e in events:
        if e["date"] >= TRACK_START and e["date"] <= yesterday and (e["date"], e["axis"]) not in claimed:
            log.append({
                "date": e["date"], "type": TYPE_OF_AXIS[e["axis"]], "axis": e["axis"], "model": e["model"],
                "scheduled": False, "quadrant_before": None, "state_before": e["from"],
                "p_flip": None, "p_market": None, "market_source": None, "pre_registered_on": None,
                "flipped": True, "quadrant_after": None, "brier": None, "brier_market": None,
                "hit": None, "hit_market": None,
            })
    log.sort(key=lambda x: x["date"], reverse=True)

    scored = [x for x in log if x["brier"] is not None]
    mkt_scored = [x for x in scored if x["brier_market"] is not None]
    summary = {
        "n_events": len(scored),
        "n_unscheduled": len(log) - len(scored),
        "n_pending": len(pending),
        "n_flips": sum(1 for x in scored if x["flipped"]),
        "n_pre_registered": sum(1 for x in scored if x["pre_registered_on"]),
        "brier": round(sum(x["brier"] for x in scored) / len(scored), 4) if scored else None,
        "hit_rate": round(sum(1 for x in scored if x["hit"]) / len(scored), 3) if scored else None,
        "n_market_scored": len(mkt_scored),
        "brier_market": round(sum(x["brier_market"] for x in mkt_scored) / len(mkt_scored), 4) if mkt_scored else None,
        "hit_rate_market": round(sum(1 for x in mkt_scored if x["hit_market"]) / len(mkt_scored), 3) if mkt_scored else None,
        "track_start": TRACK_START,
    }

    # ── daily audit collapsed into runs ─────────────────────────────────
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

    return {
        "as_of": today,
        "current": current,
        "upcoming": upcoming,
        "flip_rates": rates,
        "event_log": log,
        "pending": pending,
        "summary": summary,
        "runs": runs,
        "latest_daily": latest,
        "n_daily_rows": len(daily),
        "drivers": drivers,
    }
