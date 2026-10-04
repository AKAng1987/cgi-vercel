"""
score.py -- walk-forward scoring of P(flip) estimators. Offline; ships nothing.

For each window t (after a minimum history) every estimator is fitted ONLY on
windows whose outcome was already known at t's start, then asked for window t.
Nothing sees the future, and nothing is refitted on its own test window.

ESTIMATORS
  B0  base rate by state (the Markov baseline: flips / windows in that state)
  B1  the existing production idea, equal-weight driver terciles, but fitted
      walk-forward (the live table is computed over ALL windows, so it is
      in-sample and would flatter itself)
  M1  Kalman factor -> logistic

METRICS: Brier and log-loss, plus a paired bootstrap of the per-window loss
difference against B0, so "better" comes with how much luck it could be.
"""
from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

import numpy as np

import latent

MIN_TRAIN = 60
MIN_TERCILE_N = 8
EPS = 0.02          # probability clamp, as markov_data does: never 0 or 1


def _clamp(p):
    return np.clip(p, EPS, 1 - EPS)


def matrix(windows: list[dict], drivers: list[str], key: str) -> np.ndarray:
    return np.array([[np.nan if w[key][d] is None else float(w[key][d]) for d in drivers] for w in windows])


def base_rate(state_tr, y_tr, s_new):
    out = []
    for s in s_new:
        m = state_tr == s
        out.append(y_tr[m].mean() if m.sum() >= 5 else y_tr.mean())
    return _clamp(np.array(out))


def tercile_table(Y_tr, state_tr, y_tr, Y_new, s_new):
    """Equal-weight mean of P(flip | tercile) over drivers, terciles from TRAIN only."""
    out = []
    for row, s in zip(Y_new, s_new):
        ps = []
        sel = state_tr == s
        for k in range(Y_tr.shape[1]):
            col = Y_tr[sel, k]
            yy = y_tr[sel]
            m = ~np.isnan(col)
            if m.sum() < 3 * MIN_TERCILE_N or np.isnan(row[k]):
                continue
            c, yk = col[m], yy[m]
            b1, b2 = np.sort(c)[int(len(c) / 3)], np.sort(c)[int(2 * len(c) / 3)]
            tr = lambda x: 0 if x < b1 else (2 if x >= b2 else 1)
            t_new = tr(row[k])
            members = np.array([tr(x) == t_new for x in c])
            if members.sum() >= MIN_TERCILE_N:
                ps.append(yk[members].mean())
        out.append(np.mean(ps) if ps else (y_tr[sel].mean() if sel.sum() >= 5 else y_tr.mean()))
    return _clamp(np.array(out))


@dataclass
class Result:
    axis: str
    reading: str
    n_scored: int
    n_flips: int
    params: int
    brier: dict
    logloss: dict
    boot: dict


def brier(p, y):
    return (p - y) ** 2


def logloss(p, y):
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def walk_forward(windows, drivers, reading="r_pub", min_train=MIN_TRAIN, refit_every=1):
    Y = matrix(windows, drivers, reading)
    st = np.array([w["state"] for w in windows])
    y = np.array([w["flip"] for w in windows], dtype=float)
    preds = {"B0": [], "B1": [], "M1": []}
    idx, params = [], None
    fit = b = None
    for t in range(min_train, len(windows)):
        if fit is None or (t - min_train) % refit_every == 0:
            fit = latent.fit_factor(Y[:t])
            f_all, _ = latent.filter_factor(Y[: t + 1], fit)
            b = latent.fit_logistic(f_all[:t], st[:t], y[:t])
            params = latent.parameter_count(fit) + len(b)
        else:
            f_all, _ = latent.filter_factor(Y[: t + 1], fit)
        preds["B0"].append(base_rate(st[:t], y[:t], st[t:t + 1])[0])
        preds["B1"].append(tercile_table(Y[:t], st[:t], y[:t], Y[t:t + 1], st[t:t + 1])[0])
        preds["M1"].append(_clamp(latent.predict_logistic(b, f_all[t:t + 1], st[t:t + 1]))[0])
        idx.append(t)
    return {k: np.array(v) for k, v in preds.items()}, y[idx], params


def paired_bootstrap(loss_a, loss_b, reps=4000, seed=0):
    """Mean(loss_a - loss_b): negative = A better. Share of resamples where A wins."""
    rng = np.random.default_rng(seed)
    d = loss_a - loss_b
    n = len(d)
    means = np.array([d[rng.integers(0, n, n)].mean() for _ in range(reps)])
    return {"mean_diff": float(d.mean()), "ci95": [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))],
            "p_a_better": float((means < 0).mean())}


def score_axis(axis, block, reading="r_pub", **kw) -> Result:
    preds, y, params = walk_forward(block["windows"], block["drivers"], reading, **kw)
    out = {"brier": {}, "logloss": {}, "boot": {}}
    for k, p in preds.items():
        out["brier"][k] = float(brier(p, y).mean())
        out["logloss"][k] = float(logloss(p, y).mean())
    for k in ("B1", "M1"):
        out["boot"][f"{k}_vs_B0_brier"] = paired_bootstrap(brier(preds[k], y), brier(preds["B0"], y))
        out["boot"][f"{k}_vs_B0_logloss"] = paired_bootstrap(logloss(preds[k], y), logloss(preds["B0"], y))
    out["boot"]["M1_vs_B1_brier"] = paired_bootstrap(brier(preds["M1"], y), brier(preds["B1"], y))
    return Result(axis, reading, len(y), int(y.sum()), params, **out)
