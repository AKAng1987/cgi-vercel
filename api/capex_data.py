"""
capex_data.py — S&P 500 capital expenditure by sector, from SEC filings.

The question (Capital Flows / Bloomberg chart, 2026-10): how much of the
year-over-year growth in S&P 500 capex does each sector account for, and who is
spending more than they generate. Descriptive only: it says what was spent, not
what happens next, and it is published 4-6 weeks after each quarter ends.

    contribution(sector, q) = (capex(sector, q) - capex(sector, q-4))
                              / capex(all, q-4) * 100          [points]

so the sectors add up to the total YoY growth of the matched sample.

Two halves, kept apart on purpose:

  build_snapshot()    reads ~500 SEC companyfacts payloads (3-8MB each). Far too
                      heavy for a request on Render, so it runs offline
                      (~/market-dashboard/scripts/capex_build.py) and writes ONE
                      compact JSON to S3. Re-run each earnings season.
  build_capex_response()  reads that snapshot and does arithmetic only.

Universe: the eleven Select Sector SPDR funds, which together hold the S&P 500
and carry the GICS sector in the fund's name. Today's membership is applied to
all of history (survivorship), so early quarters will not match Bloomberg's
exactly; the page says so.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import sec_xbrl as sx

_logger = logging.getLogger("cgi_api.capex")

SCHEMA_VERSION = 6   # 6: response carries `flow` (spender capex vs receiver revenue growth); 5: rq1/rfiled1 (revenue as first reported, for the capex_flow study); 4: ofiled1 (OCF's own first-filed dates); 3: rows also carry as-first-reported capex/OCF and first-filed dates (cq1, ocfq1, filed1) for the capex_state study; 2: ocfq
KEY = "capex/capex_quarterly.json"          # under cache.PREFIX
FIRST_QUARTER = "2011Q1"                    # stored; YoY therefore exists from 2012Q1 (XBRL cash-flow facts begin ~2009)
SHOW_FROM = "2022Q1"                        # first quarter drawn (matches the chart)
PARTIAL_BELOW = 0.90                        # share of prior-year capex matched

SECTOR_ETFS = {
    "XLC": "Communication Services", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
    "XLE": "Energy", "XLF": "Financials", "XLV": "Health Care", "XLI": "Industrials",
    "XLK": "Information Technology", "XLB": "Materials", "XLRE": "Real Estate", "XLU": "Utilities",
}
SECTORS = list(SECTOR_ETFS.values())


# ── quarter keys ────────────────────────────────────────────────────────────

def cal_quarter(end: str) -> str:
    """Fiscal period end -> the calendar quarter it is nearest to ("2026Q2").

    NVDA's quarter ending 26 Jul sits 26 days after 30 Jun and 66 before 30 Sep,
    so it is calendar Q2; a 52-week retailer ending 3 Jan is the prior Q4.
    """
    d = dt.date.fromisoformat(end)
    best = None
    for y in (d.year - 1, d.year, d.year + 1):
        for m, dd in ((3, 31), (6, 30), (9, 30), (12, 31)):
            q = dt.date(y, m, dd)
            gap = abs((d - q).days)
            if best is None or gap < best[0]:
                best = (gap, y, m // 3)
    return f"{best[1]}Q{best[2]}"


def q_shift(q: str, n: int) -> str:
    y, k = int(q[:4]), int(q[5])
    i = y * 4 + (k - 1) + n
    return f"{i // 4}Q{i % 4 + 1}"


def q_range(a: str, b: str) -> list[str]:
    out, q = [], a
    while q <= b:
        out.append(q)
        q = q_shift(q, 1)
    return out


# ── one company ─────────────────────────────────────────────────────────────

def _by_cal_quarter(s: dict[str, tuple[float, str]]) -> dict[str, tuple[float, str]]:
    out: dict[str, tuple[float, str]] = {}
    for end in sorted(s):
        out[cal_quarter(end)] = s[end]            # a later period end wins a collision
    return out


def _ttm(q: dict[str, float]) -> Optional[float]:
    """Sum of the latest four CONSECUTIVE calendar quarters, else None."""
    if not q:
        return None
    last = max(q)
    keys = [q_shift(last, -i) for i in range(4)]
    return sum(q[k] for k in keys) if all(k in q for k in keys) else None


def company_record(ticker: str, sector: str) -> Optional[dict]:
    f = sx.company_facts(ticker)
    if f is None:
        return None
    cap = _by_cal_quarter(sx.cash_quarters(f, ("capex", "capex_alt")))
    ocf = _by_cal_quarter(sx.cash_quarters(f, ("op_cash_flow",)))
    rev = sx.series(f, "revenue")
    rev_q = {cal_quarter(e): v for e, v in rev.items()}
    cap1 = _by_cal_quarter(sx.cash_quarters_first(f, ("capex", "capex_alt")))
    rev1 = _by_cal_quarter(sx.cash_quarters_first(f, ("revenue",)))   # income-statement windows difference the same way
    ocf1 = _by_cal_quarter(sx.cash_quarters_first(f, ("op_cash_flow",)))
    cq = {q: round(v[0] / 1e6, 1) for q, v in cap.items() if q >= FIRST_QUARTER}
    filed = {q: v[1] for q, v in cap.items() if q >= FIRST_QUARTER}
    return {
        "t": ticker, "cik": f.get("cik"), "name": f.get("entityName"), "sector": sector,
        "cq": cq, "filed": filed,
        "ocfq": {q: round(v[0] / 1e6, 1) for q, v in ocf.items() if q >= FIRST_QUARTER},
        # as first reported, dated by FIRST filing: what was knowable on a given day (point-in-time studies)
        "cq1": {q: round(v[0] / 1e6, 1) for q, v in cap1.items() if q >= FIRST_QUARTER},
        "filed1": {q: v[1] for q, v in cap1.items() if q >= FIRST_QUARTER},
        "ocfq1": {q: round(v[0] / 1e6, 1) for q, v in ocf1.items() if q >= FIRST_QUARTER},
        "ofiled1": {q: v[1] for q, v in ocf1.items() if q >= FIRST_QUARTER},
        "rq1": {q: round(v[0] / 1e6, 1) for q, v in rev1.items() if q >= FIRST_QUARTER},      # revenue, first reported
        "rfiled1": {q: v[1] for q, v in rev1.items() if q >= FIRST_QUARTER},   # OCF's OWN first-filed dates (can be later than capex's)
        "ocf_ttm": _round_m(_ttm({q: v[0] for q, v in ocf.items()})),
        "rev_ttm": _round_m(_ttm(rev_q)),
    }


def _round_m(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(v / 1e6, 1)


# ── the universe and the snapshot ───────────────────────────────────────────

def universe() -> list[dict]:
    """[{ticker, sector}] from the sector SPDR holdings, one row per company.

    GOOG and GOOGL are one issuer; they are collapsed on CIK so Alphabet's
    capex is counted once.
    """
    import etf_holdings as eh

    seen_cik: dict[int, str] = {}
    out: list[dict] = []
    ciks = sx.cik_map()
    for etf, sector in SECTOR_ETFS.items():
        h = eh._from_ssga(etf)
        if not h:
            raise RuntimeError(f"no holdings for {etf}")
        for x in h["holdings"]:
            tk = x["ticker"].upper().replace(".", "-")
            cik = ciks.get(tk) or ciks.get(x["ticker"].upper())
            if cik is None or cik in seen_cik:
                continue
            seen_cik[cik] = tk
            out.append({"ticker": tk if tk in ciks else x["ticker"].upper(), "sector": sector})
    return out


class _Pace:
    """SEC allows 10 requests a second; stay well under it across threads."""

    def __init__(self, gap: float = 0.15):
        self.gap, self.next, self.lock = gap, 0.0, threading.Lock()

    def wait(self) -> None:
        with self.lock:
            now = time.monotonic()
            start = max(now, self.next)
            self.next = start + self.gap
        if start > now:
            time.sleep(start - now)


def build_snapshot(tickers: Optional[list[dict]] = None, workers: int = 4,
                   log: Callable[[str], None] = print) -> dict:
    uni = tickers if tickers is not None else universe()
    pace = _Pace()
    missing: list[str] = []

    def one(u: dict) -> Optional[dict]:
        pace.wait()
        try:
            return company_record(u["ticker"], u["sector"])
        except Exception as e:                   # one name must not sink the run
            _logger.warning("[capex] %s -> %s", u["ticker"], e)
            return None

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i, (u, r) in enumerate(zip(uni, ex.map(one, uni)), 1):
            if r is None:
                missing.append(u["ticker"])
            else:
                rows.append(r)
            if i % 50 == 0:
                log(f"  {i}/{len(uni)}")
    return {"built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "n_universe": len(uni), "failed": missing, "companies": rows}


def write_snapshot(snap: dict) -> None:
    import cache

    cache._s3.put_object(Bucket=cache.BUCKET, Key=cache.PREFIX + KEY,
                         Body=json.dumps(snap, separators=(",", ":")).encode("utf-8"),
                         ContentType="application/json")


def read_snapshot() -> Optional[dict]:
    import cache

    try:
        obj = cache._s3.get_object(Bucket=cache.BUCKET, Key=cache.PREFIX + KEY)
        return json.loads(obj["Body"].read())
    except Exception as e:
        _logger.warning("[capex] snapshot unavailable: %s", e)
        return None


# ── arithmetic on a snapshot (pure; this is what the check script tests) ───

def contributions(companies: list[dict], quarters: list[str]) -> list[dict]:
    """Per quarter: total YoY growth, sector contributions (points), coverage.

    Only companies with capex in BOTH q and q-4 enter either side, so the
    sectors add up to the total growth of that matched sample. `coverage` is
    the matched share of ALL prior-year capex in the quarter, so a quarter in
    which most spenders have not yet filed shows as partial instead of as a
    small, confident number.
    """
    out = []
    for q in quarters:
        p = q_shift(q, -4)
        base_all = 0.0
        base_m = 0.0
        delta = {s: 0.0 for s in SECTORS}
        n_all = n_m = 0
        for c in companies:
            prior = c["cq"].get(p)
            if prior is None:
                continue
            base_all += prior
            n_all += 1
            now = c["cq"].get(q)
            if now is None:
                continue
            base_m += prior
            n_m += 1
            delta[c["sector"]] += now - prior
        if base_m <= 0:
            out.append({"q": q, "total_yoy_pct": None, "contrib": {}, "coverage": 0.0,
                        "partial": True, "n_matched": n_m, "n_prior": n_all})
            continue
        contrib = {s: round(delta[s] / base_m * 100, 2) for s in SECTORS}
        cov = base_m / base_all if base_all else 0.0
        out.append({"q": q, "total_yoy_pct": round(sum(delta.values()) / base_m * 100, 2),
                    "contrib": contrib, "coverage": round(cov, 3), "partial": cov < PARTIAL_BELOW,
                    "n_matched": n_m, "n_prior": n_all,
                    "total_capex_usd_b": round(sum(c["cq"].get(q, 0.0) for c in companies if q in c["cq"]) / 1000, 1)})
    return out


def spenders(companies: list[dict], n: int = 10) -> dict:
    """Top spenders by trailing-twelve-month capex, with funding and intensity."""
    rows = []
    for c in companies:
        ttm = _ttm(c["cq"])
        if ttm is None:
            continue
        last = max(c["cq"])
        yoy = None
        if q_shift(last, -4) in c["cq"] and c["cq"][q_shift(last, -4)] > 0:
            yoy = round((c["cq"][last] / c["cq"][q_shift(last, -4)] - 1) * 100, 1)
        ocf, rev = c.get("ocf_ttm"), c.get("rev_ttm")
        rows.append({
            "ticker": c["t"], "name": c.get("name"), "sector": c["sector"], "last_q": last,
            "capex_ttm_b": round(ttm / 1000, 1), "capex_last_q_b": round(c["cq"][last] / 1000, 2),
            "yoy_pct": yoy,
            "capex_to_ocf": round(ttm / ocf, 2) if ocf and ocf > 0 else None,
            "capex_to_revenue": round(ttm / rev, 2) if rev and rev > 0 else None,
            "outspends_cash_flow": (ttm > ocf) if ocf is not None else None,
        })
    rows.sort(key=lambda r: -r["capex_ttm_b"])
    total = sum(r["capex_ttm_b"] for r in rows)
    top = rows[:n]
    return {"top": top, "top5_share_pct": round(sum(r["capex_ttm_b"] for r in rows[:5]) / total * 100, 1) if total else None,
            "n_with_ttm": len(rows), "ttm_total_b": round(total, 1)}


# ── where the money goes: spender capex growth beside receivers' revenue growth ──────────────────────────
# Same definitions as research/capex_flow (first-reported values, first-filed dates). Descriptive.
SPENDERS = ("AMZN", "MSFT", "GOOGL", "META", "ORCL")
# kept in step with fundamentals_data.AI_LAYERS (energy, chips, infrastructure); scripts/check_capex.py compares them
AI_RECEIVERS = {"energy": ("VST", "CEG", "NRG", "ETN"), "chips": ("NVDA", "AMD", "AVGO", "MU"),
                "infrastructure": ("VRT", "ANET", "DLR", "SMCI")}
FLOW_SECTORS = ("Industrials", "Utilities", "Materials")
FLOW_MIN_SHARE = 0.75


def _yoy(members: list[dict], q: str, key: str, min_share: float) -> Optional[float]:
    p = q_shift(q, -4)
    now = prior = 0.0
    n = 0
    for c in members:
        a, b = c.get(key, {}).get(q), c.get(key, {}).get(p)
        if a is None or b is None or b <= 0:
            continue
        now += a
        prior += b
        n += 1
    if not members or prior <= 0 or n < max(1, -(-int(min_share * 100 * len(members)) // 100)):
        return None
    return round((now / prior - 1) * 100, 1)


def flow_view(companies: list[dict], newest: str) -> dict:
    by = {c["t"]: c for c in companies}
    spend = [by[t] for t in SPENDERS if t in by]
    groups = {"AI receivers (12)": [by[t] for layer in AI_RECEIVERS.values() for t in layer if t in by]}
    for sec in FLOW_SECTORS:
        groups[sec] = [c for c in companies if c.get("sector") == sec and c["t"] not in SPENDERS]
    qs = q_range(SHOW_FROM, newest)
    series, corr = {}, {}
    for name, members in groups.items():
        rows = []
        for q in qs:
            rows.append({"q": q, "revenue_yoy": _yoy(members, q, "rq1", FLOW_MIN_SHARE),
                         "spender_capex_yoy": _yoy(spend, q, "cq1", 1.0)})
        series[name] = rows
        # whole-sample, overlapping, descriptive: capex growth k quarters earlier vs revenue growth now
        full = {r["q"]: r for r in [{"q": q, "r": _yoy(members, q, "rq1", FLOW_MIN_SHARE), "g": _yoy(spend, q, "cq1", 1.0)}
                                      for q in q_range("2013Q1", newest)]}
        c = {}
        for k in range(0, 5):
            pairs = [(full[q_shift(q, -k)]["g"], full[q]["r"]) for q in full
                     if q_shift(q, -k) in full and full[q]["r"] is not None and full[q_shift(q, -k)]["g"] is not None]
            if len(pairs) > 6:
                xs, ys = zip(*pairs)
                mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
                sxx = sum((x - mx) ** 2 for x in xs)
                syy = sum((y - my) ** 2 for y in ys)
                sxy = sum((x - mx) * (y - my) for x, y in pairs)
                c[str(k)] = {"n": len(pairs), "corr": round(sxy / (sxx * syy) ** 0.5, 2) if sxx > 0 and syy > 0 else None}
        corr[name] = c
    return {"series": series, "lead_lag": corr, "spenders": [c["t"] for c in spend],
            "members": {k: [c["t"] for c in v] for k, v in groups.items() if k.startswith("AI")}}


# ── the response ────────────────────────────────────────────────────────────

CAVEAT = ("Capex is cash paid for property, plant and equipment as filed with the SEC (finance leases and "
          "acquired data-centre capacity are not included). Sector = GICS, from the Select Sector SPDR funds; "
          "today's S&P 500 members are applied to all history, so early quarters differ from Bloomberg's. "
          "Companies that do not report capex (many banks and insurers) are left out of both sides. "
          "Each quarter is the fiscal quarter nearest that calendar quarter. Filings arrive 4-6 weeks after "
          "quarter-end, so the newest quarter is partial until most spenders have reported. "
          "Descriptive: it says what was spent, not what happens next.")


def build_capex_response() -> dict:
    snap = read_snapshot()
    if not snap or not snap.get("companies"):
        return {"available": False, "reason": "capex snapshot not built yet", "caveat": CAVEAT}
    comps = snap["companies"]
    newest = max((max(c["cq"]) for c in comps if c["cq"]), default=None)
    if newest is None:
        return {"available": False, "reason": "snapshot has no capex rows", "caveat": CAVEAT}
    quarters = q_range(SHOW_FROM, newest)
    rows = contributions(comps, quarters)
    return {
        "available": True, "schema": SCHEMA_VERSION, "built_at": snap.get("built_at"),
        "sectors": SECTORS, "newest_quarter": newest,
        "n_companies": len(comps), "n_reporting_capex": sum(1 for c in comps if c["cq"]),
        "n_failed": len(snap.get("failed", [])),
        "quarters": rows, "spenders": spenders(comps),
        "flow": flow_view(comps, newest),
        "caveat": CAVEAT,
    }
