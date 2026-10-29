"""
capex_study.py -- does S&P 500 capex growth (as KNOWN from filings on the day) or the funding gap tell us anything about the
next 1-3 months of the S&P 500 that CGI's regime and plain 20-day volatility do not? Offline; ships nothing.

Same machinery as research/erp_state (walk-forward OLS beyond the baseline, paired squared error, moving-block bootstrap).
Only the feature changes:

  g1   aggregate YoY growth of capex at the newest calendar quarter whose prior-year capex is >= 80% matched by filings
       that were on file 5+ days before the decision date (information date = FILING date, never quarter-end)
  acc  g1 minus the same figure for the quarter before (acceleration), also as known
  gap  funding gap = sum of trailing-4-quarter capex / sum of trailing-4-quarter operating cash flow, over companies with
       four consecutive quarters known and positive operating cash flow

Decision = each month end; entry = that month's last close; targets = SPX forward 1m / 3m return, 3m max drawdown, 3m vol.
BASELINE target ~ 1 + log(vol20) + compass dummies + grid dummies. CANDIDATE adds "bottom tercile" / "top tercile" dummies of
one feature (expanding terciles: cut-offs from past values only).
"""
from __future__ import annotations

import bisect
import datetime as dt
import json
import math
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "erp_state"))
import erp_study as S  # noqa: E402

LAG_DAYS = 5          # a filing counts as known only if filed this many days before the decision date
COVER = 0.80          # share of prior-year capex that must be matched for a quarter to count as "reported" (also for the prior quarter in acc)
MIN_GAP_COMPANIES = 150   # the funding gap needs at least this many companies with four consecutive known quarters
S.MIN_ERP_ROWS = 24   # months of feature history before terciles are used (pre-registered change: 36 in erp_state)
S.MIN_TRAIN = 24      # resolved training months before the first out-of-sample prediction (30 in erp_state)


# ── quarter keys ────────────────────────────────────────────────────────────

def q_shift(q: str, n: int) -> str:
    y, k = int(q[:4]), int(q[5])
    i = y * 4 + (k - 1) + n
    return f"{i // 4}Q{i % 4 + 1}"


def quarters_upto(date: str) -> list[str]:
    """Calendar quarters that could have been reported by `date`: quarter end + 20 days <= date, newest first (12 of them)."""
    d = dt.date.fromisoformat(date)
    out, y = [], d.year
    for yy in range(y, y - 4, -1):
        for k in (4, 3, 2, 1):
            end = dt.date(yy, k * 3, 30 if k in (2, 3) else 31)
            if end + dt.timedelta(days=20) <= d:
                out.append(f"{yy}Q{k}")
    return out[:12]


# ── as-known features ───────────────────────────────────────────────────────

def _known(c: dict, q: str, key: str, cutoff: str, filed_key: str = "filed1"):
    """Value of company c's quarter q AS FIRST REPORTED (cq1 / ocfq1), if first filed on or before `cutoff` (YYYY-MM-DD), else None.
    (The snapshot's cq / ocfq carry the latest restatement dated by the latest re-filing, a year late: not usable for this.)"""
    v = c.get(key, {}).get(q)
    f = c.get(filed_key, {}).get(q)
    if v is None or f is None or f > cutoff:
        return None
    return v


def growth_at(companies: list[dict], q: str, cutoff: str):
    """(aggregate YoY growth %, coverage of prior-year capex) for quarter q using only filings on file by cutoff."""
    p = q_shift(q, -4)
    base_all = base_m = delta = 0.0
    for c in companies:
        prior = _known(c, p, "cq1", cutoff)
        if prior is None or prior <= 0:
            continue
        base_all += prior
        now = _known(c, q, "cq1", cutoff)
        if now is None:
            continue
        base_m += prior
        delta += now - prior
    if base_m <= 0 or base_all <= 0:
        return None, 0.0
    return delta / base_m * 100, base_m / base_all


def features_at(companies: list[dict], decision_date: str) -> dict:
    """g1, acc, gap as known at decision_date (None where not computable)."""
    cutoff = (dt.date.fromisoformat(decision_date) - dt.timedelta(days=LAG_DAYS)).isoformat()
    reported = None
    for q in quarters_upto(decision_date):
        g, cov = growth_at(companies, q, cutoff)
        if g is not None and cov >= COVER:
            reported = q
            break
    out = {"g1": None, "acc": None, "gap": None, "q": reported, "cov": None}
    if reported is None:
        return out
    g1, cov = growth_at(companies, reported, cutoff)
    g0, cov0 = growth_at(companies, q_shift(reported, -1), cutoff)
    out.update({"g1": g1, "cov": cov, "acc": (g1 - g0) if (g0 is not None and cov0 >= COVER) else None})
    cap = ocf = 0.0
    n_gap = 0
    for c in companies:
        qs = [q_shift(reported, -i) for i in range(4)]
        cv = [_known(c, q, "cq1", cutoff) for q in qs]
        ov = [_known(c, q, "ocfq1", cutoff, "ofiled1") for q in qs]
        if any(v is None for v in cv) or any(v is None for v in ov):
            continue
        o = sum(ov)
        if o > 0:
            cap += sum(cv)
            ocf += o
            n_gap += 1
    if ocf > 0 and n_gap >= MIN_GAP_COMPANIES:
        out["gap"] = cap / ocf
    return out


# ── rows (as erp_study.build, with capex features) ──────────────────────────

def month_ends(spx_dates: list[str], first: str, last: str) -> list[str]:
    ends = {}
    for d in spx_dates:
        if first <= d <= last:
            ends[d[:7]] = d
    return [ends[m] for m in sorted(ends)]


def build(companies: list[dict], inp: dict, first="2012-09-01", last="2026-08-31") -> list[dict]:
    spx = inp["SPX"]
    dates = [x[0] for x in spx]
    p = np.array([x[1] for x in spx])
    n = len(p)
    ret = np.zeros(n)
    ret[1:] = p[1:] / p[:-1] - 1
    comp_d, comp_q = zip(*inp["compass_US"])
    grid_d, grid_q = zip(*inp["grid_US"])
    ends = month_ends(dates, first, last)
    feats = [features_at(companies, d) for d in ends]
    buckets = {k: S.expanding_terciles([f[k] for f in feats]) for k in ("g1", "acc", "gap")}
    rows = []
    for i, d in enumerate(ends):
        e = bisect.bisect_left(dates, d)
        if e < 25:
            continue
        ci, gi = bisect.bisect_right(comp_d, dates[e]) - 1, bisect.bisect_right(grid_d, dates[e]) - 1
        if ci < 0 or gi < 0:
            continue
        r = {"month": d[:7], "date": d, "e": e, "vol20": float(ret[e - 19:e + 1].std(ddof=1) * math.sqrt(252)) or 1e-6,
             "comp": comp_q[ci], "grid": grid_q[gi], "r1": None, "r3": None, "dd": None, "v3": None,
             "q": feats[i]["q"], "cov": feats[i]["cov"], "g1": feats[i]["g1"], "acc": feats[i]["acc"], "gap": feats[i]["gap"],
             "b_g1": buckets["g1"][i], "b_acc": buckets["acc"][i], "b_gap": buckets["gap"][i]}
        if e + S.H1 < n:
            r["r1"] = float(p[e + S.H1] / p[e] - 1) * 100
        if e + S.H3 < n:
            path = p[e:e + S.H3 + 1] / p[e]
            r["r3"] = float(path[-1] - 1) * 100
            r["dd"] = float((1 - path / np.maximum.accumulate(path)).max()) * 100
            r["v3"] = float(ret[e + 1:e + S.H3 + 1].std(ddof=1) * math.sqrt(252)) * 100
        rows.append(r)
    return rows
