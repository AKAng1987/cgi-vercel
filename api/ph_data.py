"""Philippines tab: storage of the three PH snapshots and (below) the response the page reads.

Nothing here calls TradingView (it is reachable only through a model); the daily builders run unattended from launchd.
Snapshots live in the same S3 folder as the other offline-built blobs (cache.PREFIX + "ph/<name>.json"):
  edge      built by ~/market-dashboard/scripts/ph_edge_build.py from PSE EDGE (disclosures, results, buy-backs)
  screener  built by ~/market-dashboard/scripts/ph_prices_build.py from EDGE's own daily bars (open/high/low/close/value traded)
            plus PSEi from Yahoo: returns, EMAs, 3-month range, 30-day average value traded, float and market cap
  breadth   exported from Pulse (export_ph_breadth.py)
  bars      daily OHLC + value traded for the last 300 sessions of the liquid and extra (COL, CTS) names (the page's chart dock)
  bsp       what the Monetary Board said at each decision (posted by the decision-day task: the BSP's own site refuses scripts)
  index     announced index changes (PSE circulars read by ph_index_watch.py; MSCI/FTSE/WisdomTree rows posted on announcement days)
  macro     PMI history, appended from the calendar's actuals (S&P Global PMI has no ECONOMICS series)
EDGE's terms forbid storing or redistributing its data without PSE's consent: `edge` holds only titles, dates, the few
figures the page shows and the link number back to the filing, never a copy of a filing.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

_logger = logging.getLogger("cgi_api.ph")
NAMES = ("edge", "screener", "breadth", "macro", "bars", "index", "bsp")


def _key(name: str) -> str:
    import cache

    if name not in NAMES:
        raise ValueError(f"unknown PH snapshot {name!r}")
    return cache.PREFIX + f"ph/{name}.json"


def write_blob(name: str, obj: dict) -> None:
    import cache

    cache._s3.put_object(Bucket=cache.BUCKET, Key=_key(name), Body=json.dumps(obj, separators=(",", ":")).encode("utf-8"),
                         ContentType="application/json")
    if name in ("edge", "screener", "breadth", "macro", "index", "bsp"):
        try:
            cache.invalidate("ph")          # the next warm-up (not a visitor) rebuilds the page from the new snapshot
        except Exception as e:  # noqa: BLE001 -- the snapshot is stored; the cache expires on its own within the hour
            _logger.warning("[ph] could not drop the cached page: %s", e)


def _label_key(v: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", " ", v.lower().replace("&", " and ")).strip()


def merge_labels(rows: list[dict]) -> list[dict]:
    """EDGE spells the same sector two ways (LTL: "PROPERTY" beside "Property"; "Power & Water" beside "Power and Water"), which splits a
    segment in two. Rows get the most common spelling of each, ties going to the one that is not all capitals."""
    from collections import Counter

    for field in ("ind", "sec"):
        seen: dict[str, Counter] = {}
        for r in rows:
            if r.get(field):
                seen.setdefault(_label_key(r[field]), Counter())[r[field]] += 1
        pick = {k: max(c, key=lambda v: (c[v], not v.isupper())) for k, c in seen.items()}
        for r in rows:
            if r.get(field):
                r[field] = pick[_label_key(r[field])]
    return rows


def screener_blob() -> dict:
    shot = read_blob("screener") or {}
    if shot.get("rows"):
        merge_labels(shot["rows"])
    return shot


def read_blob(name: str) -> Optional[dict]:
    import os

    local = os.environ.get("PH_LOCAL_DIR")       # development only: read <dir>/<name>.json instead of S3
    if local and os.path.exists(os.path.join(local, f"{name}.json")):
        return json.load(open(os.path.join(local, f"{name}.json")))
    import cache

    try:
        return json.loads(cache._s3.get_object(Bucket=cache.BUCKET, Key=_key(name))["Body"].read())
    except Exception as e:  # noqa: BLE001
        _logger.warning("[ph] %s snapshot unavailable: %s", name, e)
        return None


# ── screener snapshot (posted by the morning routine) ────────────────────────

MAX_ROWS = 400
LIQ_MIN = 5_000_000        # average value traded over 30 sessions, pesos a day: the line the Pulse breadth card also uses
HORIZONS = {"1D": "d", "1W": "w", "1M": "m", "3M": "q", "YTD": "y"}


def _f(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) < 1e16 else None


# ── views (pure) ─────────────────────────────────────────────────────────────

def is_extra(r: dict) -> bool:
    """COL and CTS: names Arvin asked for by name, kept in every list whatever they trade (`pinned` is the earlier spelling)."""
    return bool(r.get("extra") or r.get("pinned"))


def liquid(rows: list[dict]) -> list[dict]:
    """The names every list is built from: trading at least LIQ_MIN a day (30-session average), plus the extra names."""
    return [r for r in rows if r.get("c") and ((r.get("v30") or 0) >= LIQ_MIN or is_extra(r))]


def _vs(c, e):
    return round((c / e - 1) * 100, 1) if c and e else None


def _row_view(r: dict, key: str) -> dict:
    return {"s": r["s"], "ret": r.get(key), "c": r["c"], "vs50": _vs(r["c"], r.get("e50")), "vs200": _vs(r["c"], r.get("e200")),
            "vt": r.get("vt"), "ind": r.get("ind"), "sec": r.get("sec"), "psei": r.get("psei", 0),
            "from_high3m": _vs(r["c"], r.get("h3")), "d": r.get("d"), "w": r.get("w"), "m": r.get("m"), "q": r.get("q"), "y": r.get("y")}


def leaderboard(rows: list[dict], key: str, n_top: int = 15, n_bottom: int = 10) -> dict:
    live = [r for r in liquid(rows) if r.get(key) is not None]
    live.sort(key=lambda r: r[key], reverse=True)
    return {"horizon_key": key, "n": len(live), "top": [_row_view(r, key) for r in live[:n_top]],
            "bottom": [_row_view(r, key) for r in live[::-1][:n_bottom]]}


def segments(rows: list[dict], key: str, by: str = "ind", min_n: int = 2) -> list[dict]:
    import statistics as st

    g: dict[str, list[dict]] = {}
    for r in liquid(rows):
        if r.get(key) is not None and r.get(by):
            g.setdefault(r[by], []).append(r)
    out = []
    for name, rs in g.items():
        if len(rs) < min_n:
            continue
        rs.sort(key=lambda r: r[key], reverse=True)
        out.append({"name": name, "n": len(rs), "median": round(st.median(r[key] for r in rs), 1),
                    "pct_up": round(100 * sum(1 for r in rs if r[key] > 0) / len(rs)), "top": rs[0]["s"], "top_ret": round(rs[0][key], 1),
                    "members": [r["s"] for r in rs[:6]]})
    out.sort(key=lambda x: x["median"], reverse=True)
    return out


def expected_report(sym: str, edge: dict, today, days: int = 35) -> Optional[dict]:
    """The estimated next reporting date for one company, or None when it already filed this season or has no history."""
    import datetime as dt

    dates = sorted((edge.get("filing_dates") or {}).get(sym, []))
    last_res = max((r["announced"][:10] for r in edge.get("results", []) if r["symbol"] == sym), default="")
    last = max(last_res, dates[-1] if dates else "")
    if last and (today - dt.date.fromisoformat(last)).days < 45:
        return None                                        # already reported this season
    end = today + dt.timedelta(days=days)
    cands = []
    for d in dates:
        est = dt.date.fromisoformat(d) + dt.timedelta(days=365)
        while est.weekday() >= 5:
            est += dt.timedelta(days=1)
        if today <= est <= end:
            cands.append((est, d))
    if not cands:
        return None
    est, basis = min(cands)
    return {"date": est.isoformat(), "basis": f"filed {basis} last year"}


def earnings_next(rows: list[dict], edge: dict, today, days: int = 35) -> list[dict]:
    """Expected reporting dates for liquid names. EDGE publishes no calendar, so the estimate is last year's filing date for the
    same report plus 365 days (companies file within a few days of the same date each year); names that already filed this
    quarter are left out. Labelled as an estimate on the page."""
    out = []
    for r in liquid(rows):
        e = expected_report(r["s"], edge, today, days)
        if e:
            out.append({"s": r["s"], **e, "mc": r.get("mc"), "psei": r.get("psei", 0), "ind": r.get("ind")})
    out.sort(key=lambda x: (x["date"], -(x["mc"] or 0)))
    return out


def _pesos(v, scale):
    return None if v is None else v * (scale or 1.0)


def results_view(edge: dict, rows: list[dict], today, days: int = 60) -> list[dict]:
    """Reported results with year-on-year change from the filing's own prior-year column. Most recent first."""
    import datetime as dt

    sec = {r["s"]: r for r in rows}
    cut = (today - dt.timedelta(days=days)).isoformat()

    def yoy(cur, prev):
        """None when either side is a loss: the page says 'loss' or 'swing to profit' instead of a percentage."""
        return None if cur is None or prev is None or prev <= 0 or cur < 0 else round((cur / prev - 1) * 100, 1)

    out = []
    for r in edge.get("results", []):
        if r["announced"][:10] < cut:
            continue
        ni, nip = r.get("net_income_parent"), r.get("net_income_parent_prev")
        out.append({"s": r["symbol"], "kind": r["kind"], "period": r["period"], "announced": r["announced"], "edge_no": r["edge_no"],
                    "revenue": _pesos(r.get("revenue"), r.get("scale")), "rev_yoy": yoy(r.get("revenue"), r.get("revenue_prev")),
                    "ni": _pesos(ni, r.get("scale")), "ni_yoy": yoy(ni, nip), "ni_loss": bool(ni is not None and ni < 0),
                    "ni_swing": bool(ni is not None and nip is not None and nip <= 0 < ni),
                    "ytd_ni_yoy": yoy(r.get("net_income_parent_ytd"), r.get("net_income_parent_prev_ytd")),
                    "eps": r.get("eps"), "eps_prev": r.get("eps_prev"), "ind": (sec.get(r["symbol"]) or {}).get("ind"),
                    "ret_1m": (sec.get(r["symbol"]) or {}).get("m"), "psei": (sec.get(r["symbol"]) or {}).get("psei", 0)})
    out.sort(key=lambda x: x["announced"], reverse=True)
    return out


def buyback_board(edge: dict, today, days: int = 60) -> list[dict]:
    import datetime as dt

    c30 = (today - dt.timedelta(days=30)).isoformat()
    c60 = (today - dt.timedelta(days=days)).isoformat()
    g: dict[str, list[dict]] = {}
    for b in edge.get("buybacks", []):
        if b["report_date"] >= c60:
            g.setdefault(b["symbol"], []).append(b)
    out = []
    for sym, bs in g.items():
        bs.sort(key=lambda b: b["report_date"], reverse=True)
        last = bs[0]
        recent = [b for b in bs if b["report_date"] >= c30]
        sh = sum(b["shares"] for b in recent)
        val = sum(b["value"] for b in recent)
        out.append({"s": sym, "last_date": last["report_date"], "reports_30d": len(recent), "shares_30d": sh, "value_30d": val,
                    "avg_price_30d": round(val / sh, 4) if sh else None,
                    "pct_outstanding_30d": round(100 * sh / last["outstanding_after"], 3) if sh and last.get("outstanding_after") else None,
                    "cumulative": next((b["cumulative"] for b in bs if b.get("cumulative")), None),
                    "total_repurchased": next((b["total_repurchased"] for b in bs if b.get("total_repurchased")), None),
                    "edge_no": last["edge_no"]})
    out.sort(key=lambda x: (x["value_30d"], x["last_date"]), reverse=True)
    return out


def material_feed(edge: dict, today, days: int = 14, limit: int = 160) -> list[dict]:
    import datetime as dt

    cut = (today - dt.timedelta(days=days)).isoformat()
    bb = {b["edge_no"]: b for b in edge.get("buybacks", [])}
    res = {r["edge_no"]: r for r in edge.get("results", [])}
    out = []
    for d in edge.get("disclosures", []):
        if d["announced"][:10] < cut or d["chip"] == "other":
            continue
        row = {k: d[k] for k in ("symbol", "company", "chip", "form", "title", "amend", "announced", "edge_no")}
        row.update({k: d[k] for k in ("subject", "dividend", "insider") if k in d})
        b = bb.get(d["edge_no"])
        if b:
            row["buyback"] = {"shares": b["shares"], "avg_price": b["avg_price"], "value": b["value"]}
        r = res.get(d["edge_no"])
        if r:
            row["period"] = r["period"]
        out.append(row)
    out.sort(key=lambda x: x["announced"], reverse=True)
    return out[:limit]


def rebalance_watch(rows: list[dict], n: int = 8) -> dict:
    """Where PSEi membership could change: members ranked by free-float market cap against the largest non-members.
    A screen on public numbers, not PSE's method (which also weighs trading days and value traded over its review period)."""
    def ffmc(r):
        return (r.get("mc") or 0) * (r.get("fl") or 0) / 100.0

    live = liquid(rows)
    members = sorted((r for r in live if r.get("psei")), key=ffmc, reverse=True)
    others = sorted((r for r in live if not r.get("psei") and ffmc(r) > 0), key=ffmc, reverse=True)
    smallest = ffmc(members[-1]) if members else 0

    def view(r, rank=None):
        return {"s": r["s"], "ffmc": ffmc(r), "mc": r.get("mc"), "fl": r.get("fl"), "vt": r.get("vt"), "ind": r.get("ind"),
                "ret_3m": r.get("q"), "rank": rank}
    return {"n_members": len(members),
            "members": [view(r, i + 1) for i, r in enumerate(members)],
            "weakest_members": [view(r, len(members) - i) for i, r in enumerate(members[::-1][:5])],
            "nearest_non_members": [dict(view(r), vs_smallest_member=round(ffmc(r) / smallest, 2) if smallest else None)
                                    for r in others[:n]],
            "method": "free-float market cap (market cap x float %) among liquid names; PSE also weighs value traded and trading days"}


# ── one symbol (chart dock) ────────────────────────────────────────────────

EMA_SPANS = (5, 10, 20, 50, 100, 200)
_bars_memo: dict = {"at": 0.0, "blob": None}


def ema_series(values: list[float], n: int) -> list[float]:
    k = 2.0 / (n + 1)
    out, e = [], None
    for v in values:
        e = v if e is None else v * k + e * (1 - k)
        out.append(round(e, 4))
    return out


def _bars_blob() -> dict:
    import time

    if _bars_memo["blob"] is None or time.monotonic() - _bars_memo["at"] > 1800:
        _bars_memo.update(blob=read_blob("bars") or {}, at=time.monotonic())
    return _bars_memo["blob"]


def chart_series(bars: list[list], show: int = 160) -> dict:
    """Last `show` bars with the 5/10/20/50/100/200 EMAs computed over the whole stored series (so EMA200 is warmed up)."""
    closes = [b[4] for b in bars]
    emas = {str(n): ema_series(closes, n)[-show:] for n in EMA_SPANS}
    return {"bars": bars[-show:], "ema": emas, "n_stored": len(bars)}


def chart_events(sym: str, edge: dict, res: list[dict], first: str, last: str, limit: int = 70) -> list[dict]:
    """Filings to mark on the chart: results (R), buy-back reports (B), insider buys and sells (I), dividends (D), material information
    (M), corporate actions (C), ownership and tender reports (O). Date = the day it was announced (buy-backs: the report date). Only
    events inside the bars shown; each carries the EDGE filing number so the page can link to it."""
    ev = []
    for r in res:
        d = r["announced"][:10]
        label = (f"{'FY' if r['kind'] == 'A' else 'Q to ' + r['period'][5:7] + '/' + r['period'][2:4]}: revenue "
                 f"{'n/a' if r.get('rev_yoy') is None else format(r['rev_yoy'], '+.1f') + '%'}, net income "
                 f"{'loss' if r.get('ni_loss') else 'swing to profit' if r.get('ni_swing') else 'n/a' if r.get('ni_yoy') is None else format(r['ni_yoy'], '+.1f') + '%'}")
        ev.append({"date": d, "type": "R", "label": label, "edge_no": r["edge_no"]})
    for b in edge.get("buybacks", []):
        if b["symbol"] == sym:
            ev.append({"date": b["report_date"], "type": "B", "label": f"buy-back {int(b['shares']):,} sh @ {b['avg_price']:g}", "edge_no": b["edge_no"]})
    kind = {"material": "M", "insider": "I", "dividend": "D", "corporate": "C", "ownership": "O"}
    for d in edge.get("disclosures", []):
        if d["symbol"] != sym or d["chip"] not in kind:
            continue
        t = kind[d["chip"]]
        label = d.get("subject") or d["title"]
        side = None
        if t == "I" and d.get("insider"):
            side = d["insider"]["side"]
            label = f"{d['insider'].get('name') or 'insider'} {side} {int(abs(d['insider']['net_shares'])):,} sh"
        if t == "D" and d.get("dividend"):
            label = f"dividend ₱{d['dividend']['per_share']:g} a share, record {d['dividend'].get('record') or '?'}"
        ev.append({"date": d["announced"][:10], "type": t, "label": label[:140], "edge_no": d["edge_no"], **({"side": side} if side else {})})
    ev = [e for e in ev if first <= e["date"] <= last]
    ev.sort(key=lambda e: e["date"], reverse=True)
    return ev[:limit]


def symbol_view(sym: str, today=None) -> dict:
    """Everything the chart dock shows for one ticker: bars with EMAs, its snapshot numbers, the last results (with y/y),
    buy-backs and disclosures, and its estimated next report date. 'PSEI' returns the index close history instead."""
    import datetime as dt

    today = today or dt.datetime.now(dt.timezone.utc).date()
    sym = sym.upper()
    shot = screener_blob()
    edge = read_blob("edge") or {}
    if sym == "PSEI":
        hist = shot.get("psei_history") or {}
        return {"symbol": "PSEI", "name": "PSEi", "kind": "index", "line": [[d, v] for d, v in list(hist.items())[-160:]],
                "numbers": shot.get("psei_index"), "disclosures": [], "results": [], "buybacks": []}
    row = next((r for r in shot.get("rows", []) if r["s"] == sym), None)
    bars = _bars_blob().get("bars", {}).get(sym, [])
    directory = (edge.get("directory") or {}).get(sym, {})
    res = results_view({"results": [r for r in edge.get("results", []) if r["symbol"] == sym]}, shot.get("rows", []), today, days=800)
    bb = [b for b in edge.get("buybacks", []) if b["symbol"] == sym][:3]
    disc = [d for d in edge.get("disclosures", []) if d["symbol"] == sym and d["chip"] != "other"][:12]
    shown = bars[-160:]
    return {
        "events": chart_events(sym, edge, res, shown[0][0], shown[-1][0]) if shown else [],
        "symbol": sym, "name": directory.get("name"), "sector": directory.get("sector"), "subsector": directory.get("subsector"), "kind": "stock",
        "numbers": _row_view(row, "m") | {"mc": row.get("mc"), "v30": row.get("v30"), "fl": row.get("fl"), "h3": row.get("h3"), "l3": row.get("l3"),
                                         "liquid": bool(row.get("v30") and row["v30"] >= LIQ_MIN), "extra": 1 if is_extra(row) else 0} if row else None,
        **chart_series(bars), "expected_report": expected_report(sym, edge, today),
        "results": res[:3], "buybacks": [{k: b.get(k) for k in ("report_date", "shares", "avg_price", "value", "cumulative", "edge_no")} for b in bb],
        "disclosures": [{k: d.get(k) for k in ("announced", "chip", "title", "subject", "dividend", "insider", "edge_no", "amend")} for d in disc],
    }


# ── macro, calendar, and the response ────────────────────────────────────────

# (key, CGI symbol, label, unit, kind) kind: rate = already a rate, show change in points; level = show YoY % of the level
MACRO = [
    ("policy", "PH_POLICY_RATE", "BSP policy rate", "%", "rate"),
    ("cpi", "PH_CPI_YOY", "Inflation y/y", "%", "rate"),
    ("core", "PH_CORE_CPI", "Core inflation y/y", "%", "rate"),
    ("cpi_mom", "PH_CPI_MOM", "Inflation m/m", "%", "rate"),
    ("gdp_yoy", "PH_GDP_YOY", "GDP y/y", "%", "rate"),
    ("gdp_qoq", "PH_GDP_QOQ", "GDP q/q", "%", "rate"),
    ("unemployment", "PH_UNEMPLOYMENT", "Unemployment rate", "%", "rate"),
    ("loans", "PH_LOANS_PRIVATE", "Bank lending (private sector)", "level", "level"),
    ("ip", "PH_IP_YOY", "Industrial production y/y", "%", "rate"),
    ("remit", "PH_REMITTANCES", "Cash remittances", "USD", "level"),
    ("reserves", "PH_FX_RESERVES", "FX reserves", "USD", "level"),
    ("m2", "PH_M2", "M2", "level", "level"),
]
_MONTHS = {m: i + 1 for i, m in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))}


def pmi_month(period: Optional[str], release_iso: str) -> Optional[str]:
    """'Oct' released on 2026-11-02 -> '2026-10'; 'Dec' released 2027-01-04 -> '2026-12'."""
    import datetime as dt

    m = _MONTHS.get((period or "")[:3].title())
    if not m:
        return None
    rel = dt.date.fromisoformat(release_iso)
    y = rel.year if m <= rel.month else rel.year - 1
    return f"{y}-{m:02d}"


def pmi_update(rows: list[dict]) -> dict:
    """Fold PH Manufacturing PMI actuals (and the 'previous' of each release) into the macro blob. S&P Global publishes the
    headline only; TradingView carries it in the calendar, so history is built from now on. Never raises."""
    try:
        blob = read_blob("macro") or {}
        pmi = dict(blob.get("pmi", {}))
        n0 = len(pmi)
        for r in rows:
            if r.get("country") != "PH" or r.get("kind") != "pmi":
                continue
            key = pmi_month(r.get("period"), r["date"])
            if not key:
                continue
            if r.get("actual") is not None:
                pmi[key] = r["actual"]
            if r.get("previous") is not None:
                y, m = int(key[:4]), int(key[5:])
                pk = f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"
                pmi.setdefault(pk, r["previous"])
        if len(pmi) != n0 or pmi != blob.get("pmi"):
            write_blob("macro", {"pmi": dict(sorted(pmi.items())), "at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds")})
        return {"months": len(pmi), "added": len(pmi) - n0}
    except Exception as e:  # noqa: BLE001 -- additive; the calendar post must not fail on this
        return {"error": str(e)[:100]}


def pmi_point(blob: Optional[dict]) -> Optional[dict]:
    pmi = (blob or {}).get("pmi") or {}
    if not pmi:
        return None
    keys = sorted(pmi)
    last = keys[-1]
    out = {"symbol": "PH_PMI", "label": "Manufacturing PMI (S&P Global)", "unit": "index", "kind": "rate", "as_of": f"{last}-01",
           "latest": pmi[last], "n_obs": len(keys), "note": "50 = no change; headline only, history builds from the calendar"}
    if len(keys) >= 2:
        out["prior"] = pmi[keys[-2]]
        out["change_since_prior"] = round(pmi[last] - pmi[keys[-2]], 2)
        out["direction"] = "up" if pmi[last] > pmi[keys[-2]] else "down" if pmi[last] < pmi[keys[-2]] else "flat"
    return out


def macro_block(blob: Optional[dict]) -> dict:
    import country_data

    out = {}
    for key, sym, label, unit, kind in MACRO:
        pt = country_data._macro_point(sym, kind=kind)
        if pt:
            pt.update({"label": label, "unit": unit, "kind": kind})
            out[key] = pt
    pm = pmi_point(blob)
    if pm:
        out["pmi"] = pm
    return out


def calendar_view(macro: dict, today, pmi_blob: Optional[dict], horizon_days: int = 35) -> dict:
    import country_calendar

    snap = country_calendar.read()
    loaded = {p["symbol"]: p["as_of"] for p in macro.values() if isinstance(p, dict) and p.get("symbol") and p.get("as_of")}
    evs = country_calendar.for_country(snap, "PH", today=today, loaded=loaded, all_kinds=True)
    pm = (pmi_blob or {}).get("pmi") or {}
    out = []
    for e in evs:
        if e["days_to_go"] > horizon_days:
            continue
        if e.get("kind") == "pmi" and e["days_to_go"] < 0:
            e["loaded"] = pmi_month(e.get("period"), e["date"]) in pm
        out.append(e)
    return {"asof": snap.get("at"), "events": out,
            "late": [f"{e['kind']} {e['date']}" for e in out if e.get("loaded") is False],
            "note": "TradingView's calendar looks about 31 days ahead; BSP meetings come from the bsp.gov.ph schedule"}


def bsp_meetings(today) -> dict:
    import release_calendar as rc

    dates = sorted(d for ds in rc._BSP.values() for d in ds)      # Monetary Board meetings (bsp.gov.ph schedule)
    up = [d for d in dates if d >= today.isoformat()]
    return {"next": up[0] if up else None, "upcoming": up[:3], "schedule_ends": dates[-1] if dates else None}


def bsp_note_problems(today, notes: list[dict]) -> list[dict]:
    """A Monetary Board meeting 2 to 14 days ago with no stored decision note (the decision-day task or a manual post is missing)."""
    import datetime as dt
    import release_calendar as rc

    out = []
    for d in sorted(x for ds in rc._BSP.values() for x in ds):
        age = (today - dt.date.fromisoformat(d)).days
        if 2 <= age <= 14 and not any(abs((dt.date.fromisoformat(n["date"]) - dt.date.fromisoformat(d)).days) <= 1 for n in notes):
            out.append({"check": "bsp_note", "detail": f"BSP Monetary Board met on {d} but no decision note is stored: run the decision-day task or POST /api/ph/bsp_notes"})
    return out


def age_days(iso: Optional[str], today) -> Optional[int]:
    import datetime as dt

    if not iso:
        return None
    try:
        return (today - dt.date.fromisoformat(iso[:10])).days
    except ValueError:
        return None


BSP_DECISIONS = ("hike", "cut", "hold")


def clean_bsp_notes(body, today=None) -> tuple[list[dict], dict]:
    """Validate POST /api/ph/bsp_notes: {"notes": [{date, decision, rate, change_bp, lines[], source_url}]}. Dates from 120 days back to tomorrow, rate 0-25,
    change in basis points within +-300, at most 3 lines of at most 160 characters, https source. Never raises on a bad row."""
    import datetime as dt
    import re

    today = today or dt.datetime.now(dt.timezone.utc).date()
    rep = {"received": 0, "kept": 0, "dropped": {}}

    def drop(why):
        rep["dropped"][why] = rep["dropped"].get(why, 0) + 1

    rows = body.get("notes") if isinstance(body, dict) else None
    if not isinstance(rows, list):
        return [], {**rep, "error": "body needs notes (list)"}
    rows = rows[:12]
    rep["received"] = len(rows)
    out = []
    for r in rows:
        if not isinstance(r, dict):
            drop("malformed")
            continue
        try:
            d = dt.date.fromisoformat(str(r.get("date"))[:10])
        except ValueError:
            drop("date")
            continue
        if not today - dt.timedelta(days=120) <= d <= today + dt.timedelta(days=1):
            drop("outside window")
            continue
        dec = str(r.get("decision", "")).lower()
        rate, bp = _f(r.get("rate")), _f(r.get("change_bp"))
        if dec not in BSP_DECISIONS or rate is None or not 0 <= rate <= 25 or bp is None or abs(bp) > 300:
            drop("decision/rate/change")
            continue
        lines = [str(x).strip()[:160] for x in (r.get("lines") or []) if str(x).strip()][:3]
        url = str(r.get("source_url") or "")
        out.append({"date": d.isoformat(), "decision": dec, "rate": round(rate, 3), "change_bp": int(bp), "lines": lines,
                    "source_url": url if re.fullmatch(r"https://[^\s\"'<>]{4,190}", url) else ""})
    rep["kept"] = len(out)
    return out, rep


def merge_bsp_notes(old: list[dict], new: list[dict]) -> list[dict]:
    by = {n["date"]: n for n in old}
    by.update({n["date"]: n for n in new})
    return sorted(by.values(), key=lambda n: n["date"], reverse=True)[:12]


def build_digest(resp: dict, edge: Optional[dict] = None) -> dict:
    """The morning read in about 1,500 tokens, so a model asking 'what is going on in PH' does not pull the whole page (about 30,000):
    freshness, macro and the next releases, movers and segments, who reported, buy-backs, insider and dividend news, material subjects,
    and COL and CTS in one line each. Built from the response itself, nothing new is read."""
    def row(r):
        # a price under PHP 1 moves in whole ticks: say so, so the read does not treat it as a segment signal
        return [r["s"], r["ret"], "under P1: tick-size noise"] if r["c"] < 1 else [r["s"], r["ret"]]

    def mv(h, n=5):
        L = resp["horizons"][h]["leaders"]
        return {"up": [row(r) for r in L["top"][:n]], "down": [row(r) for r in L["bottom"][:n]]}

    def macro_row(v):
        """Levels (bank lending, M2, remittances, reserves) as year-on-year % plus the level in trillions or billions, not raw pesos."""
        if v.get("kind") == "level":
            lvl, cur = v["latest"], ("US$" if v.get("unit") == "USD" else "P")
            txt = f"{cur}{lvl / 1e12:.2f}T" if lvl >= 1e12 else f"{cur}{lvl / 1e9:.2f}B"
            yoy = v.get("yoy_pct")
            return [v["label"], txt, None if yoy is None else f"{yoy:+.1f}% y/y", v["as_of"][:7]]
        return [v["label"], v["latest"], v.get("prior"), v["as_of"][:7]]

    def segs(h, n=3):
        sg = resp["horizons"][h]["segments_industry"]
        return {"best": [[g["name"], g["median"], g["n"]] for g in sg[:n]], "worst": [[g["name"], g["median"], g["n"]] for g in sg[-n:]]}

    ins = {}
    for m in resp["material"]:
        if m.get("insider"):
            k = (m["symbol"], m["insider"].get("name"))
            if k not in ins:
                ins[k] = [m["symbol"], m["insider"].get("name"), m["insider"]["side"], m["insider"]["net_shares"], m["announced"][:10]]
    extra = []
    for r in resp["scanner"]:
        if r.get("extra"):
            # the latest filing at any age (the material feed only holds 14 days, and these two file rarely)
            pool = (edge or {}).get("disclosures") or resp["material"]
            last = next((m for m in pool if m.get("symbol") == r["s"] and m.get("chip") != "other"), None)
            extra.append({"s": r["s"], "c": r["c"], "d": r.get("d"), "m": r.get("m"), "v30": r.get("v30"),
                          "last_filing": last and [last["announced"][:10], (last.get("subject") or last["title"])[:80]]})
    counts = {}
    for m in resp["material"]:
        counts[m["chip"]] = counts.get(m["chip"], 0) + 1
    h = resp["header"]
    return {
        "as_of": resp["as_of"], "freshness": {"prices_asof": resp["freshness"]["prices"]["asof"], "edge_built_at": resp["freshness"]["edge"]["built_at"]},
        "header": {"psei": h["psei"], "usdphp": h["usdphp"] and h["usdphp"].get("last"), "bsp_rate": h["policy"] and h["policy"]["latest"], "bsp_next": h["bsp"]["next"],
                   "regime": h["regime"], "ephe_in_regime": h["equity"] and {k: h["equity"].get(k) for k in ("avg_return_pct", "hit_rate", "occurrences")}},
        "macro": {k: macro_row(v) for k, v in resp["macro"].items()},
        "calendar_next": [[e["date"], e["kind"], e.get("previous"), e.get("forecast")] for e in resp["calendar"]["events"] if e["days_to_go"] >= 0][:6],
        "calendar_late": resp["calendar"]["late"],
        "movers": {"1D": mv("1D"), "1M": mv("1M")}, "segments_1M": segs("1M"), "segments_1D": segs("1D"),
        "reported": [[r["s"], r["period"], r["rev_yoy"], "loss" if r["ni_loss"] else "swing" if r["ni_swing"] else r["ni_yoy"], r["announced"][:10]] for r in resp["earnings"]["reported"][:8]],
        "expected_next": [[e["s"], e["date"]] for e in resp["earnings"]["next"][:8]],
        "buybacks_30d": [[b["s"], b["value_30d"], b["pct_outstanding_30d"], b["last_date"]] for b in resp["buybacks"][:5]],
        "insider": list(ins.values())[:8],
        "dividends": [[m["symbol"], m["dividend"]["per_share"], m["dividend"].get("record"),
                       "preferred" if "preferred" in (m.get("subject") or "").lower() else "common or not stated", (m.get("subject") or m["title"])[:60]]
                      for m in resp["material"] if m.get("dividend")][:6],
        "material_counts_14d": counts,
        "material_latest": [[m["symbol"], (m.get("subject") or m["title"])[:90], m["announced"][:10]] for m in resp["material"] if m["chip"] == "material"][:8],
        "extra_names": extra, "breadth": resp.get("breadth") and {k: resp["breadth"].get(k) for k in ("as_of", "colour", "net", "streak_days")},
        "bsp_last": (resp.get("bsp") or {}).get("notes", [None])[0] if (resp.get("bsp") or {}).get("notes") else None,
        "index_next": [[e["provider"], e["announce"] or e["effective"], e["event"][:40]] for e in resp.get("index", {}).get("calendar", []) if e["status"] != "done"][:4],
        "index_announced": [[e["provider"], e["date"], e["kind"], e["index"], e["symbols"][:8]] for e in resp.get("index", {}).get("events", [])][:6],
        "rebalance": {"weakest_members": [[x["s"], round(x["ffmc"] / 1e9, 1)] for x in resp["rebalance"]["weakest_members"][:3]],
                      "largest_non_members": [[x["s"], round(x["ffmc"] / 1e9, 1)] for x in resp["rebalance"]["nearest_non_members"][:3]]},
    }


def build_ph_response() -> dict:
    import datetime as dt

    import country_data
    import regime_matrix

    today = dt.datetime.now(dt.timezone.utc).date()
    shot = screener_blob()
    edge = read_blob("edge") or {}
    mblob = read_blob("macro")
    breadth = read_blob("breadth")
    rows = shot.get("rows", [])

    compass_q, grid_q = country_data.resolve_regime(None, None)
    matrix = regime_matrix.build_matrix(compass_q, grid_q)
    ph = next((c for c in matrix.get("countries", []) if c["code"] == "PH"), {})
    blocks = country_data.build_country_blocks(matrix.get("countries", []))
    block = blocks.get("PH") or {}
    macro = macro_block(mblob)
    rel = {"BSP": bsp_meetings(today)}
    hz = {name: {"leaders": leaderboard(rows, key), "segments_industry": segments(rows, key, "ind"),
                 "segments_sector": segments(rows, key, "sec")} for name, key in HORIZONS.items()}
    resp = {
        "schema_version": SCHEMA_VERSION,
        "as_of": today.isoformat(),
        "header": {"psei": shot.get("psei_index"), "usdphp": country_data._fx("USDPHP"), "regime": f"C{compass_q}G{grid_q}",
                   "compass_q": compass_q, "grid_q": grid_q, "policy": macro.get("policy"), "bsp": rel["BSP"],
                   "equity": ph.get("equity"), "currency": ph.get("currency"), "regime_ranking": ph.get("regime_ranking"),
                   "curve": block.get("curve"), "risk_premium": block.get("risk_premium"), "market": block.get("market")},
        "macro": macro,
        "calendar": calendar_view(macro, today, mblob),
        "breadth": breadth,
        "horizons": hz,
        "earnings": {"next": earnings_next(rows, edge, today), "reported": results_view(edge, rows, today)},
        "buybacks": buyback_board(edge, today),
        "material": material_feed(edge, today),
        "rebalance": rebalance_watch(rows),
        "scanner": [_row_view(r, "m") | {"mc": r.get("mc"), "v30": r.get("v30"), "fl": r.get("fl"), "extra": 1 if is_extra(r) else 0,
                                         "below_line": bool((r.get("v30") or 0) < LIQ_MIN)} for r in liquid(rows)],
        "freshness": {"prices": {"asof": shot.get("asof"), "age_days": age_days(shot.get("asof"), today), "n": len(rows),
                                   "n_liquid": len(liquid(rows))},
                      "edge": {"built_at": edge.get("built_at"), "age_days": age_days(edge.get("built_at"), today),
                               "last_run": edge.get("last_run")},
                      "breadth": {"asof": (breadth or {}).get("asof") or (breadth or {}).get("as_of"), },
                      "macro_pmi_months": len(((mblob or {}).get("pmi")) or {})},
        "digest": None,
        "caveats": [
            "Leaderboard, segments and scanner cover names trading at least PHP 5M a day (30-session average), plus COL and CTS by request.",
            "Earnings figures are read from the filings on PSE EDGE; the link opens the filing there. Descriptive, not a forecast.",
            "PSEi membership flags and rebalance ranks are a screen on public numbers, not PSE's index method.",
        ],
    }
    import ph_index

    resp["bsp"] = {"notes": (read_blob("bsp") or {}).get("notes", [])[:4], "next": rel["BSP"]["next"]}
    ix = read_blob("index") or {}
    resp["index"] = {"calendar": ph_index.calendar_view(today)[:14], "events": (ix.get("events") or [])[:40], "psei_members_as_of": ix.get("psei_members_as_of"),
                     "circular": ix.get("last_circular"), "note": "MSCI, FTSE and WisdomTree do not publish per-stock candidates, so there is no screen for them; "
                     "their Philippine changes appear here after each announcement"}
    resp["digest"] = build_digest(resp, edge)
    return resp


SCHEMA_VERSION = 6   # 6: one spelling per sector/subsector; 5: BSP notes; 4: digest units, preferred dividends, extra-name filings, penny marks; 3: 1D return, COL/CTS as list names (no pinned strip); 2: bars blob, expected_report helper
