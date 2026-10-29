"""consensus_study.py -- does a release's consensus (forecast minus previous) predict an axis flip?

Offline; ships nothing. A study of INFORMATION AVAILABLE BEFORE THE RELEASE: the forecast and the previous print are
both on the calendar before the number comes out, so nothing here sees the outcome.

What decides an axis (cmon-backend-service update_grid_model.py): the growth axis is up when the newest GDP print is
above the print before it (rate_of_change > 0); the inflation axis likewise for the inflation rate. So a flip happens
exactly when the SIGN of (new print - previous print) differs from the sign last time. The consensus is a market
estimate of the new print, so (forecast - previous) is a forecast of that sign. The question is whether that carries
information beyond how often this axis flips anyway.

ORIENTED GAP g: positive means "the consensus already implies a flip".
    axis currently UP  : flip needs new < previous  ->  g = previous - forecast
    axis currently DOWN: flip needs new > previous  ->  g = forecast - previous
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "latent_state"))
import score  # noqa: E402  (paired_bootstrap, base_rate, brier, logloss, _clamp)

SETTLE_DAYS = 3          # as markov_data: a flip lands 0-3 days after the release in model history
Q_TO_AXES = {1: (1, 0), 2: (1, 1), 3: (0, 1), 4: (0, 0)}      # api/release_calendar.py
SLOT = {"growth": 0, "inflation": 1}
MIN_TRAIN = 20
EPS = score.EPS


# ── state and flips from the model history ──────────────────────────────────

def axis_series(rows, axis):
    """[(date, state)] for the axis from (date, quadrant) rows."""
    return [(d, Q_TO_AXES[q][SLOT[axis]]) for d, q in rows]


def state_before(series, date):
    s = None
    for d, st in series:
        if d < date:
            s = st
        else:
            break
    return s


def flip_after(series, date, settle=SETTLE_DAYS):
    """Did the axis state change between the last row before `date` and the last row on/before date+settle?"""
    before = state_before(series, date)
    if before is None:
        return None, None
    end = (dt.date.fromisoformat(date) + dt.timedelta(days=settle)).isoformat()
    after = before
    for d, st in series:
        if d >= date and d <= end:
            after = st
    return before, int(after != before)


def oriented_gap(forecast, previous, state):
    if forecast is None or previous is None or state is None:
        return None
    return (previous - forecast) if state == 1 else (forecast - previous)


# ── the release table ───────────────────────────────────────────────────────

def build_rows(releases, series):
    """One row per release: state before, flip, forecast, previous, actual, oriented gap, actual-implied sign."""
    out = []
    for r in releases:
        date = r["date"][:10]
        st, flip = flip_after(series, date)
        if st is None:
            continue
        g = oriented_gap(r.get("forecast"), r.get("previous"), st)
        out.append({"date": date, "period": r.get("period"), "state": st, "flip": flip,
                    "forecast": r.get("forecast"), "previous": r.get("previous"), "actual": r.get("actual"),
                    "g": g})
    out.sort(key=lambda x: x["date"])
    return out


# ── walk-forward estimators ─────────────────────────────────────────────────

def _logit_fit(x, y, iters=60, l2=1.0):
    """Logistic regression y ~ a + b*x with a small ridge on b (stable at n of a few dozen)."""
    a, b = 0.0, 0.0
    for _ in range(iters):
        z = a + b * x
        p = 1 / (1 + np.exp(-z))
        w = p * (1 - p) + 1e-6
        ga, gb = np.sum(p - y), np.sum((p - y) * x) + l2 * b
        haa, hab, hbb = np.sum(w), np.sum(w * x), np.sum(w * x * x) + l2
        det = haa * hbb - hab * hab
        if abs(det) < 1e-12:
            break
        da, db = (hbb * ga - hab * gb) / det, (-hab * ga + haa * gb) / det
        a, b = a - da, b - db
        if abs(da) + abs(db) < 1e-7:
            break
    return a, b


def walk_forward(rows, min_train=MIN_TRAIN):
    """Expanding window. Row t is predicted from rows 0..t-1 only. Returns arrays over scored rows."""
    use = [r for r in rows if r["g"] is not None]
    g = np.array([r["g"] for r in use], dtype=float)
    y = np.array([r["flip"] for r in use], dtype=float)
    st = np.array([r["state"] for r in use])
    p0, p1, idx = [], [], []
    for t in range(min_train, len(use)):
        p0.append(score.base_rate(st[:t], y[:t], st[t:t + 1])[0])
        sd = g[:t].std() or 1.0
        a, b = _logit_fit(g[:t] / sd, y[:t])
        p1.append(float(np.clip(1 / (1 + np.exp(-(a + b * g[t] / sd))), EPS, 1 - EPS)))
        idx.append(t)
    return np.array(p0), np.array(p1), y[idx], [use[i] for i in idx]


def block_boot(d, block=3, reps=4000, seed=0):
    """Mean of d with a moving-block bootstrap CI (releases are sequential; adjacent ones share state)."""
    rng = np.random.default_rng(seed)
    n = len(d)
    nb = int(np.ceil(n / block))
    means = []
    for _ in range(reps):
        starts = rng.integers(0, max(1, n - block + 1), nb)
        means.append(np.concatenate([d[s:s + block] for s in starts])[:n].mean())
    return float(d.mean()), [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def compare(rows, min_train=MIN_TRAIN):
    """Brier of the gap model vs the base rate, with the paired bootstrap difference (negative = gap model better)."""
    p0, p1, y, used = walk_forward(rows, min_train)
    if len(y) < 8:
        return {"n_scored": int(len(y)), "note": "too few releases"}
    b0, b1 = score.brier(p0, y), score.brier(p1, y)
    d = b1 - b0
    mean, ci = block_boot(d)
    return {"n_scored": int(len(y)), "n_flips": int(y.sum()), "brier_base": float(b0.mean()),
            "brier_gap": float(b1.mean()), "diff": mean, "ci95": ci,
            "verdict": "BETTER" if ci[1] < 0 else ("worse" if ci[0] > 0 else "no clear difference")}


def sign_rule(rows):
    """Mechanical benchmark: call a flip when sign(forecast - previous) differs from the current state (g > 0)."""
    use = [r for r in rows if r["g"] is not None and r["actual"] is not None]
    if not use:
        return {}
    pred = np.array([r["g"] > 0 for r in use])
    y = np.array([r["flip"] for r in use], dtype=bool)
    tp, fp = int((pred & y).sum()), int((pred & ~y).sum())
    fn, tn = int((~pred & y).sum()), int((~pred & ~y).sum())
    return {"n": len(use), "hit_rate": float((pred == y).mean()), "flip_rate": float(y.mean()),
            "TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "p_flip_given_pred": float(tp / (tp + fp)) if tp + fp else None,
            "p_flip_given_not_pred": float(fn / (fn + tn)) if fn + tn else None}


def bins(rows):
    """No model: flip rate when the consensus implies a flip (g>0) vs not, and by |g| size."""
    use = [r for r in rows if r["g"] is not None]
    out = {}
    for name, f in (("g<=0 (consensus implies no flip)", lambda r: r["g"] <= 0),
                    ("g>0 (consensus implies a flip)", lambda r: r["g"] > 0)):
        sel = [r for r in use if f(r)]
        out[name] = {"n": len(sel), "flips": sum(r["flip"] for r in sel),
                     "rate": (sum(r["flip"] for r in sel) / len(sel)) if sel else None}
    return out
