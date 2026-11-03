"""
election_study.py -- does the S&P 500 (price index) behave differently after a US midterm election, or in the midterm-year
Mar-Sep season, than a volatility-matched baseline?  Offline; ships nothing.  Pre-registered in PREREG.md (commit before any return).

PRIMARY    252-trading-day return from the close before election day, 19 midterms 1950-2022, minus the mean forward-252 return of
           all start days in the same expanding 20-day-vol tercile (start days within 21 bars of any election excluded).
INFERENCE  permutation (draw random start days from the event's tercile pool) for p; moving-block bootstrap (block 252) of the
           baseline means + resampling of the 19 events for the interval.  A "claim" needs p < 0.05 AND an interval excluding 0.
"""
from __future__ import annotations

import bisect
import json
import pathlib

import numpy as np

import elections as E

HERE = pathlib.Path(__file__).resolve().parent
LAST_CLOSE = "2026-11-02"       # the 3 Nov bar is intraday when this was built; the live case uses the 2 Nov close
EXCL = 21                       # start days within this many bars of an election are not baseline
BLOCK = 252
VOL_N = 20


def load_spx(path=None):
    rows = json.loads(pathlib.Path(path or HERE / "data" / "spx_yahoo.json").read_text())
    import datetime as dt
    out = []
    for d, c in rows:
        if d > LAST_CLOSE:
            continue
        if d < "1952-06-01" and dt.date.fromisoformat(d).weekday() == 5:
            continue                                # Saturday sessions before June 1952
        out.append((d, float(c)))
    return [d for d, _ in out], np.array([c for _, c in out])


def vol20(c):
    lr = np.diff(np.log(c))
    v = np.full(len(c), np.nan)
    for i in range(VOL_N, len(c)):
        v[i] = lr[i - VOL_N:i].std(ddof=1)
    return v


def expanding_terciles(v):
    """tercile (0/1/2) of v[i] against v[first valid..i] only; -1 where v is nan."""
    out = np.full(len(v), -1, dtype=int)
    hist = []
    for i, x in enumerate(v):
        if np.isnan(x):
            continue
        bisect.insort(hist, x)
        rank = bisect.bisect_left(hist, x) / max(len(hist) - 1, 1) if len(hist) > 1 else 0.5
        out[i] = 0 if rank < 1 / 3 else (1 if rank < 2 / 3 else 2)
    return out


def forward(c, h):
    f = np.full(len(c), np.nan)
    f[:len(c) - h] = c[h:] / c[:len(c) - h] - 1
    return f


def bar_before(dates, day):
    """index of the last bar strictly before `day` (ISO string)."""
    return bisect.bisect_left(dates, day) - 1


def state_at(c, i):
    """Correction / Up / Flat at bar i, using only data up to i."""
    hi = c[max(0, i - 251):i + 1].max()
    dd = c[i] / hi - 1
    r3 = c[i] / c[i - 63] - 1
    return ("Correction" if dd <= -0.10 else ("Up" if r3 >= 0.03 else "Flat")), dd, r3


def pool_mask(fwd, terc, e_idx, first=0):
    m = ~np.isnan(fwd) & (terc >= 0)
    m[:first] = False
    for e in e_idx:
        m[max(0, e - EXCL):e + EXCL + 1] = False
    return m


def _block_means(vals, mask, n_boot, rng):
    """moving-block bootstrap of the mean of vals[mask] (blocks of BLOCK consecutive bars, timeline order)."""
    n = len(vals)
    x = np.where(mask, vals, 0.0)
    cs = np.concatenate([[0.0], np.cumsum(x)])
    cn = np.concatenate([[0], np.cumsum(mask.astype(int))])
    nb = -(-n // BLOCK)
    starts = rng.integers(0, n - BLOCK + 1, size=(n_boot, nb))
    s = (cs[starts + BLOCK] - cs[starts]).sum(1)
    k = (cn[starts + BLOCK] - cn[starts]).sum(1)
    return np.where(k > 0, s / np.maximum(k, 1), np.nan)


def excess_test(ev_vals, ev_terc, ev_idx, terc, fwd, rng, first=0, n_boot=2000):
    """mean excess of event values over their tercile's baseline mean; permutation p, bootstrap 95% interval, claim flag."""
    ev_vals, ev_terc = np.asarray(ev_vals, float), np.asarray(ev_terc, int)
    mask = pool_mask(fwd, terc, ev_idx, first)
    pools = {k: fwd[mask & (terc == k)] for k in (0, 1, 2)}
    base = {k: (pools[k].mean() if len(pools[k]) else np.nan) for k in pools}
    ex = ev_vals - np.array([base[k] for k in ev_terc])
    stat = float(ex.mean())
    # permutation null: move the whole election calendar by a common circular offset inside the sample (from `first` on).  Keeps the
    # 4-year spacing and the autocorrelation of returns (iid random dates proved too conservative for evenly spaced events in the
    # self-test); every offset is used, offset 0 is the observed calendar.
    ev_idx = np.asarray(ev_idx)
    L = len(fwd) - 253 - first
    bt = np.array([base[0], base[1], base[2], np.nan])[np.where(terc >= 0, terc, 3)]
    pos = first + (ev_idx[None, :] - first + np.arange(L)[:, None]) % L
    vals = fwd[pos] - bt[pos]
    null = vals[~np.isnan(vals).any(1)].mean(1)
    p = float(np.sum(np.abs(null) >= abs(stat) - 1e-12) / len(null))
    bm = {k: _block_means(fwd, mask & (terc == k), n_boot, rng) for k in (0, 1, 2)}
    pick = rng.integers(0, len(ev_vals), size=(n_boot, len(ev_vals)))
    bmat = np.stack([bm[k] for k in (0, 1, 2)], 1)               # n_boot x 3
    boot = (ev_vals[pick] - bmat[np.arange(n_boot)[:, None], ev_terc[pick]]).mean(1)
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    return {"n": len(ev_vals), "mean_excess": stat, "mean_event": float(ev_vals.mean()),
            "mean_baseline": float(np.mean([base[k] for k in ev_terc])), "p": p, "n_offsets": int(len(null)), "ci95": [float(lo), float(hi)],
            "claim": bool(p < 0.05 and (lo > 0 or hi < 0)), "pool_sizes": {k: int(len(pools[k])) for k in pools}}


def season_stats(dates, c, year):
    """(start idx = last close of Feb, end idx = last close of Sep, return, max drawdown) for the Mar 1-Sep 30 window."""
    s = bar_before(dates, f"{year}-03-01")
    e = bar_before(dates, f"{year}-10-01")
    seg = c[s:e + 1]
    dd = float((seg / np.maximum.accumulate(seg) - 1).min())
    return s, e, float(c[e] / c[s] - 1), dd


def diff_perm(a, b, rng, n=10000):
    a, b = np.asarray(a, float), np.asarray(b, float)
    obs = a.mean() - b.mean()
    allv = np.concatenate([a, b])
    cnt = 0
    for _ in range(n):
        rng.shuffle(allv)
        cnt += abs(allv[:len(a)].mean() - allv[len(a):].mean()) >= abs(obs) - 1e-12
    return float(obs), float((1 + cnt) / (n + 1))


def crosscheck(dates, c, tv_elections, tv_last300, tol=0.001):
    """compare Yahoo closes with the TradingView spot-checks; return {'checked': n, 'gaps': [...] } for gaps over tol."""
    pos = {d: i for i, d in enumerate(dates)}
    gaps, n = [], 0
    for y, (d, tv) in tv_elections.items():
        n += 1
        if d not in pos:
            gaps.append({"what": f"election {y}", "date": d, "note": "date missing in Yahoo", "tv": tv}); continue
        g = c[pos[d]] / tv - 1
        if abs(g) > tol:
            gaps.append({"what": f"election {y}", "date": d, "yahoo": float(c[pos[d]]), "tv": tv, "gap_pct": float(100 * g)})
    tv = np.array(tv_last300["c"])
    last = pos[tv_last300["last_date"]]
    first = last - len(tv) + 1
    if dates[first] != tv_last300["first_date"]:
        gaps.append({"what": "last300 alignment", "note": f"first date {dates[first]} != TV {tv_last300['first_date']}"})
    else:
        n += len(tv)
        for j, t in enumerate(tv):
            g = c[first + j] / t - 1
            if abs(g) > tol:
                gaps.append({"what": "last300", "date": dates[first + j], "yahoo": float(c[first + j]), "tv": float(t),
                             "gap_pct": float(100 * g)})
    return {"checked": n, "gaps": gaps}
