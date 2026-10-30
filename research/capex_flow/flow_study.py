"""
flow_study.py -- does the hyperscalers' capex show up in their suppliers' revenue, and does knowing it help forecast that revenue?

SPENDERS  AMZN, MSFT, GOOGL, META, ORCL (the five the Capital Flows post names). Capex = cash paid for PP&E as first reported.
RECEIVERS AI layers CGI already defines (fundamentals_data.AI_LAYERS: energy VST CEG NRG ETN; chips NVDA AMD AVGO MU; infrastructure
          VRT ANET DLR SMCI), pooled as "AI receivers", plus whole sectors (Industrials, Utilities, Materials), summed over today's
          S&P 500 members (survivorship stated).
TARGET    receiver revenue growth year on year at calendar quarter q+1 (sum of matched members' revenue, first reported).
BASELINE  AR(1): growth(q+1) ~ 1 + growth(q).
CANDIDATE baseline + spender capex growth at q (year on year, sum of the five, as first reported).
INFORMATION  Forecasts for q+1 are made once the spenders' capex for q AND the receivers' revenue for q are both on file (the later of
          the filing dates). Training rows are quarters whose targets were already known by then. Nothing after that date is used.
SCORING   out-of-sample squared error, candidate vs baseline, paired difference, moving-block bootstrap (block 3 quarters).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "erp_state"))
import erp_study as S  # noqa: E402  (block_boot)

SPENDERS = ["AMZN", "MSFT", "GOOGL", "META", "ORCL"]
AI_LAYERS = {
    "energy": ["VST", "CEG", "NRG", "ETN"],
    "chips": ["NVDA", "AMD", "AVGO", "MU"],
    "infrastructure": ["VRT", "ANET", "DLR", "SMCI"],
}
AI_ALL = sorted({t for v in AI_LAYERS.values() for t in v})
SECTOR_GROUPS = ["Industrials", "Utilities", "Materials"]
MIN_TRAIN = 16          # resolved quarters before the first out-of-sample forecast
BLOCK = 3
MIN_SHARE = 0.75        # share of a group's members that must have BOTH quarters for a growth figure


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


def _val(c: dict, q: str, key: str, fkey: str):
    v, f = c.get(key, {}).get(q), c.get(fkey, {}).get(q)
    return (v, f) if v is not None and f is not None else (None, None)


def group_growth(members: list[dict], q: str, key: str, fkey: str, min_share: float = MIN_SHARE):
    """(year-on-year growth of the summed first-reported values, date the figure was knowable, n members used).
    Members need BOTH q and q-4 on file; a group with too few such members returns (None, None, n)."""
    p = q_shift(q, -4)
    now = prior = 0.0
    dates, n = [], 0
    for c in members:
        a, fa = _val(c, q, key, fkey)
        b, fb = _val(c, p, key, fkey)
        if a is None or b is None or b <= 0:
            continue
        now += a
        prior += b
        dates += [fa, fb]
        n += 1
    if not members or n < max(1, int(np.ceil(min_share * len(members)))) or prior <= 0:
        return None, None, n
    return (now / prior - 1) * 100, max(dates), n


def panel(companies: list[dict], group_members: dict[str, list[dict]], first="2013Q1", last="2026Q2") -> dict:
    """Per group, per quarter: receiver growth r, spender capex growth g, and the date both were on file."""
    spenders = [c for c in companies if c["t"] in SPENDERS]
    out = {}
    for name, members in group_members.items():
        rows = []
        for q in q_range(first, last):
            r, fr, nr = group_growth(members, q, "rq1", "rfiled1")
            g, fg, ng = group_growth(spenders, q, "cq1", "filed1", min_share=1.0)    # all five spenders
            rows.append({"q": q, "r": r, "g": g, "known": max(fr, fg) if (fr and fg) else None, "rknown": fr, "n_r": nr, "n_g": ng})
        out[name] = rows
    return out


# ── walk-forward ────────────────────────────────────────────────────────────

def examples(rows: list[dict], lag: int = 0) -> list[dict]:
    """Forecasting examples: at the quarter q the features are r(q), g(q-lag); the target is r(q+1)."""
    by = {r["q"]: r for r in rows}
    out = []
    for r in rows:
        nxt = by.get(q_shift(r["q"], 1))
        gl = by.get(q_shift(r["q"], -lag))
        if r["r"] is None or nxt is None or nxt["r"] is None or gl is None or gl["g"] is None or r["known"] is None:
            continue
        out.append({"q": r["q"], "r": r["r"], "g": gl["g"], "y": nxt["r"], "known": r["known"], "ty_known": nxt.get("rknown")})
    return out


def walkforward(ex: list[dict], min_train: int = MIN_TRAIN, variant: str = "level"):
    """Out-of-sample squared errors of the baseline and the baseline + capex. A training row s is used for the forecast at q only
    if its TARGET was on file (by FILING DATE) on or before q's information date: ty_known(s) <= known(q).

    variant  "level"  baseline AR(1); candidate adds capex growth                              (pre-registered)
             "diff"   candidate adds the CHANGE in capex growth from the quarter before         (robustness: a shared trend cannot help)
             "ar2"    baseline AR(2) (adds growth two quarters back); candidate adds capex growth
    """
    prev_r = {e["q"]: e["r"] for e in ex}
    prev_g = {e["q"]: e["g"] for e in ex}

    def feats(e, cand):
        row = [1.0, e["r"]]
        if variant == "ar2":
            row.append(prev_r.get(q_shift(e["q"], -1), e["r"]))
        if cand:
            if variant == "diff":
                row.append(e["g"] - prev_g.get(q_shift(e["q"], -1), e["g"]))
            else:
                row.append(e["g"])
        return np.array(row)

    se_b, se_c, when = [], [], []
    for i, row in enumerate(ex):
        if row.get("known") is None:
            continue
        train = [e for e in ex[:i] if e.get("ty_known") and e["ty_known"] <= row["known"]]
        if len(train) < min_train:
            continue
        y = np.array([e["y"] for e in train])
        cb = np.linalg.lstsq(np.array([feats(e, False) for e in train]), y, rcond=None)[0]
        cc = np.linalg.lstsq(np.array([feats(e, True) for e in train]), y, rcond=None)[0]
        se_b.append((row["y"] - feats(row, False) @ cb) ** 2)
        se_c.append((row["y"] - feats(row, True) @ cc) ** 2)
        when.append(row["q"])
    return np.array(se_b), np.array(se_c), when


def compare(rows: list[dict], lag: int = 0, min_train: int = MIN_TRAIN, variant: str = "level", drop_quarter: str | None = None) -> dict:
    se_b, se_c, when = walkforward(examples(rows, lag), min_train, variant)
    if drop_quarter is not None:        # leave one forecast quarter out of the scoring (robustness)
        keep = [i for i, w in enumerate(when) if w != drop_quarter]
        se_b, se_c, when = se_b[keep], se_c[keep], [when[i] for i in keep]
    if len(se_b) < 8:
        return {"n": int(len(se_b)), "too_few": True}
    d = se_b - se_c
    mean, ci = S.block_boot(d, block=BLOCK, reps=3000)
    return {"n": int(len(d)), "first": when[0], "last": when[-1], "mse_base": float(se_b.mean()), "mse_cand": float(se_c.mean()),
            "rel_gain_pct": float(100 * (1 - se_c.mean() / se_b.mean())), "mean_diff": mean, "ci95": list(ci), "helps": bool(ci[0] > 0)}


def lead_lag(rows: list[dict], max_lag: int = 4) -> dict:
    """Descriptive, whole-sample: correlation of spender capex growth at q-k with receiver revenue growth at q."""
    by = {r["q"]: r for r in rows}
    out = {}
    for k in range(0, max_lag + 1):
        xs, ys = [], []
        for r in rows:
            g = by.get(q_shift(r["q"], -k))
            if r["r"] is not None and g is not None and g["g"] is not None:
                xs.append(g["g"])
                ys.append(r["r"])
        out[str(k)] = {"n": len(xs), "corr": float(np.corrcoef(xs, ys)[0, 1]) if len(xs) > 6 else None}
    return out


def group_members(companies: list[dict]) -> dict[str, list[dict]]:
    by = {c["t"]: c for c in companies}
    gm = {"AI receivers": [by[t] for t in AI_ALL if t in by]}
    for name, tk in AI_LAYERS.items():
        gm[f"AI: {name}"] = [by[t] for t in tk if t in by]
    for sec in SECTOR_GROUPS:
        gm[sec] = [c for c in companies if c["sector"] == sec and c["t"] not in SPENDERS]
    return gm
