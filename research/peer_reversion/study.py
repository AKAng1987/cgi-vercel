"""
study.py -- when an instrument moves far more than its peer group over a few days, does it come back?

The one Medallion strategy described concretely in public (Magerman): prices that move too far relative to their
group tend to come partway back. Here at DAILY resolution on CGI's universe -- coarse next to their 5-minute data, so
the honest prior is weak-or-null after costs. Offline; ships nothing.

  residual_t      = instrument's daily return minus its group's average (the instrument itself excluded)
  overshoot z     = sum of the last k residuals / (60-day residual vol x sqrt(k)), known at the close of day t
  event           = |z| >= Z_EVENT
  fade P&L        = -sign(z) x the next h days' residual (positive = it came back), minus COST per event
Events on the same day are averaged first, then days are block-bootstrapped (weekly blocks), so one market-wide
day cannot count as fifty independent wins.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Z_EVENT = 2.0
COST = 0.0010          # 10 bp round trip
VOL_WIN = 60
KS = (1, 3, 5)
HS = (1, 3, 5, 10)


def residuals(rets: pd.DataFrame, groups: dict[str, str]) -> pd.DataFrame:
    out = {}
    for g in set(groups.values()):
        cols = [c for c in rets.columns if groups.get(c) == g]
        if len(cols) < 3:
            continue
        block = rets[cols]
        s, n = block.sum(axis=1, min_count=1), block.notna().sum(axis=1)
        for c in cols:
            peers = (s - block[c].fillna(0)) / (n - block[c].notna().astype(int))
            out[c] = block[c] - peers.where(n - block[c].notna().astype(int) >= 2)
    return pd.DataFrame(out)


def events(res: pd.DataFrame, k: int) -> pd.DataFrame:
    vol = res.rolling(VOL_WIN, min_periods=40).std()
    z = res.rolling(k).sum() / (vol * np.sqrt(k))
    return z


def fade_table(res: pd.DataFrame, k: int, h: int, cost: float = COST) -> pd.Series:
    """Per-day average net fade P&L over all events that day (NaN on days with no event)."""
    z = events(res, k)
    fwd = res[::-1].rolling(h).sum()[::-1].shift(-1)        # residual over t+1..t+h
    hit = z.abs() >= Z_EVENT
    pnl = (-np.sign(z) * fwd - cost).where(hit)
    return pnl.mean(axis=1)


def block_boot(daily: pd.Series, block: int = 5, reps: int = 2000, seed: int = 0) -> dict:
    v = daily.dropna().to_numpy()
    if len(v) < 30:
        return {"mean": float("nan"), "ci95": [float("nan")] * 2, "days": int(len(v))}
    rng = np.random.default_rng(seed)
    nb = len(v) // block
    ms = []
    for _ in range(reps):
        idx = np.concatenate([np.arange(s, s + block) for s in rng.integers(0, len(v) - block, nb)])
        ms.append(v[idx].mean())
    return {"mean": float(v.mean()), "ci95": [float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))],
            "days": int(len(v)), "hit": float((v > 0).mean())}
