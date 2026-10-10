"""
erp_study.py -- does Damodaran's implied equity risk premium (ERP) tell us anything about the next 1-3 months of the
S&P 500 that CGI's regime and plain 20-day volatility do not already tell us? Offline; ships nothing.

QUESTION   Do ERP level terciles, 3-month change terciles, or ERP-minus-T-bond terciles improve a walk-forward prediction
           of SPX forward 1m / 3m return, 3m max drawdown, or 3m realised vol, beyond the BASELINE below?
BASELINE   target ~ 1 + log(vol20) + compass quadrant dummies + grid quadrant dummies   (OLS, refit each month)
CANDIDATE  the baseline + "bottom tercile" and "top tercile" dummies of one ERP feature.
INFORMATION  At decision month M the ERP row used is the one dated the FIRST OF THE PRIOR MONTH (he posts a row in its
           first week; a one-month lag is the cautious reading). Terciles use only ERP values up to that row (expanding
           window). Regressions train only on months whose forward window had already ended. Entry = prior close.
SCORING    Out-of-sample squared error, candidate vs baseline, paired difference d_t = se_base - se_cand (positive = ERP
           helped). Moving-block bootstrap (block = 3 months, windows overlap) for the 95% interval of mean(d).
"""
from __future__ import annotations

import bisect
import json
import math
import pathlib

import numpy as np

H1, H3 = 21, 63
MIN_ERP_ROWS = 36     # months of ERP history before terciles are used
MIN_TRAIN = 30        # resolved training months before the first out-of-sample prediction
BLOCK = 3
B = 3000
TARGETS = {"ret1m": ("r1", H1), "ret3m": ("r3", H3), "maxdd3m": ("dd", H3), "vol3m": ("v3", H3)}
FEATURES = {"erp_level": "b_level", "erp_chg3": "b_chg", "erp_gap": "b_gap"}


def load(path=None) -> dict:
    p = pathlib.Path(path) if path else pathlib.Path(__file__).resolve().parent / "data" / "inputs.json"
    return json.loads(p.read_text())


def expanding_terciles(vals: list) -> list:
    """Bucket 0/1/2 of vals[i] against cutoffs from vals[:i+1] only; None until MIN_ERP_ROWS values exist."""
    out = [None] * len(vals)
    seen: list[float] = []
    for i, v in enumerate(vals):
        if v is None:
            continue
        seen.append(v)
        if len(seen) < MIN_ERP_ROWS:
            continue
        c = np.percentile(seen, [100 / 3, 200 / 3])
        out[i] = int(v >= c[0]) + int(v >= c[1])
    return out


def build(inp: dict) -> list[dict]:
    spx = inp["SPX"]
    dates = [x[0] for x in spx]
    p = np.array([x[1] for x in spx])
    n = len(p)
    ret = np.zeros(n)
    ret[1:] = p[1:] / p[:-1] - 1
    erp, tb = dict(inp["ERP_T12M"]), dict(inp["ERP_TBOND"])
    months = sorted(set(erp) & set(tb))
    v_erp = [erp[m] for m in months]
    v_gap = [erp[m] - tb[m] for m in months]
    v_chg = [None] * 3 + [v_erp[i] - v_erp[i - 3] for i in range(3, len(months))]
    b = {"b_level": expanding_terciles(v_erp), "b_gap": expanding_terciles(v_gap), "b_chg": expanding_terciles(v_chg)}
    comp_d, comp_q = zip(*inp["compass_US"])
    grid_d, grid_q = zip(*inp["grid_US"])
    rows = []
    for i, m in enumerate(months):
        nxt = (int(m[:4]) + (int(m[5:7]) == 12), int(m[5:7]) % 12 + 1)
        d0 = f"{nxt[0]:04d}-{nxt[1]:02d}-01"
        di = bisect.bisect_left(dates, d0)
        e = di - 1                                    # entry = close before the decision day
        if e < 25 or di >= n:
            continue
        ci, gi = bisect.bisect_right(comp_d, dates[e]) - 1, bisect.bisect_right(grid_d, dates[e]) - 1
        if ci < 0 or gi < 0:
            continue
        r = {"month": m, "date": dates[e], "e": e, "erp": v_erp[i], "gap": v_gap[i],
             "vol20": float(ret[e - 19:e + 1].std(ddof=1) * math.sqrt(252)) or 1e-6,
             "comp": comp_q[ci], "grid": grid_q[gi], "r1": None, "r3": None, "dd": None, "v3": None}
        r.update({k: b[k][i] for k in b})
        if e + H1 < n:
            r["r1"] = float(p[e + H1] / p[e] - 1) * 100
        if e + H3 < n:
            path = p[e:e + H3 + 1] / p[e]
            r["r3"] = float(path[-1] - 1) * 100
            r["dd"] = float((1 - path / np.maximum.accumulate(path)).max()) * 100
            r["v3"] = float(ret[e + 1:e + H3 + 1].std(ddof=1) * math.sqrt(252)) * 100
        rows.append(r)
    return rows


def _base_x(r: dict) -> np.ndarray:
    return np.array([1.0, math.log(max(r["vol20"], 1e-6))]
                    + [float(r["comp"] == q) for q in (2, 3, 4)] + [float(r["grid"] == q) for q in (2, 3, 4)])


def _cand_x(r: dict, feat: str) -> np.ndarray:
    return np.concatenate([_base_x(r), [float(r[feat] == 0), float(r[feat] == 2)]])


def walkforward(rows: list[dict], feature: str, target: str, h: int) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Out-of-sample squared errors of baseline and candidate for every month that can be scored."""
    feat = FEATURES.get(feature, feature)
    se_b, se_c, when = [], [], []
    for t, row in enumerate(rows):
        if row[feat] is None or row[target] is None:
            continue
        train = [r for r in rows[:t] if r[feat] is not None and r[target] is not None and r["e"] + h <= row["e"]]
        if len(train) < MIN_TRAIN:
            continue
        y = np.array([r[target] for r in train])
        cb = np.linalg.lstsq(np.array([_base_x(r) for r in train]), y, rcond=None)[0]
        cc = np.linalg.lstsq(np.array([_cand_x(r, feat) for r in train]), y, rcond=None)[0]
        se_b.append((row[target] - _base_x(row) @ cb) ** 2)
        se_c.append((row[target] - _cand_x(row, feat) @ cc) ** 2)
        when.append(row["month"])
    return np.array(se_b), np.array(se_c), when


def block_boot(d: np.ndarray, stat=np.mean, block: int = BLOCK, reps: int = B, seed: int = 0):
    rng = np.random.default_rng(seed)
    n = len(d)
    nb = math.ceil(n / block)
    starts = rng.integers(0, max(1, n - block + 1), size=(reps, nb))
    idx = (starts[:, :, None] + np.arange(block)[None, None, :]).reshape(reps, -1)[:, :n]
    s = stat(d[idx], axis=1)
    return float(stat(d)), (float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5)))


def compare(rows, feature, target, h, seed=0) -> dict:
    se_b, se_c, when = walkforward(rows, feature, target, h)
    if len(se_b) < 40:
        return {"n": int(len(se_b)), "too_few": True}
    d = se_b - se_c
    mean, ci = block_boot(d, seed=seed)
    return {"n": int(len(d)), "first": when[0], "last": when[-1], "mse_base": float(se_b.mean()), "mse_cand": float(se_c.mean()),
            "rel_gain_pct": float(100 * (1 - se_c.mean() / se_b.mean())), "mean_diff": mean, "ci95": ci, "helps": bool(ci[0] > 0)}


def tercile_table(rows, feature="b_level") -> dict:
    ev = [r for r in rows if r[feature] is not None]
    out = {}
    for k in (0, 1, 2):
        g = [r for r in ev if r[feature] == k]
        out[k] = {"n": len(g), **{t: (float(np.mean([r[t] for r in g if r[t] is not None])) if any(r[t] is not None for r in g) else None)
                                  for t in ("r1", "r3", "dd", "v3")}}
    return out


def low_vs_high(rows, target, feature="b_level", seed=1) -> dict:
    ev = [r for r in rows if r[feature] is not None and r[target] is not None]
    if len(ev) < 40:
        return {"n": len(ev), "too_few": True}
    lab = np.array([r[feature] for r in ev])
    val = np.array([r[target] for r in ev])
    rng = np.random.default_rng(seed)
    n = len(ev)
    nb = math.ceil(n / BLOCK)
    diffs = []
    for _ in range(B):
        idx = (rng.integers(0, n - BLOCK + 1, size=nb)[:, None] + np.arange(BLOCK)[None, :]).ravel()[:n]
        l, v = lab[idx], val[idx]
        if (l == 0).sum() and (l == 2).sum():
            diffs.append(v[l == 0].mean() - v[l == 2].mean())
    diff = float(val[lab == 0].mean() - val[lab == 2].mean())
    return {"n_low": int((lab == 0).sum()), "n_high": int((lab == 2).sum()), "diff_low_minus_high": diff,
            "ci95": (float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5)))}


def spearman(a, b) -> float:
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def annual_supplement(inp: dict, seed=2) -> dict:
    """Year-end ERP (1961-2024) vs the NEXT calendar year's S&P 500 price return and worst drawdown. n is ~60 years."""
    spx = inp["SPX"]
    dates = [x[0] for x in spx]
    p = np.array([x[1] for x in spx])
    erp, tb = dict(inp["ERP_ANNUAL"]), dict(inp["ERP_ANNUAL_TBOND"])
    X, G, R, D = [], [], [], []
    for y in range(1961, 2025):
        a, z = f"{y}-12-31", f"{y + 1}-12-31"
        if a not in erp or a not in tb:
            continue
        i0, i1 = bisect.bisect_right(dates, a) - 1, bisect.bisect_right(dates, z) - 1
        if dates[i1] < f"{y + 1}-12-20":
            continue
        path = p[i0:i1 + 1] / p[i0]
        X.append(erp[a]); G.append(erp[a] - tb[a]); R.append((path[-1] - 1) * 100)
        D.append(float((1 - path / np.maximum.accumulate(path)).max()) * 100)
    X, G, R, D = map(np.array, (X, G, R, D))
    rng = np.random.default_rng(seed)

    def boot(a, b):
        s = []
        for _ in range(B):
            ix = rng.integers(0, len(a), len(a))
            s.append(spearman(a[ix], b[ix]))
        return float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))
    return {"n_years": int(len(X)),
            **{f"{fx}_vs_{ty}": {"rho": spearman(fv, tv), "ci95": boot(fv, tv)}
               for fx, fv in (("erp", X), ("gap", G)) for ty, tv in (("next_year_return", R), ("next_year_max_drawdown", D))}}
