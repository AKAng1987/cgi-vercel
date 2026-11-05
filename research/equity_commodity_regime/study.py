"""study.py -- regime tilt, vol sizing and regime correlations in a 7-equity + 3-commodity ETF portfolio, judged on Sharpe over cash. Offline; ships nothing.
Reuses the covariance, optimiser and bootstrap pieces of research/regime_diversification (study.py there). Rules are in PREREG.md."""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("rd_study", HERE.parent / "regime_diversification" / "study.py")
D = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(D)

RISK = ["SPY", "QQQ", "IWM", "EWJ", "EWG", "FXI", "EWZ", "DBC", "GLD", "USO"]
EQ, CM = list(range(7)), [7, 8, 9]
NAMES = RISK + ["SHY"]
CASH = 10
COSTS = np.array([10 if s in ("DBC", "USO", "EWZ", "FXI") else 5 for s in NAMES]) / 1e4
VOL_TARGET = 0.10
TILT = 0.15
MIN_REG = D.MIN_REG


def load():
    y = json.loads((HERE / "data" / "yahoo.json").read_text())
    ser = {s: {d: a for d, _, a in y[s]} for s in NAMES}
    dates = sorted(set.intersection(*[set(v) for v in ser.values()]))
    px = np.array([[ser[s][d] for s in NAMES] for d in dates])
    return dates[1:], px[1:] / px[:-1] - 1


def labels(dates, lag=1):
    h = json.loads((HERE / "data" / "regime_history.json").read_text())
    c = D._step([tuple(x) for x in h["compass"]], dates, lag)
    g = D._step([tuple(x) for x in h["grid"]], dates, lag)
    bucket = np.where(c < 0, -1, np.where(c >= 3, 3, c))
    quad = np.where((c < 0) | (g < 0), -1, (c - 1) * 4 + (g - 1))
    return bucket, quad


def overlay(w, cov):
    s = min(1.0, VOL_TARGET / np.sqrt(w @ cov @ w * 252))
    return np.concatenate([s * w, [1 - s]])


def group_w(vol, eq_share):
    w = np.zeros(10)
    iv = 1 / vol
    w[EQ] = iv[EQ] / iv[EQ].sum() * eq_share
    w[CM] = iv[CM] / iv[CM].sum() * (1 - eq_share)
    return w


def tilt_share(rets, lab, i):
    """equity share: 0.5 +/- TILT toward the group that did better on earlier days of the same label; 0.5 when too few days."""
    cur = lab[i - 1]
    if cur < 0:
        return 0.5
    idx = np.where(lab[:i] == cur)[0]
    if len(idx) < MIN_REG:
        return 0.5
    diff = rets[idx][:, EQ].mean() - rets[idx][:, CM].mean()
    return 0.5 + TILT * np.sign(diff)


def schedule(rets, dates, bucket, quad, lag_bucket=None):
    days = D.decision_days(dates)
    lab_b = bucket if lag_bucket is None else lag_bucket
    r = rets[:, :10]
    W = {k: [] for k in ("EW", "V", "G0", "T1", "T1q", "T1lag", "B4e", "C", "Cpure", "Clag", "B4roll")}
    for i in days:
        hist = r[:i]
        d = r[i - 60:i].std(axis=0, ddof=1)
        blind = D.shrunk_corr(hist)
        cb = np.outer(d, d) * blind
        mk = lambda w: overlay(w, cb)
        reg = lambda lab, bl=D.BLEND: np.outer(d, d) * D.regime_corr(r, lab, i, blind, bl)
        iv = 1 / d
        W["EW"].append(np.concatenate([np.full(10, 0.1), [0.0]]))
        W["V"].append(mk(iv / iv.sum()))
        W["G0"].append(mk(group_w(d, 0.5)))
        W["T1"].append(mk(group_w(d, tilt_share(r, bucket, i))))
        W["T1q"].append(mk(group_w(d, tilt_share(r, quad, i))))
        W["T1lag"].append(mk(group_w(d, tilt_share(r, lab_b, i))))
        W["B4e"].append(mk(D.min_var(cb)))
        W["C"].append(mk(D.min_var(reg(bucket))))
        W["Cpure"].append(mk(D.min_var(reg(bucket, 1.0))))
        W["Clag"].append(mk(D.min_var(reg(lab_b))))
        W["B4roll"].append(mk(D.min_var(np.outer(d, d) * D.shrunk_corr(r[i - 756:i]))))
    return days, {k: np.array(v) for k, v in W.items()}


def simulate(rets, days, Wk, costs=None):
    return D.simulate(rets, days, Wk, costs=COSTS if costs is None else costs)


def paired_ci(a, b, stat, idx, rf=None, level=0.95):
    """stat(a) - stat(b), point and percentile interval over paired block resamples."""
    q = (1 - level) / 2 * 100
    def f(x, i=None):
        xx = x if i is None else x[i]
        return stat(xx) if rf is None else stat(xx, rf if i is None else rf[i])
    pt = float(f(a) - f(b))
    bs = np.concatenate([f(a, idx[c:c + 250]) - f(b, idx[c:c + 250]) for c in range(0, len(idx), 250)])
    return pt, float(np.percentile(bs, q)), float(np.percentile(bs, 100 - q))


SHARPE_LEVEL = 1 - 0.05 / 2        # two primary tests after PREREG Amendment 1 (Bonferroni)


def primary(R, rf, idx):
    """P1 regime tilt (Sharpe, T1 - G0) and P3 regime correlations (volatility, C lower than B4e AND V), 97.5% intervals (PREREG Amendment 1).
    P2 (V - EW, Sharpe) is returned for the record but is descriptive, not a claim."""
    sh = lambda a, b: paired_ci(R[a], R[b], D.sharpe, idx, rf=rf, level=SHARPE_LEVEL)
    vo = lambda a, b: paired_ci(R[b], R[a], D.ann_vol, idx, level=SHARPE_LEVEL)          # positive = a calmer than b
    p1 = sh("T1", "G0"); p2 = sh("V", "EW"); p3a = vo("C", "B4e"); p3b = vo("C", "V")
    return {"P1": (p1[1] > 0, p1), "P2": (False, p2), "P3": (p3a[1] > 0 and p3b[1] > 0, p3a, p3b)}
