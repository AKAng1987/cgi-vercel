"""
cgi_changes.py -- what crossed, and how unusual that is.

THE POINT
A brief that summarises everything every morning trains you to ignore it, and
"trust Claude to pick the interesting bits" is not auditable. So importance is
not a judgement made here. Every event below is a rule that already exists
somewhere in CGI, written down before today:

  compass / grid flip      the pre-registered Markov event log
  theme onset / end        themes_data's 80%-persistence run definition
  standing exit rule       the exit conditions the USER wrote, in STANDING
  breadth colour / cross   the user's own CONSEC=3 and 8/20 rules
  COT extreme              cot_data's 10 / 90 bands
  fundamentals surprise    a MEASURED p95/p5 of the acceleration distribution
  policy candidate         policy_watch's central-bank feeds

RANKED BY MEASURED RARITY, NOT BY OPINION
Each kind carries how often it actually fires, counted from the same history
the rest of CGI runs on (2026-09-25):

  compass axis flip     2.5/yr    55 events, 22 years
  grid axis flip        8.9/yr   165 events, 18 years
  breadth 8/20 cross   21.6/yr   430 events, 20 years
  breadth colour       32.1/yr   639 events, 20 years

Rarity = 1/rate, so a compass flip outranks a breadth colour change by ~13x
automatically. Nothing is promoted because it feels significant.

MOSTLY STATELESS, DELIBERATELY
Themes carry an onset date, breadth carries its last cross, the Markov layer
carries event dates -- so "did this change" is read straight off the data and
needs no stored snapshot. Only fundamentals need memory, because a filing does
not announce that it differs from the last one; that lives in
fundamentals_history.py.

If nothing crossed, this returns an empty list and the brief says so. That is
the anti-flip discipline, and on most days it is the correct output.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Optional

import cgi_state

_logger = logging.getLogger("cgi_api.cgi_changes")

# kind -> (events per year, push-worthy). Rates measured from CGI's own
# history; see the module docstring. A rate of None means "not yet counted",
# and those sort below everything that has been.
RATES: dict[str, tuple[Optional[float], bool]] = {
    "regime_flip_compass": (2.5, True),
    "standing_exit_touched": (3.0, True),      # by construction, rare
    "regime_flip_grid": (8.9, True),
    "theme_onset": (36.0, True),               # ~727 runs / 20y across all proxies
    "fundamentals_surprise": (26.0, True),     # p95 of 4,545 company-quarters
    "cot_extreme": (40.0, True),
    "theme_end": (36.0, False),
    "fundamentals_verdict": (60.0, False),
    "breadth_cross": (21.6, False),
    "breadth_colour": (32.1, False),
    "policy_candidate": (50.0, False),
}


def _rarity(kind: str) -> float:
    rate = RATES.get(kind, (None, False))[0]
    return 0.0 if not rate else 1.0 / rate


def _days_ago(date: Optional[str], today: dt.date) -> Optional[int]:
    if not date:
        return None
    try:
        return (today - dt.date.fromisoformat(date[:10])).days
    except ValueError:
        return None


def collect(window_days: int = 1, *, themes=None, technicals=None, markov=None,
            cot=None, policy=None, fundamental_changes=None) -> list[dict]:
    """Everything that crossed inside the window, rarest first.

    Each source is optional and independently guarded: one dead sub-source
    must degrade its own line, never the whole brief.
    """
    today = dt.date.today()
    out: list[dict] = []

    def add(kind: str, title: str, detail: str, when: Optional[str] = None, **extra):
        out.append({"kind": kind, "title": title, "detail": detail, "when": when,
                    "rate_per_year": RATES.get(kind, (None, False))[0],
                    "push": RATES.get(kind, (None, False))[1],
                    "rarity": _rarity(kind), **extra})

    # ── regime ──────────────────────────────────────────────────────────────
    try:
        # markov_data calls this event_log, not events -- reading the wrong key
        # meant regime flips, the single most important event CGI has, would
        # have silently never fired.
        for ev in (markov or {}).get("event_log", []) or []:
            d = _days_ago(ev.get("date"), today)
            if d is None or d > window_days:
                continue
            axis = ev.get("axis", "")
            kind = ("regime_flip_compass" if axis in ("liquidity", "credit")
                    else "regime_flip_grid")
            qb, qa = ev.get("quadrant_before"), ev.get("quadrant_after")
            moved = f"{qb} -> {qa}" if qa is not None else f"from quadrant {qb}"
            pre = ev.get("p_flip")
            add(kind, f"{axis.upper()} flipped on {ev.get('type')}",
                (f"{ev.get('model')} {moved}"
                 + (f"; pre-registered P(flip) was {pre:.0%}" if pre is not None else "")
                 + (f", market said {ev['p_market']:.0%}" if ev.get("p_market") is not None else "")),
                ev.get("date"), axis=axis)
    except Exception:
        _logger.exception("[changes] markov")

    # ── themes: onset, end, and the user's own exit rules ───────────────────
    try:
        for t in (themes or {}).get("themes", []) or []:
            d = _days_ago(t.get("onset"), today)
            if t.get("age_days") is not None and d is not None and d <= window_days:
                add("theme_onset", f"{t['theme']} started a run",
                    (f"RS above its 200d trend from {t['onset']}; "
                     f"lead {t.get('lead_symbol')}, "
                     f"{int((t.get('survival_pct') or 0) * 100)}% of past runs lasted longer"),
                    t.get("onset"), theme=t["theme"])
            for leg in t.get("legs", []) or []:
                if leg.get("status") == "no active run":
                    dd = _days_ago(leg.get("last_above"), today)
                    if dd is not None and dd <= window_days:
                        add("theme_end", f"{t['theme']}: {leg['symbol']} lost its trend",
                            f"{leg['symbol']} RS below its 200d trend, "
                            f"{leg.get('rs_vs_trend_pct')}% under",
                            leg.get("last_above"), theme=t["theme"])

        # Standing themes carry exit rules the user wrote. The measurable half
        # is "lead proxy below its 200d trend for 6 consecutive weeks"; the
        # rest is judgement and is surfaced for review rather than evaluated.
        legs_by_symbol = {}
        for t in (themes or {}).get("themes", []) or []:
            for leg in t.get("legs", []) or []:
                legs_by_symbol[leg.get("symbol")] = leg
        for st in (themes or {}).get("standing", []) or []:
            broken = [s for s in st.get("expressions", [])
                      if legs_by_symbol.get(s, {}).get("status") == "no active run"]
            if broken and len(broken) >= max(1, len(st.get("expressions", [])) // 2):
                add("standing_exit_touched", f"Standing theme under its exit rule: {st['name']}",
                    (f"{len(broken)} of {len(st.get('expressions', []))} tracked proxies "
                     f"({', '.join(broken)}) are below their 200d RS trend. "
                     f"Your exit rule: {st.get('exit_rule', '')[:160]}"),
                    None, theme=st["name"])
    except Exception:
        _logger.exception("[changes] themes")

    # ── breadth ─────────────────────────────────────────────────────────────
    try:
        nnh = (technicals or {}).get("net_new_highs") or {}
        lc = nnh.get("last_cross") or {}
        if lc.get("days_ago") is not None and lc["days_ago"] <= window_days:
            add("breadth_cross", f"Breadth 8/20 crossed {lc.get('direction')}",
                nnh.get("cross_signal") or "", lc.get("date"))
        if nnh.get("streak_days") == 3 and nnh.get("colour") in ("red", "green"):
            add("breadth_colour", f"Breadth turned {nnh['colour']}",
                nnh.get("state") or "", (technicals or {}).get("as_of"))
    except Exception:
        _logger.exception("[changes] technicals")

    # ── positioning ─────────────────────────────────────────────────────────
    # Only a contract ENTERING an extreme is an event. Positioning stays
    # pinned for months -- cot_data records 2011 sitting max short while price
    # kept falling -- so reporting the standing condition would have pushed
    # seven notifications on day one, the same seven every morning after.
    # A contract already extreme last week is carried on the page, not pushed.
    try:
        extremes = (cot or {}).get("extremes", []) or []
        prior = set(cgi_state.get("cot_extremes").get("contracts", []))
        now = [e.get("contract") for e in extremes if e.get("contract")]
        first_run = not prior
        for e in extremes:
            name = e.get("contract")
            entered = name not in prior
            # First ever run has no prior state; treat everything as standing
            # rather than firing the whole book at once.
            if first_run:
                entered = False
            out.append({
                "kind": "cot_extreme", "title": f"{name} positioning at an extreme",
                "detail": (f"COT index {e.get('cot_index_3y')} (3y), "
                           f"{e.get('cot_index_3y_pct_oi')} on share of open interest; "
                           f"{e.get('signal') or ''}"),
                "when": (cot or {}).get("as_of"), "contract": name,
                "rate_per_year": RATES["cot_extreme"][0],
                "push": bool(entered),          # standing extremes never push
                "newly_entered": bool(entered),
                "rarity": _rarity("cot_extreme") * (1.0 if entered else 0.15),
            })
        if now:
            cgi_state.put("cot_extremes", {"contracts": now,
                                           "as_of": (cot or {}).get("as_of")})
    except Exception:
        _logger.exception("[changes] cot")

    # ── fundamentals (the one source that needs memory) ─────────────────────
    try:
        for ch in fundamental_changes or []:
            if ch["kind"] == "fundamentals_surprise":
                add("fundamentals_surprise",
                    f"{ch['symbol']} revenue {ch['direction']} sharply", ch["detail"],
                    ch.get("as_of"), symbol=ch["symbol"])
            else:
                add("fundamentals_verdict",
                    f"{ch['symbol']}: {ch.get('from')} -> {ch.get('to')}", ch["detail"],
                    ch.get("as_of"), symbol=ch["symbol"])
    except Exception:
        _logger.exception("[changes] fundamentals")

    # ── policy ──────────────────────────────────────────────────────────────
    try:
        for c in (policy or {}).get("candidates", []) or []:
            d = _days_ago(c.get("announced"), today)
            if d is not None and d <= window_days:
                add("policy_candidate", f"{c.get('country')}: {c.get('title')}",
                    f"{c.get('source')} -- confirm it to become a policy note",
                    c.get("announced"), link=c.get("link"))
    except Exception:
        _logger.exception("[changes] policy")

    out.sort(key=lambda e: (-e["rarity"], e.get("when") or ""))
    return out


def push_worthy(changes: list[dict]) -> list[dict]:
    return [c for c in changes if c.get("push")]
