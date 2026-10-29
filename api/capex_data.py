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

SCHEMA_VERSION = 1
KEY = "capex/capex_quarterly.json"          # under cache.PREFIX
FIRST_QUARTER = "2018Q1"                    # stored; YoY therefore exists from 2019Q1
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
    cq = {q: round(v[0] / 1e6, 1) for q, v in cap.items() if q >= FIRST_QUARTER}
    filed = {q: v[1] for q, v in cap.items() if q >= FIRST_QUARTER}
    return {
        "t": ticker, "cik": f.get("cik"), "name": f.get("entityName"), "sector": sector,
        "cq": cq, "filed": filed,
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
        "caveat": CAVEAT,
    }
