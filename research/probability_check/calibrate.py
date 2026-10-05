"""
calibrate.py -- are CGI's published flip probabilities calibrated, and do they beat the plain base rate
going forward? Offline; ships nothing. Reuses the walk-forward windows built for research/latent_state
(same windows, same publication lags) and its estimators, so the numbers here are comparable to RESULTS.md there.

ESTIMATORS (each fitted only on windows already resolved at t, then asked for window t)
  B0   base rate by state                         (what markov_data publishes)
  Bp   ONE pooled flip rate, no state split (is the per-state split itself just noise?)
  B1   equal-weight driver terciles               (what the "today" figure on /cgi is), fitted walk-forward
  Bλ   B0 + λ (B1 - B0), λ in {.25,.5,.75}        shrinking the "today" figure toward the base rate
  H1   base rate by state x time-in-state tercile (does the odds of a flip depend on how long we've been here?)

METRICS: Brier + paired bootstrap vs B0; calibration slope/intercept of y on logit(p) (slope < 1 = overconfident).
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

LS = pathlib.Path(__file__).resolve().parent.parent / "latent_state"
sys.path.insert(0, str(LS))
import score  # noqa: E402  (latent_state/score.py)

MIN_BUCKET = 8
LAMBDAS = (0.25, 0.5, 0.75)


def dwell(states: np.ndarray) -> np.ndarray:
    """Windows already spent in the current state, counted from PAST windows only."""
    d = np.zeros(len(states), dtype=int)
    for t in range(1, len(states)):
        d[t] = d[t - 1] + 1 if states[t] == states[t - 1] else 0
    return d


def hazard_pred(st_tr, y_tr, d_tr, s_new, d_new):
    """Base rate within (state, time-in-state tercile), terciles from TRAIN only; falls back to B0."""
    m = st_tr == s_new
    if m.sum() < 3 * MIN_BUCKET:
        return score.base_rate(st_tr, y_tr, np.array([s_new]))[0]
    cuts = np.percentile(d_tr[m], [100 / 3, 200 / 3])
    b = lambda x: int(x >= cuts[0]) + int(x >= cuts[1])
    same = np.array([b(x) == b(d_new) for x in d_tr[m]])
    yy = y_tr[m][same]
    if same.sum() < MIN_BUCKET:
        return score.base_rate(st_tr, y_tr, np.array([s_new]))[0]
    return float(np.clip(yy.mean(), score.EPS, 1 - score.EPS))


def run_axis(block: dict, reading: str = "r_pub", min_train: int = score.MIN_TRAIN) -> dict:
    W = block["windows"]
    Y = score.matrix(W, block["drivers"], reading)
    st = np.array([w["state"] for w in W])
    y = np.array([w["flip"] for w in W], dtype=float)
    d = dwell(st)
    preds = {"B0": [], "Bp": [], "B1": [], "H1": [], **{f"L{l}": [] for l in LAMBDAS}}
    idx = []
    for t in range(min_train, len(W)):
        b0 = score.base_rate(st[:t], y[:t], st[t:t + 1])[0]
        b1 = score.tercile_table(Y[:t], st[:t], y[:t], Y[t:t + 1], st[t:t + 1])[0]
        preds["B0"].append(b0)
        preds["Bp"].append(float(np.clip(y[:t].mean(), score.EPS, 1 - score.EPS)))
        preds["B1"].append(b1)
        preds["H1"].append(hazard_pred(st[:t], y[:t], d[:t], st[t], d[t]))
        for l in LAMBDAS:
            preds[f"L{l}"].append(float(np.clip(b0 + l * (b1 - b0), score.EPS, 1 - score.EPS)))
        idx.append(t)
    preds = {k: np.array(v) for k, v in preds.items()}
    yy = y[idx]
    out = {"n_scored": int(len(yy)), "n_flips": int(yy.sum()), "brier": {}, "vs_B0": {}, "calibration": {}}
    for k, p in preds.items():
        out["brier"][k] = float(score.brier(p, yy).mean())
        if k != "B0":
            out["vs_B0"][k] = score.paired_bootstrap(score.brier(p, yy), score.brier(preds["B0"], yy))
    for k in ("B0", "Bp", "B1"):
        out["calibration"][k] = calibration(preds[k], yy)
    return out


def calibration(p: np.ndarray, y: np.ndarray, reps: int = 400, seed: int = 0) -> dict:
    """Slope/intercept of y on logit(p) (1.0/0.0 = perfectly calibrated) with a bootstrap CI on the slope,
    plus three equal-count reliability bins (mean predicted vs observed)."""
    def fit(pp, yy):
        x = np.log(pp / (1 - pp))
        X = np.column_stack([np.ones_like(x), x])
        b = np.zeros(2)
        for _ in range(40):
            mu = 1 / (1 + np.exp(-X @ b))
            g = X.T @ (yy - mu) - 1e-6 * b
            H = (X * (mu * (1 - mu))[:, None]).T @ X + 1e-6 * np.eye(2)
            step = np.linalg.solve(H, g)
            b += step
            if np.abs(step).max() < 1e-8:
                break
        return b
    rng = np.random.default_rng(seed)
    b = fit(p, y)
    slopes = []
    for _ in range(reps):
        i = rng.integers(0, len(p), len(p))
        if y[i].min() == y[i].max():
            continue
        slopes.append(fit(p[i], y[i])[1])
    order = np.argsort(p)
    bins = []
    for chunk in np.array_split(order, 3):
        bins.append({"n": int(len(chunk)), "mean_pred": float(p[chunk].mean()), "observed": float(y[chunk].mean())})
    return {"intercept": float(b[0]), "slope": float(b[1]),
            "slope_ci95": [float(np.percentile(slopes, 2.5)), float(np.percentile(slopes, 97.5))], "bins": bins}
