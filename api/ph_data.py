"""Philippines tab: storage of the three PH snapshots and (below) the response the page reads.

Nothing here calls TradingView (it is reachable only through a model); the daily builders run unattended from launchd.
Snapshots live in the same S3 folder as the other offline-built blobs (cache.PREFIX + "ph/<name>.json"):
  edge      built by ~/market-dashboard/scripts/ph_edge_build.py from PSE EDGE (disclosures, results, buy-backs)
  screener  built by ~/market-dashboard/scripts/ph_prices_build.py from EDGE's own daily bars (open/high/low/close/value traded)
            plus PSEi from Yahoo: returns, EMAs, 3-month range, 30-day average value traded, float and market cap
  breadth   exported from Pulse (export_ph_breadth.py)
  macro     PMI history, appended from the calendar's actuals (S&P Global PMI has no ECONOMICS series)
EDGE's terms forbid storing or redistributing its data without PSE's consent: `edge` holds only titles, dates, the few
figures the page shows and the link number back to the filing, never a copy of a filing.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

_logger = logging.getLogger("cgi_api.ph")
NAMES = ("edge", "screener", "breadth", "macro")


def _key(name: str) -> str:
    import cache

    if name not in NAMES:
        raise ValueError(f"unknown PH snapshot {name!r}")
    return cache.PREFIX + f"ph/{name}.json"


def write_blob(name: str, obj: dict) -> None:
    import cache

    cache._s3.put_object(Bucket=cache.BUCKET, Key=_key(name), Body=json.dumps(obj, separators=(",", ":")).encode("utf-8"),
                         ContentType="application/json")


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
HORIZONS = {"1W": "w", "1M": "m", "3M": "q", "YTD": "y"}


def _f(v) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) < 1e16 else None


# ── views (pure) ─────────────────────────────────────────────────────────────

def liquid(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("c") and (r.get("v30") or 0) >= LIQ_MIN]


def _vs(c, e):
    return round((c / e - 1) * 100, 1) if c and e else None


def _row_view(r: dict, key: str) -> dict:
    return {"s": r["s"], "ret": r.get(key), "c": r["c"], "vs50": _vs(r["c"], r.get("e50")), "vs200": _vs(r["c"], r.get("e200")),
            "vt": r.get("vt"), "ind": r.get("ind"), "sec": r.get("sec"), "psei": r.get("psei", 0),
            "from_high3m": _vs(r["c"], r.get("h3")), "w": r.get("w"), "m": r.get("m"), "q": r.get("q"), "y": r.get("y")}


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


def earnings_next(rows: list[dict], edge: dict, today, days: int = 35) -> list[dict]:
    """Expected reporting dates for liquid names. EDGE publishes no calendar, so the estimate is last year's filing date for the
    same report plus 365 days (companies file within a few days of the same date each year); names that already filed this
    quarter are left out. Labelled as an estimate on the page."""
    import datetime as dt

    hist = edge.get("filing_dates", {})
    res_latest = {}
    for r in edge.get("results", []):
        res_latest[r["symbol"]] = max(res_latest.get(r["symbol"], ""), r["announced"][:10])
    end = today + dt.timedelta(days=days)
    out = []
    for r in liquid(rows):
        dates = sorted(hist.get(r["s"], []))
        last = max(res_latest.get(r["s"], ""), dates[-1] if dates else "")
        if last and (today - dt.date.fromisoformat(last)).days < 45:
            continue                                       # already reported this season
        # a year-ago filing inside the window [today - 365, end - 365]; the earliest one still ahead of us
        cands = []
        for d in dates:
            est = dt.date.fromisoformat(d) + dt.timedelta(days=365)
            while est.weekday() >= 5:
                est += dt.timedelta(days=1)
            if today <= est <= end:
                cands.append((est, d))
        if cands:
            est, basis = min(cands)
            out.append({"s": r["s"], "date": est.isoformat(), "basis": f"filed {basis} last year", "mc": r.get("mc"),
                        "psei": r.get("psei", 0), "ind": r.get("ind")})
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


def age_days(iso: Optional[str], today) -> Optional[int]:
    import datetime as dt

    if not iso:
        return None
    try:
        return (today - dt.date.fromisoformat(iso[:10])).days
    except ValueError:
        return None


def build_ph_response() -> dict:
    import datetime as dt

    import country_data
    import regime_matrix

    today = dt.datetime.now(dt.timezone.utc).date()
    shot = read_blob("screener") or {}
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
    return {
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
        "scanner": [_row_view(r, "m") | {"mc": r.get("mc"), "v30": r.get("v30"), "fl": r.get("fl")} for r in liquid(rows)],
        "freshness": {"prices": {"asof": shot.get("asof"), "age_days": age_days(shot.get("asof"), today), "n": len(rows),
                                   "n_liquid": len(liquid(rows))},
                      "edge": {"built_at": edge.get("built_at"), "age_days": age_days(edge.get("built_at"), today),
                               "last_run": edge.get("last_run")},
                      "breadth": {"asof": (breadth or {}).get("asof") or (breadth or {}).get("as_of"), },
                      "macro_pmi_months": len(((mblob or {}).get("pmi")) or {})},
        "caveats": [
            "Leaderboard and segments cover liquid names only (close x 30-day average volume >= PHP 5M a day).",
            "Earnings figures are read from the filings on PSE EDGE; the link opens the filing there. Descriptive, not a forecast.",
            "PSEi membership flags and rebalance ranks are a screen on public numbers, not PSE's index method.",
        ],
    }


SCHEMA_VERSION = 1
