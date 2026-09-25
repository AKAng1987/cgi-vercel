"""
brief_data.py -- the morning brief.

WHAT IT IS FOR
Manila morning is after the US close, so the daily brief covers the session
that just finished -- the user's own framing of what LIVE was always meant to
answer: "an overview of what happened the night before".

WHAT MAKES SOMETHING IMPORTANT
Not this module's judgement. Every headline comes from cgi_changes, where each
event is a rule that already existed in CGI and was written down before today,
ranked by how rarely it actually fires. This module only arranges them.

IF NOTHING CROSSED, IT SAYS SO.
That is the whole anti-flip discipline in one line. A brief that manufactures
something to say every morning is how a weeks-to-months process gets traded
daily, which is the problem CGI exists to fix. Most mornings should be quiet,
and a quiet morning is a finding, not a failure.

ORDER IS DELIBERATE
Fast layers first. Fundamentals lag price by three to six weeks -- they are
quarterly filings -- so they read as CONFIRMATION, never as news, and they sit
below the tape rather than above it.

EVERY SUB-SOURCE IS GUARDED
The brief reads seven other builders. One of them failing must degrade its own
section to a stated "unavailable", never take out the page: the morning it
matters most is the morning something is broken.
"""
from __future__ import annotations

import datetime as dt
import logging
from typing import Any, Callable, Optional

import cache
import cgi_changes
import cot_data
import fundamentals_data
import fundamentals_history
import markov_data
import policy_watch
import release_calendar as rc
import technicals_data
import themes_data

_logger = logging.getLogger("cgi_api.brief_data")

WINDOW = {"daily": 1, "weekly": 7}


def _try(label: str, fn: Callable[[], Any]) -> tuple[Optional[Any], Optional[str]]:
    try:
        return fn(), None
    except Exception as exc:
        _logger.exception("[brief] %s failed", label)
        return None, f"{type(exc).__name__}: {exc}"[:200]


def _section(name: str, headline: str, body: Any, error: Optional[str] = None) -> dict:
    return {"name": name, "headline": headline, "body": body,
            "status": "unavailable" if error else "ok", "error": error}


def build_brief(cadence: str = "daily") -> dict:
    cadence = cadence if cadence in WINDOW else "daily"
    window = WINDOW[cadence]
    today = dt.date.today()

    themes, e_th = _try("themes", lambda: cache.get_or_fetch(
        "themes", themes_data.build_themes_response))
    tech, e_te = _try("technicals", lambda: cache.get_or_fetch(
        "technicals", technicals_data.build_technicals_response))
    mk, e_mk = _try("markov", markov_data.build_markov_response)
    cot, e_ct = _try("cot", lambda: cache.get_or_fetch("cot", cot_data.build_cot_response))
    pol, e_pw = _try("policy", lambda: cache.get_or_fetch(
        "policy_watch", lambda: policy_watch.build_policy_watch(45)))
    fund, e_fu = _try("fundamentals", lambda: cache.get_or_fetch(
        "fundamentals", lambda: fundamentals_data.build_fundamentals_response()))

    # Filings first seen inside the window. Read from the history store rather
    # than from this build's own `changes`, because the fundamentals response
    # is cached for 24h and its change list belongs to whichever run happened
    # to recompute it -- not to the window being reported.
    recent_filings, _ = _try("filings", lambda: fundamentals_history.recent(
        days=max(window, 7) if cadence == "daily" else 14))

    fund_changes = []
    for r in (recent_filings or []):
        acc = r.get("acceleration_pp")
        if acc is not None and (acc >= fundamentals_history.SURPRISE_UP
                                or acc <= fundamentals_history.SURPRISE_DOWN):
            fund_changes.append({"kind": "fundamentals_surprise", "symbol": r["symbol"],
                                 "as_of": r.get("as_of"), "direction": "up" if acc > 0 else "down",
                                 "acceleration_pp": acc, "yoy_pct": r.get("yoy_pct"),
                                 "detail": (f"{r['symbol']} revenue {r.get('yoy_pct')}% YoY, "
                                            f"acceleration {acc:+.1f}pp")})
        if r.get("prev_verdict") and r.get("verdict") != r["prev_verdict"]:
            fund_changes.append({"kind": "fundamentals_verdict", "symbol": r["symbol"],
                                 "as_of": r.get("as_of"), "from": r["prev_verdict"],
                                 "to": r.get("verdict"),
                                 "detail": f"{r['symbol']} {r['prev_verdict']} -> {r.get('verdict')}"})

    changes, e_ch = _try("changes", lambda: cgi_changes.collect(
        window, themes=themes, technicals=tech, markov=mk, cot=cot, policy=pol,
        fundamental_changes=fund_changes))
    changes = changes or []
    pushable = cgi_changes.push_worthy(changes)

    sections: list[dict] = []

    # 1 regime -- the state everything else is conditioned on
    if mk:
        cur = mk.get("current") or {}
        nxt = (mk.get("upcoming") or [{}])[0] if mk.get("upcoming") else {}
        c, g = cur.get("compass"), cur.get("grid")
        # Q_TO_AXES maps a quadrant to (first axis up, second axis up):
        # compass is (liquidity, credit), grid is (growth, inflation).
        def _axes(q, names):
            t = rc.Q_TO_AXES.get(q)
            if not t:
                return ""
            return ", ".join(f"{n} {'up' if v else 'down'}" for n, v in zip(names, t))
        head = f"C{c}G{g}"
        detail = (f"{_axes(c, ('liquidity', 'credit'))}; "
                  f"{_axes(g, ('growth', 'inflation'))}")
        if nxt:
            detail += (f". Next: {nxt.get('type')} on {nxt.get('date')}, "
                       f"P({nxt.get('axis')} flips) = {nxt.get('p_flip')}")
        sections.append(_section("regime", f"{head} — {detail}",
                                 {"current": cur, "next_release": nxt,
                                  "pending": mk.get("pending")}))
    else:
        sections.append(_section("regime", "unavailable", None, e_mk))

    # 2 breadth -- colour and cross are separate reads, both always reported
    if tech:
        nnh = tech.get("net_new_highs") or {}
        # The whole technicals response, because BreadthStrip already takes
        # exactly that shape -- reshaping it here would mean a second component
        # to keep in step with the first.
        sections.append(_section(
            "breadth", nnh.get("state") or nnh.get("colour", "?"), tech))
    else:
        sections.append(_section("breadth", "unavailable", None, e_te))

    # 3 themes -- what is running, what just started, what just broke
    if themes:
        running = [t for t in themes.get("themes", []) if t.get("age_days") is not None]
        started = [t for t in running
                   if t.get("onset") and (today - dt.date.fromisoformat(t["onset"])).days <= window]
        sections.append(_section(
            "themes",
            (f"{len(started)} started, {len(running)} running"
             if started else f"{len(running)} running, none new"),
            {"started": started,
             "standing": themes.get("standing"),
             "run_stats": themes.get("run_stats"),
             # full rows, unsorted slice removed: ThemesTable does its own
             # grouping into megatrend / running / dormant
             "running": themes.get("themes", [])}))
    else:
        sections.append(_section("themes", "unavailable", None, e_th))

    # 4 fundamentals -- confirmation, not news
    if fund:
        sections.append(_section(
            "fundamentals",
            (f"{len(fund_changes)} filing change(s)" if fund_changes else "no new filings"),
            {"changes": fund_changes, "ai_layers": fund.get("ai_layers"),
             "themes": fund.get("themes"), "coverage": fund.get("coverage")}))
    else:
        sections.append(_section("fundamentals", "unavailable", None, e_fu))

    # 5 positioning -- Fridays daily, always weekly (COT publishes Friday)
    if cadence == "weekly" or today.weekday() == 4:
        if cot:
            ex = cot.get("extremes") or []
            sections.append(_section("positioning", f"{len(ex)} contracts at an extreme",
                                     {"extremes": ex, "as_of": cot.get("as_of"),
                                      "caveat": cot.get("caveat")}))
        else:
            sections.append(_section("positioning", "unavailable", None, e_ct))

    # 6 policy candidates
    if pol:
        cands = [c for c in (pol.get("candidates") or [])
                 if c.get("announced") and
                 (today - dt.date.fromisoformat(c["announced"][:10])).days <= max(window, 7)]
        sections.append(_section("policy", f"{len(cands)} candidate(s)",
                                 {"candidates": cands, "no_feed": pol.get("no_feed")}))
    else:
        sections.append(_section("policy", "unavailable", None, e_pw))

    # 7 weekly only: ageing against the survival curve, and what is due
    if cadence == "weekly" and themes:
        ageing = sorted(
            [t for t in themes.get("themes", [])
             if t.get("survival_pct") is not None and t.get("class") != "megatrend"],
            key=lambda t: t["survival_pct"])[:8]
        sections.append(_section(
            "ageing", f"{len(ageing)} themes with the least runway left",
            {"themes": ageing, "run_stats": themes.get("run_stats")}))
        due, _ = _try("calendar", lambda: rc.releases_between(
            today.isoformat(), (today + dt.timedelta(days=10)).isoformat()))
        sections.append(_section("due", "releases in the next 10 days", due or []))

    unavailable = [s["name"] for s in sections if s["status"] == "unavailable"]
    return {
        "cadence": cadence,
        "as_of": today.isoformat(),
        "window_days": window,
        "covers": ("the US session that just closed" if cadence == "daily"
                   else "the past week"),
        # The headline IS the discipline: most mornings nothing crossed.
        "nothing_crossed": not changes,
        "headline": ("Nothing crossed." if not changes
                     else f"{len(changes)} crossed, {len(pushable)} worth a notification."),
        "changes": changes,
        "push": pushable,
        "sections": sections,
        "unavailable": unavailable,
        "note": ("Importance is a diff against rules already written down, ranked by how "
                 "rarely each one fires -- not a judgement made each morning."),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
