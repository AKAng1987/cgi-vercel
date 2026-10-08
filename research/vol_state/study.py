"""
study.py -- does sizing by the HMM's P(stormy) beat sizing by plain 20-day volatility? Offline; ships nothing.

Rules (all use information up to the previous close only):
  HOLD   always 1x
  VOL20  1x scaled to a 15% annual vol target using the trailing 20-day volatility, capped at 1.5x
  HMM    same target, using the HMM's predicted volatility for tomorrow (P(stormy)-weighted state vols)
The HMM is refitted every 63 trading days on the previous 10 years only (walk-forward).
"""
from __future__ import annotations

import numpy as np

import hmm

TARGET = 0.15 / np.sqrt(252)
CAP = 1.5
WINDOW = 2520
REFIT = 63


def vol20(r: np.ndarray) -> np.ndarray:
    s = np.full(len(r), np.nan)
    for t in range(20, len(r)):
        s[t] = r[t - 20:t].std()                      # up to yesterday
    return s


def hmm_vol(r: np.ndarray) -> np.ndarray:
    """Predicted vol for day t using returns up to t-1, refitting on the trailing window every REFIT days."""
    s = np.full(len(r), np.nan)
    p = None
    for start in range(WINDOW, len(r), REFIT):
        p = hmm.fit(r[start - WINDOW:start])
        end = min(start + REFIT, len(r))
        # filter from the window start so the state belief is warm, then read the block
        probs = hmm.filter_next(r[start - WINDOW:end - 1], p)
        ps = probs[WINDOW - 1:WINDOW - 1 + (end - start)]
        s[start:end] = ps * p["sd"][1] + (1 - ps) * p["sd"][0]
    return s


def weights(sig: np.ndarray) -> np.ndarray:
    return np.clip(TARGET / sig, 0, CAP)


def stats(ret: np.ndarray) -> dict:
    eq = np.cumprod(1 + ret)
    dd = 1 - eq / np.maximum.accumulate(eq)
    ann = eq[-1] ** (252 / len(ret)) - 1
    vol = ret.std() * np.sqrt(252)
    return {"cagr": ann, "vol": vol, "sharpe": (ret.mean() * 252) / vol if vol else 0.0,
            "max_dd": dd.max(), "calmar": ann / dd.max() if dd.max() else 0.0}


def sharpe_diff_boot(a: np.ndarray, b: np.ndarray, block: int = 21, reps: int = 2000, seed: int = 0) -> dict:
    """Block bootstrap (monthly blocks keep volatility clustering) of Sharpe(a) - Sharpe(b)."""
    rng = np.random.default_rng(seed)
    n = len(a); k = n // block
    sh = lambda x: x.mean() / x.std() * np.sqrt(252)
    d = []
    for _ in range(reps):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.integers(0, n - block, k)])
        d.append(sh(a[idx]) - sh(b[idx]))
    d = np.array(d)
    return {"diff": float(sh(a) - sh(b)), "ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]}


def run(r: np.ndarray) -> dict:
    v20, vh = vol20(r), hmm_vol(r)
    ok = ~np.isnan(v20) & ~np.isnan(vh)
    rr = r[ok]
    rules = {"HOLD": rr, "VOL20": weights(v20[ok]) * rr, "HMM": weights(vh[ok]) * rr}
    out = {k: stats(v) for k, v in rules.items()}
    out["HMM_vs_VOL20"] = sharpe_diff_boot(rules["HMM"], rules["VOL20"])
    out["n_days"] = int(ok.sum())
    return out
