"""
Historical context tables for the CGI tab.

These lived in a planning spreadsheet, where they were typed once and then
went stale. Everything here that CAN be computed from held history IS
computed, so the tables stay current without anyone maintaining them:

  * S&P drawdown base rates        -- fully derived from SPX back to 1927
  * Yield-curve inversion cycles   -- fully derived from T10Y3M / T10Y2Y
  * Fed easing/tightening episodes -- boundaries curated, every market
                                      column derived

The point of the drawdown table is stated plainly by the user: to see the
base rates often enough "to make the feelings even keel". So it leads with
where we are NOW against the distribution, not with the distribution alone.

METHOD NOTE, because it decides the numbers
-------------------------------------------
A decline is measured with a zigzag whose reversal threshold EQUALS the depth
being counted: declines of "at least 10%" are found with a 10% threshold, "at
least 35%" with a 35% threshold. This matters more than it sounds.

  * Requiring recovery to the prior ALL-TIME high before a new episode can
    start collapses 2000-2013 into one episode and reports 0.48 pullbacks a
    year against the conventional 3-4.
  * Using one small threshold for every depth does the opposite at the deep
    end: a 5% reversal chops 2007-09's -56.8% into several -20% pieces and
    finds only one >=35% decline since 1937.

Per-depth thresholds avoid both. Validated against the user's own sheet on the
post-war window: >=35% 4 vs their 4, 20-34.9% 11 vs 12, 10-14.9% 30 vs 29,
15-19.9% 10 vs 13. The 5-9.9% bucket is 152 vs their 84 -- at that depth the
count is very sensitive to the reversal rule, so it is a definition difference,
not a data disagreement, and both windows are returned so it can be seen.
"""

from __future__ import annotations

import datetime as dt
import math
import statistics as st
from typing import Optional

import axis_drivers

# See cache.py SCHEMA_FROM_MODULE: bumping this invalidates the cached payload,
# so a shape change and its version bump are the same edit.
SCHEMA_VERSION = 1

# How far either side of an inversion to look for the market top it belongs to.
# Module-level because joins() needs them too -- they previously lived inside
# inversions() as locals, and joins() raised NameError, which build_context()
# propagated and the page's .catch(() => null) then swallowed whole.
LOOKBACK_M, LOOKAHEAD_M = 12, 36

# Depth levels, in percent. Each is counted with its own reversal threshold.
LEVELS = (5, 10, 15, 20, 35)
BUCKETS = (
    ("5-9.9%", 5, 10, "pullback"),
    ("10-14.9%", 10, 15, "technical correction"),
    ("15-19.9%", 15, 20, "deep correction"),
    ("20-34.9%", 20, 35, "bear market"),
    (">=35%", 35, None, "major crash / dislocation"),
)
POSTWAR_START = "1946-01-01"

# Fed policy history is DERIVED, not curated.
#
# The first version of this table hardcoded episode boundaries, and it went
# stale immediately: it still described an ongoing cutting cycle that had in
# fact ended and reversed, and it named a chair who had left. That is exactly
# the spreadsheet problem this module exists to escape -- a table that has to
# be maintained by hand will be wrong by the time anyone looks at it.
#
# So the cycles come from the rate series itself. A hike on 2026-09-17 ends the
# easing cycle the moment it prints, with nobody editing anything.
#
# What genuinely CANNOT be derived is kept small and clearly separate:
#   * QE programme NAMES ("QE2", "Operation Twist") are labels, not data.
#     The balance-sheet EXPANSION they refer to is derived from WALCL below,
#     so the annotation only supplies the name.
#   * The Fed CHAIR is a fact about people, not a series. Where the date is
#     past the last recorded chair, the table says so rather than carrying the
#     previous name forward -- the failure that produced this rewrite.

# Effective-average vs target-upper-bound differ by a few basis points, so the
# join between them is a change of SOURCE and must not read as a policy move.
FEDFUNDS_SPLICE_SYMBOL = "DFEDTARU"
MIN_MOVE_PP = 0.05     # FEDFUNDS is an effective average and drifts a bp or two
CYCLE_GAP_MONTHS = 18  # a hold this long ends a cycle even without a reversal

# Curated, and the ONLY curated policy facts left. `until` is exclusive.
CHAIRS = [
    {"name": "Volcker", "from": "1979-08-06"},
    {"name": "Greenspan", "from": "1987-08-11"},
    {"name": "Bernanke", "from": "2006-02-01"},
    {"name": "Yellen", "from": "2014-02-03"},
    {"name": "Powell", "from": "2018-02-05"},
    {"name": "Warsh", "from": "2026-05-22"},
]

# The date this list was last CONFIRMED against reality. Past it the current
# chair is still reported -- a chair serves for years and blanking the name
# every day would be its own kind of wrong -- but it is reported WITH this date
# attached, so a stale entry is visible rather than silent.
#
# The failure being guarded against: the first version of this table carried
# the last known name forward with nothing attached, and so went on naming
# Powell months after Warsh had taken over. The fix is not silence, it is
# provenance.
CHAIRS_CONFIRMED_ON = "2026-09-26"

# How long a confirmation is trusted before the page calls it stale.
CHAIR_STALE_DAYS = 365

# Balance-sheet programme names, joined to derived WALCL expansions by date.
QE_LABELS = [
    {"from": "2008-11-25", "to": "2010-03-31", "label": "QE1"},
    {"from": "2010-11-03", "to": "2011-06-30", "label": "QE2"},
    {"from": "2012-09-13", "to": "2014-10-31", "label": "QE3"},
    {"from": "2020-03-23", "to": "2022-03-09", "label": "Unlimited QE / pandemic"},
]

# Columns computed at each episode's start. A series that does not reach back
# that far returns None and renders "unavailable" -- never blank, never carried
# forward from a later date.
AT_START = [("dxy", "DXY"), ("us10y", "US10Y"), ("fed_balance_sheet", "WALCL"), ("unemployment", "UNRATE")]


# SPX alone is ~24,800 rows and is read by drawdowns(), inversions() AND
# fed_episodes(). Each _load_close is a full paginated DynamoDB scan of that
# symbol, so without this the endpoint pays for it three times over.
_series_cache: dict[str, tuple[list[str], list[float]]] = {}


def _series(sym: str) -> tuple[list[str], list[float]]:
    if sym not in _series_cache:
        _series_cache[sym] = axis_drivers._load_close(sym)
    return _series_cache[sym]


def _at(dates: list[str], vals: list[float], on: str) -> Optional[float]:
    """Last value on or before `on`; None if the series starts after it."""
    import bisect
    i = bisect.bisect_right(dates, on) - 1
    return vals[i] if i >= 0 else None


def _years(a: str, b: str) -> float:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days / 365.25


def declines(dates: list[str], vals: list[float], thresh: float) -> list[dict]:
    """Every decline of at least `thresh`% from a local peak. The episode closes
    once price has rallied `thresh`% off the trough -- NOT when it regains the
    prior high, which is what lets a decade below an old peak still contain
    countable pullbacks. See the module docstring for why the threshold tracks
    the depth."""
    out: list[dict] = []
    peak, peak_d = vals[0], dates[0]
    trough = trough_d = None
    falling = False
    for d, v in zip(dates, vals):
        if not falling:
            if v >= peak:
                peak, peak_d = v, d
            elif (v / peak - 1) * 100 <= -thresh:
                falling, trough, trough_d = True, v, d
        else:
            if v < trough:
                trough, trough_d = v, d
            if (v / trough - 1) * 100 >= thresh:
                out.append({
                    "peak_date": peak_d, "trough_date": trough_d,
                    "depth_pct": round((trough / peak - 1) * 100, 1),
                    "days_to_trough": (dt.date.fromisoformat(trough_d) - dt.date.fromisoformat(peak_d)).days,
                    "recovered": True,
                })
                falling, peak, peak_d = False, v, d
    if falling:
        out.append({
            "peak_date": peak_d, "trough_date": trough_d,
            "depth_pct": round((trough / peak - 1) * 100, 1),
            "days_to_trough": (dt.date.fromisoformat(trough_d) - dt.date.fromisoformat(peak_d)).days,
            "recovered": False,
        })
    return out


def _rate_block(eps: list[dict], years: float) -> dict:
    n = len(eps)
    per_year = n / years if years else 0.0
    return {
        "n": n,
        "per_year": round(per_year, 2),
        # Poisson: chance of at least one in a year, given the measured rate.
        # Stated as "at least one", because that is the question being asked.
        "prob_1plus_per_year": round((1 - math.exp(-per_year)) * 100),
        "median_days_to_trough": st.median([e["days_to_trough"] for e in eps]) if eps else None,
        "median_depth_pct": round(st.median([e["depth_pct"] for e in eps]), 1) if eps else None,
    }


def _drawdown_window(dates, vals, label: str) -> dict:
    years = _years(dates[0], dates[-1])
    at_level = {t: [e for e in declines(dates, vals, t) if abs(e["depth_pct"]) >= t] for t in LEVELS}
    at_least = [{"level_pct": t, **_rate_block(at_level[t], years)} for t in LEVELS]
    buckets = []
    for name, lo, hi, desc in BUCKETS:
        sel = [e for e in at_level[lo] if hi is None or abs(e["depth_pct"]) < hi]
        recent = sorted(sel, key=lambda e: e["trough_date"])[-3:]
        buckets.append({
            "bucket": name, "definition": desc, **_rate_block(sel, years),
            "recent": [{"trough": e["trough_date"], "depth_pct": e["depth_pct"]} for e in reversed(recent)],
        })
    return {
        "label": label,
        "start": dates[0], "end": dates[-1], "years": round(years, 1),
        "at_least": at_least,
        "buckets": buckets,
        "deepest": sorted(at_level[35], key=lambda e: e["depth_pct"])[:6],
    }


def drawdowns() -> dict:
    dates, vals = _series("SPX")
    full = _drawdown_window(dates, vals, "full history")
    i0 = next((i for i, d in enumerate(dates) if d >= POSTWAR_START), 0)
    post = _drawdown_window(dates[i0:], vals[i0:], "post-war")

    # Where we are now, so the base rate is anchored to today rather than
    # floating free. Running high, not all-time high, is the honest reference
    # for "how far have we fallen".
    peak, peak_d = vals[0], dates[0]
    for d, v in zip(dates, vals):
        if v >= peak:
            peak, peak_d = v, d
    now_dd = (vals[-1] / peak - 1) * 100
    band = next((b for b, lo, hi, _ in BUCKETS if lo <= abs(now_dd) < (hi or 1e9)), None)

    return {
        "windows": [full, post],
        "now": {
            "as_of": dates[-1], "spx": round(vals[-1], 2),
            "running_high": round(peak, 2), "running_high_date": peak_d,
            "drawdown_pct": round(now_dd, 2),
            "band": band or "at or near the high",
        },
        "method": ("Each depth is counted with its own reversal threshold; an episode "
                   "closes when price rallies that same percentage off the trough. "
                   "The 5-9.9% count is sensitive to that rule -- both windows are "
                   "shown so the difference is visible."),
    }


def _crossings(sym: str) -> list[dict]:
    """Zero crossings of a spread: when it inverts and when it de-inverts."""
    dates, vals = _series(sym)
    out = []
    inv_date = None
    for d, v in zip(dates, vals):
        if v < 0 and inv_date is None:
            inv_date = d
        elif v >= 0 and inv_date is not None:
            out.append({"inverts": inv_date, "deinverts": d,
                        "days_inverted": (dt.date.fromisoformat(d) - dt.date.fromisoformat(inv_date)).days})
            inv_date = None
    if inv_date is not None:
        out.append({"inverts": inv_date, "deinverts": None, "days_inverted": None})
    # Brief dips through zero are noise, not a cycle.
    out = [c for c in out if c["days_inverted"] is None or c["days_inverted"] >= 30]

    # Merge inversions separated by a short pop back above zero: 1989-05 and
    # 1989-07, and 2019-05 and 2019-07, are each ONE cycle that un-inverted for
    # a few weeks, and counting them twice would double-count the sample that
    # every statistic below is divided by.
    merged: list[dict] = []
    for c in out:
        if merged and merged[-1]["deinverts"] and (
            dt.date.fromisoformat(c["inverts"]) - dt.date.fromisoformat(merged[-1]["deinverts"])
        ).days <= 180:
            prev = merged[-1]
            prev["deinverts"] = c["deinverts"]
            prev["days_inverted"] = (
                (dt.date.fromisoformat(c["deinverts"]) - dt.date.fromisoformat(prev["inverts"])).days
                if c["deinverts"] else None
            )
            prev["re_inverted"] = True
        else:
            merged.append(dict(c))
    return merged


def _months(a: str, b: str) -> Optional[float]:
    if not a or not b:
        return None
    return round((dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days / 30.44, 1)


def inversions() -> dict:
    """Curve inversion cycles, with the SPX peak that followed and how long it
    took -- the "how many months before the peak" column, derived rather than
    typed."""
    spx_d, spx_v = _series("SPX")
    # A CYCLICAL peak means the start of a real bear, so >=20%. At 15% the
    # 2000 cycle picked up a secondary high in 2001-05 and reported a tidy
    # 10-month lead, hiding the fact that the market had already topped in
    # March 2000 -- BEFORE that curve inverted. An indicator that looks
    # predictive only because the search started after the event is worse
    # than no indicator.
    # >=10%, not >=20%: a hard 20% cut made the 1989 inversion skip the 1990
    # bear (-19.9%, a tenth of a point short) and match the 2000 top instead,
    # reporting a 130-month "lead". Threshold cliffs manufacture nonsense, so
    # take the DEEPEST decline in the window whatever its size and report that
    # size alongside.
    # The UNION across thresholds, deduped by peak date. One threshold cannot
    # serve both ends: at 10% the 2000-2002 bear fragments into several legs so
    # its real -49% top (2000-03-24) never exists to be matched, and the cycle
    # gets attributed to a 2002 bear-market-rally high instead; at 20% the 1990
    # bear (-19.9%) vanishes entirely. Taking every episode found at any
    # threshold and picking the deepest in the window avoids both.
    seen: dict[str, dict] = {}
    for t in (10, 15, 20, 35):
        for e in declines(spx_d, spx_v, t):
            if abs(e["depth_pct"]) < t:
                continue
            prev = seen.get(e["peak_date"])
            if prev is None or e["depth_pct"] < prev["depth_pct"]:
                seen[e["peak_date"]] = e
    bears = sorted(seen.values(), key=lambda e: e["peak_date"])

    def nearest_peak(inv: str) -> Optional[dict]:
        """The market top belonging to this inversion: the deepest decline whose
        peak falls within 12 months BEFORE and 36 months AFTER the inversion.

        Bounded on BOTH sides deliberately. Searching only forward, unbounded,
        lets an inversion claim credit for a bear a decade later; allowing the
        peak to precede is what exposes a curve that inverted only after the
        market had already topped, which is what 2000 and 2022 both did."""
        d0 = dt.date.fromisoformat(inv)
        lo = (d0 - dt.timedelta(days=int(LOOKBACK_M * 30.44))).isoformat()
        hi = (d0 + dt.timedelta(days=int(LOOKAHEAD_M * 30.44))).isoformat()
        cand = [e for e in bears if lo <= e["peak_date"] <= hi]
        return min(cand, key=lambda e: e["depth_pct"]) if cand else None

    out = {}
    for label, sym in (("10y-3m", "T10Y3M"), ("10y-2y", "T10Y2Y")):
        rows = []
        for c in _crossings(sym):
            nxt = nearest_peak(c["inverts"])
            lag = _months(c["inverts"], nxt["peak_date"]) if nxt else None
            rows.append({
                **c,
                "spx_peak_date": nxt["peak_date"] if nxt else None,
                # Signed: positive = the curve inverted BEFORE the peak (a lead),
                # negative = it inverted after the market had already topped.
                "months_inversion_to_peak": lag,
                "led_the_peak": (lag is not None and lag > 0),
                "spx_trough_date": nxt["trough_date"] if nxt else None,
                "drawdown_pct": nxt["depth_pct"] if nxt else None,
                "no_match": nxt is None,
            })
        out[label] = rows
    return out


def _spliced_policy_rate() -> tuple[list[str], list[float], str]:
    """The policy rate back to 1954: FEDFUNDS (monthly effective) before
    DFEDTARU (daily target upper bound) begins, then DFEDTARU."""
    fd, fv = _series("FEDFUNDS")
    td, tv = _series(FEDFUNDS_SPLICE_SYMBOL)
    splice = td[0]
    dates = [d for d in fd if d < splice] + td
    vals = [v for d, v in zip(fd, fv) if d < splice] + tv
    return dates, vals, splice


def _policy_moves(dates, vals, splice) -> list[dict]:
    out = []
    for i in range(1, len(vals)):
        if dates[i] == splice:
            continue  # source change, not a policy move
        delta = vals[i] - vals[i - 1]
        if abs(delta) >= MIN_MOVE_PP:
            out.append({"date": dates[i], "from_rate": round(vals[i - 1], 2),
                        "to_rate": round(vals[i], 2), "delta_pp": round(delta, 2)})
    return out


def chair_on(date: str) -> Optional[str]:
    """Who chaired the Fed on `date`, or None before the first recorded chair."""
    name = None
    for c in CHAIRS:
        if date >= c["from"]:
            name = c["name"]
    return name


def chair_confidence(as_of: str) -> dict:
    """Whether the chair for `as_of` rests on a confirmation or on an
    assumption that nothing has changed since CHAIRS_CONFIRMED_ON."""
    stale_days = (dt.date.fromisoformat(as_of) - dt.date.fromisoformat(CHAIRS_CONFIRMED_ON)).days
    return {
        "name": chair_on(as_of),
        "confirmed_on": CHAIRS_CONFIRMED_ON,
        "assumed": stale_days > 0,
        "days_since_confirmed": max(stale_days, 0),
        "stale": stale_days > CHAIR_STALE_DAYS,
    }


def rate_cycles() -> dict:
    """Hiking and easing cycles, derived. A cycle ends on a reversal or after a
    hold of CYCLE_GAP_MONTHS -- without the hold rule, ZIRP's seven move-less
    years merged the 2015-2018 hiking cycle into a 2008 stub and reported a
    ten-year 'cycle'."""
    dates, vals, splice = _spliced_policy_rate()
    moves = _policy_moves(dates, vals, splice)
    cycles: list[dict] = []
    cur: Optional[dict] = None
    for m in moves:
        dirn = "hike" if m["delta_pp"] > 0 else "cut"
        gap = None
        if cur:
            gap = (dt.date.fromisoformat(m["date"]) - dt.date.fromisoformat(cur["end"])).days / 30.44
        if cur is None or cur["direction"] != dirn or (gap is not None and gap > CYCLE_GAP_MONTHS):
            if cur:
                cycles.append(cur)
            cur = {"direction": dirn, "start": m["date"], "end": m["date"],
                   "from_rate": m["from_rate"], "to_rate": m["to_rate"], "moves": 1}
        else:
            cur["end"], cur["to_rate"] = m["date"], m["to_rate"]
            cur["moves"] += 1
    if cur:
        cycles.append(cur)

    today = dates[-1]
    spx_d, spx_v = _series("SPX")
    ctx = {name: _series(sym) for name, sym in AT_START}
    for c in cycles:
        c["total_pp"] = round(c["to_rate"] - c["from_rate"], 2)
        c["duration_days"] = (dt.date.fromisoformat(c["end"]) - dt.date.fromisoformat(c["start"])).days
        c["chair_at_start"] = chair_on(c["start"])
        # The market columns the hand-typed table carried, now attached to a
        # cycle that derives its own boundaries. None means the series does not
        # reach back this far and must render "unavailable".
        for name, sym in AT_START:
            d, v = ctx[name]
            val = _at(d, v, c["start"])
            c[f"{name}_at_start"] = round(val, 2) if val is not None else None
        win = [(d, v) for d, v in zip(spx_d, spx_v) if c["start"] <= d <= c["end"]]
        if win:
            pk = max(win, key=lambda x: x[1])
            tr = min(win, key=lambda x: x[1])
            c["spx_peak"] = {"date": pk[0], "value": round(pk[1], 2)}
            c["spx_trough"] = {"date": tr[0], "value": round(tr[1], 2)}
        else:
            c["spx_peak"] = c["spx_trough"] = None

    last = cycles[-1] if cycles else None
    prev_opposite = next((c for c in reversed(cycles[:-1]) if last and c["direction"] != last["direction"]), None)
    return {
        "cycles": cycles,
        "current": {
            "as_of": today,
            "rate": round(vals[-1], 2),
            "rate_source": f"{FEDFUNDS_SPLICE_SYMBOL} (target upper bound; a sheet quoting the lower bound will read 25bp lower)",
            "direction": last["direction"] if last else None,
            "cycle_began": last["start"] if last else None,
            "last_move": last["end"] if last else None,
            "days_since_last_move": (dt.date.fromisoformat(today) - dt.date.fromisoformat(last["end"])).days if last else None,
            "moves_this_cycle": last["moves"] if last else None,
            "chair": chair_on(today),
            "chair_confidence": chair_confidence(today),
            "previous_cycle": prev_opposite,
        },
        "computed_columns": [sym for _, sym in AT_START] + ["SPX"],
        "method": ("Derived from FEDFUNDS spliced to DFEDTARU. A cycle ends on a reversal "
                   f"or a hold longer than {CYCLE_GAP_MONTHS} months. Nothing here is typed in, "
                   "so a new move changes this table the day it prints."),
    }


def balance_sheet_regimes(window_days: int = 91, threshold_pct: float = 1.5,
                          min_days: int = 60) -> dict:
    """Expansion and contraction of the Fed balance sheet, derived from WALCL.

    QE and QT are visible in the series itself; only the programme NAMES have
    to be supplied, and those are joined on from QE_LABELS.
    """
    dates, vals = _series("WALCL")
    import bisect
    regimes: list[dict] = []
    cur: Optional[dict] = None
    for i, (d, v) in enumerate(zip(dates, vals)):
        j = bisect.bisect_left(dates, (dt.date.fromisoformat(d) - dt.timedelta(days=window_days)).isoformat())
        if j >= i:
            continue
        chg = (v / vals[j] - 1) * 100
        state = "expanding" if chg >= threshold_pct else "contracting" if chg <= -threshold_pct else "flat"
        if cur is None or cur["state"] != state:
            if cur and cur["state"] != "flat":
                regimes.append(cur)
            cur = {"state": state, "start": d, "end": d, "from_level": vals[j], "to_level": v}
        else:
            cur["end"], cur["to_level"] = d, v
    if cur and cur["state"] != "flat":
        regimes.append(cur)

    def label_for(r: dict) -> Optional[str]:
        for q in QE_LABELS:
            if r["start"] <= q["to"] and r["end"] >= q["from"]:
                return q["label"]
        return None

    # A regime that lasted a week is measurement noise crossing a threshold,
    # not a policy stance. Drop it rather than listing it beside QE3.
    regimes = [r for r in regimes
               if (dt.date.fromisoformat(r["end"]) - dt.date.fromisoformat(r["start"])).days >= min_days]
    for r in regimes:
        r["duration_days"] = (dt.date.fromisoformat(r["end"]) - dt.date.fromisoformat(r["start"])).days
        r["change_pct"] = round((r["to_level"] / r["from_level"] - 1) * 100, 1)
        r["from_tn"] = round(r["from_level"] / 1e6, 2)
        r["to_tn"] = round(r["to_level"] / 1e6, 2)
        r["label"] = label_for(r)
        r["chair_at_start"] = chair_on(r["start"])
    return {
        "regimes": regimes,
        "window_days": window_days,
        "threshold_pct": threshold_pct,
        "min_days": min_days,
        "method": (f"A {window_days}-day change in WALCL beyond +/-{threshold_pct}% marks expansion or "
                   "contraction. Programme names are annotations joined by date; the regime itself "
                   "is measured."),
    }


def joins() -> dict:
    """The association the user asked for: how often an inversion was followed
    by a real drawdown, and at what lag.

    Roughly six cycles. This is association on a handful of observations, not
    cause, and it says so.
    """
    inv = inversions()
    out = {}
    for label, rows in inv.items():
        done = [r for r in rows if r["months_inversion_to_peak"] is not None]
        led = [r for r in done if r["led_the_peak"]]
        lags = [r["months_inversion_to_peak"] for r in led]
        dds = [r["drawdown_pct"] for r in done if r["drawdown_pct"] is not None]
        out[label] = {
            "window": f"deepest decline peaking within {LOOKBACK_M}m before and {LOOKAHEAD_M}m after the inversion",
            "n_cycles": len(rows),
            "n_matched_to_a_decline": len(done),
            # Only cycles where the curve inverted BEFORE the top can be called
            # a lead. Averaging the others in would manufacture a lead time.
            "n_led_the_peak": len(led),
            "median_months_lead": round(st.median(lags), 1) if lags else None,
            "range_months_lead": [min(lags), max(lags)] if lags else None,
            "median_drawdown_pct": round(st.median(dds), 1) if dds else None,
        }
    return {
        "inversion_to_drawdown": out,
        "caveat": ("Six or so cycles per curve. Every figure carries its n. This is "
                   "association, not cause, and the sample is too small to be "
                   "anything else."),
    }


def build_context() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "drawdowns": drawdowns(),
        "inversions": inversions(),
        "rate_cycles": rate_cycles(),
        "balance_sheet": balance_sheet_regimes(),
        "joins": joins(),
    }
