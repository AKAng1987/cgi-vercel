"""
erp_data.py -- Damodaran's implied equity risk premium: keep it current, and build the gauge for the CGI tab.

Two jobs, both descriptive. Nothing here forecasts and nothing feeds the regime logic.

SYNC   sync_if_due() runs from /api/freshness (the refresh routine reads that page every morning). At most once a
       day it downloads Damodaran's two workbooks (~100 KB), and appends any month or year we do not hold through
       series_write.append, which has the range / no-future / append-only guards. Nothing to schedule.
GAUGE  build_erp_block() reads the stored series and returns the numbers the CGI Context section shows:
       the ERP, the 10-year T-bond rate he subtracts, their gap, where today sits in the 2008-on monthly history,
       the last time the premium was this thin (annual file, back to 1961), and the high-yield credit spread
       beside it. Source credit and the label travel with the payload.

Source: Aswath Damodaran, NYU Stern, https://pages.stern.nyu.edu/~adamodar/ (implied ERP, monthly and annual).
"""
from __future__ import annotations

import datetime as dt
import logging
import time
import urllib.request
from decimal import Decimal

import boto3

import cache
import erp_parse
import series_write

REGION = "ap-southeast-1"
PRICE_TABLE = "cmon-stage-backend-price-history"
_ddb = boto3.client("dynamodb", region_name=REGION)
_logger = logging.getLogger(__name__)
LABEL = "Valuation cushion, descriptive, not a forecast"
SOURCE = "Aswath Damodaran, NYU Stern (pages.stern.nyu.edu/~adamodar): implied equity risk premium"
_last_failed_at = 0.0
RETRY_AFTER_FAIL_S = 1800


# ── storage reads ─────────────────────────────────────────────────────────

def _series(symbol: str) -> list[tuple[str, float]]:
    out, key = [], None
    while True:
        kw = dict(TableName=PRICE_TABLE, KeyConditionExpression="symbol = :s",
                  ExpressionAttributeValues={":s": {"S": symbol}}, ProjectionExpression="#d, #c",
                  ExpressionAttributeNames={"#d": "date", "#c": "close"})
        if key:
            kw["ExclusiveStartKey"] = key
        r = _ddb.query(**kw)
        out += [(i["date"]["S"], float(Decimal(i["close"]["N"]))) for i in r.get("Items", [])]
        key = r.get("LastEvaluatedKey")
        if not key:
            return sorted(out)


# ── sync ──────────────────────────────────────────────────────────────────

def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (cgi erp sync)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read(erp_parse.MAX_BYTES + 1)


def sync() -> dict:
    """Download both workbooks and append whatever is new. Raises on a network or layout problem."""
    monthly = erp_parse.parse_monthly(_download(erp_parse.MONTHLY_URL))
    annual = erp_parse.parse_annual(_download(erp_parse.ANNUAL_URL))
    written: dict[str, int] = {}
    for sym, rows in {**monthly, **annual}.items():
        if sym not in series_write.ALLOWED_EXTERNAL:
            continue
        have = series_write._last_date(sym)
        new = [(d, v) for d, v in rows if have is None or d > have]
        for i in range(0, len(new), series_write.MAX_ROWS):
            series_write.append(sym, [{"date": d, "value": v} for d, v in new[i:i + series_write.MAX_ROWS]])
        if new:
            written[sym] = len(new)
    return {"ok": True, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "written": written,
            "monthly_through": monthly["ERP_T12M"][-1][0]}


def sync_if_due() -> dict:
    """At most one real sync per day; a failure is reported and retried after 30 minutes, never raised."""
    global _last_failed_at
    done = cache.get("erp_sync")
    if done is not None:
        return done
    if time.time() - _last_failed_at < RETRY_AFTER_FAIL_S:
        return {"ok": False, "error": "recent failure; waiting before retrying"}
    try:
        res = sync()
    except Exception as exc:  # noqa: BLE001 -- additive; must never break the page that calls it
        _last_failed_at = time.time()
        _logger.exception("[erp] sync failed")
        return {"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    cache.set("erp_sync", res)
    return res


# ── the gauge ─────────────────────────────────────────────────────────────

def _pct_le(vals: list[float], x: float) -> float:
    return round(100.0 * sum(v <= x for v in vals) / len(vals), 1)


def _pct_ge(vals: list[float], x: float) -> float:
    return round(100.0 * sum(v >= x for v in vals) / len(vals), 1)


def expected_month(today: dt.date) -> str:
    """He posts a month's row in its first week. By the 12th we expect the current month; before that, the last."""
    first = today.replace(day=1)
    if today.day >= 12:
        return first.isoformat()
    return (first - dt.timedelta(days=1)).replace(day=1).isoformat()


def status(today: dt.date | None = None) -> dict:
    """What /api/freshness reports: the newest month we hold against the one we should hold by now."""
    t = today or dt.date.today()
    held = series_write._last_date("ERP_T12M")
    exp = expected_month(t)
    return {"newest_month": held, "expected_month": exp, "behind": bool(held is None or held < exp)}


def _hy_by_month(months: list[str]) -> dict[str, float]:
    """High-yield spread (bp), taken on the first trading day on/after each month start. Empty if unavailable."""
    try:
        import macro_data
        recs = cache.get_or_fetch("spreads", macro_data.fetch_spreads)
    except Exception:  # noqa: BLE001 -- additive
        return {}
    hy = {r["date"]: r["HY_Spread"] for r in recs if r.get("HY_Spread") is not None}
    days = sorted(hy)
    out = {}
    for m in months:
        nxt = next((d for d in days if d >= m), None)
        if nxt and (dt.date.fromisoformat(nxt) - dt.date.fromisoformat(m)).days <= 8:
            out[m] = float(hy[nxt])
    return out


def build_erp_block() -> dict:
    erp = _series("ERP_T12M")
    tb = dict(_series("ERP_TBOND"))
    if not erp:
        return {"available": False, "label": LABEL, "source": SOURCE, "why": "no ERP rows stored yet"}
    ann_erp, ann_tb = _series("ERP_ANNUAL"), dict(_series("ERP_ANNUAL_TBOND"))
    exp_ret, growth = dict(_series("ERP_EXPECTED_RET")), dict(_series("ERP_GROWTH"))

    months = [(d, v, tb[d]) for d, v in erp if d in tb]          # (date, erp, tbond) both present
    gap = [e - b for _d, e, b in months]
    d_now, e_now, b_now = months[-1]
    g_now = e_now - b_now
    erps = [e for _d, e, _b in months]

    # the last time the premium was this thin, looking back through the annual (year-end) figures too
    last_this_low = None
    prior = [(d, v) for d, v in ann_erp if d < months[0][0]] + [(d, v) for d, v, _b in months[:-1]]
    for d, v in reversed(sorted(prior)):
        if v <= e_now:
            last_this_low = {"date": d, "erp": v, "basis": "monthly" if d >= months[0][0] else "annual year-end"}
            break

    hy_m = _hy_by_month([d for d, _e, _b in months])
    hy_now = None
    if hy_m:
        try:
            import macro_data
            recs = cache.get_or_fetch("spreads", macro_data.fetch_spreads)
            latest = [r for r in recs if r.get("HY_Spread") is not None][-1]
            hv = list(hy_m.values())
            hy_now = {"bp": round(float(latest["HY_Spread"]), 1), "as_of": latest["date"],
                      "percentile_since_2008": _pct_le(hv, float(latest["HY_Spread"])), "n": len(hv)}
        except Exception:  # noqa: BLE001 -- additive
            hy_now = None

    low_since = min(months, key=lambda m: m[1])
    high_since = max(months, key=lambda m: m[1])
    p_low, p_high = _pct_le(erps, e_now), _pct_ge(erps, e_now)
    band = "bottom10" if p_low <= 10.0 else "top10" if p_high <= 10.0 else "middle"
    dot = next(((d, v) for d, v in ann_erp if d.startswith("1999")), None)
    dot_tb = ann_tb.get(dot[0]) if dot else None

    return {
        "available": True, "label": LABEL, "source": SOURCE, "as_of": d_now,
        "current": {"date": d_now, "erp": round(e_now, 2), "tbond": round(b_now, 2), "gap": round(g_now, 2),
                    "expected_return": exp_ret.get(d_now), "expected_growth": growth.get(d_now)},
        "since_2008": {
            "n_months": len(months), "first": months[0][0],
            "erp_rank_lowest": 1 + sum(v < e_now for v in erps), "erp_pct_le": p_low, "erp_pct_ge": p_high,
            "gap_pct_le": _pct_le(gap, g_now), "band": band,
            "median_erp": round(sorted(erps)[len(erps) // 2], 2),
            "low": {"date": low_since[0], "erp": low_since[1]}, "high": {"date": high_since[0], "erp": high_since[1]},
        },
        "last_this_low": last_this_low,
        "dotcom_1999": ({"erp": dot[1], "tbond": dot_tb, "gap": round(dot[1] - dot_tb, 2) if dot_tb is not None else None}
                        if dot else None),
        "hy_spread": hy_now,
        "history": {"annual": [{"d": d, "erp": v, "tbond": ann_tb.get(d)} for d, v in ann_erp if d < months[0][0]],
                    "monthly": [{"d": d, "erp": round(e, 2), "tbond": round(b, 2)} for d, e, b in months]},
        "freshness": status(),
        "caveats": [
            "Descriptive: it says how stocks are priced against the T-bond, not what they will earn.",
            "The ERP moves with the price of stocks, the T-bond rate and analysts' cash-flow forecasts, so part of it "
            "is the same information as price.",
            "1961 to 2007 are annual year-end estimates and 2008 on are monthly start-of-month estimates; "
            "the two files use slightly different methods.",
        ],
    }
