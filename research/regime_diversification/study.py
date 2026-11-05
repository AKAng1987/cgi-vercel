"""study.py -- does a Compass-regime-conditional correlation matrix improve a walk-forward long-only portfolio? Offline; ships nothing.

Rules (see PREREG.md, locked before run.py): decision day = first trading day of a month, every input dated before it.
Covariance = D R D with D = 60-day vol; the baselines and the candidate differ only in R (blind vs regime-conditional)."""
from __future__ import annotations

import json
import pathlib

import numpy as np
from scipy.optimize import minimize

HERE = pathlib.Path(__file__).resolve().parent
SLEEVES = ["SPY", "QQQ", "IWM", "EWJ", "EWG", "FXI", "EWZ", "VNQ", "TLT", "IEF", "SHY", "GLD", "DBC", "UUP"]
COST_BPS = {s: (10 if s in ("DBC", "EWZ", "FXI", "UUP") else 5) for s in SLEEVES}
CAP = 0.25
MIN_HIST = 756
MIN_REG = 120
SHRINK = 0.2
BLEND = 0.5
BLOCK = 21


# ---------------------------------------------------------------- data
def load():
    y = json.loads((HERE / "data" / "yahoo.json").read_text())
    ser = {s: {d: a for d, _, a in y[s]} for s in SLEEVES}
    dates = sorted(set.intersection(*[set(v) for v in ser.values()]))
    px = np.array([[ser[s][d] for s in SLEEVES] for d in dates])
    return dates[1:], px[1:] / px[:-1] - 1


def _step(events, dates, lag):
    """label in force on each date (last event on or before it), then shifted by `lag` trading days. -1 = none yet."""
    ev = sorted(events)
    out = np.full(len(dates), -1)
    j, cur = 0, -1
    for i, d in enumerate(dates):
        while j < len(ev) and ev[j][0] <= d:
            cur = ev[j][1]; j += 1
        out[i] = cur
    if lag:
        out = np.concatenate([np.full(lag, -1), out[:-lag]])
    return out


def labels(dates, lag=1):
    h = json.loads((HERE / "data" / "regime_history.json").read_text())
    c = _step([tuple(x) for x in h["compass"]], dates, lag)
    g = _step([tuple(x) for x in h["grid"]], dates, lag)
    bucket = np.where(c < 0, -1, np.where(c >= 3, 3, c))               # 1, 2, 3 (= C3+C4)
    quad = np.where((c < 0) | (g < 0), -1, (c - 1) * 4 + (g - 1))      # 0..15
    return bucket, quad


# ---------------------------------------------------------------- covariance pieces
def shrunk_corr(x):
    r = np.corrcoef(x, rowvar=False)
    n = r.shape[0]
    avg = (r.sum() - n) / (n * (n - 1))
    t = np.full((n, n), avg); np.fill_diagonal(t, 1.0)
    return (1 - SHRINK) * r + SHRINK * t


def regime_corr(rets, lab, i, blind, blend, window=None):
    """correlation from days before i that carried the same label as day i-1; blind matrix when too few days or no label."""
    cur = lab[i - 1]
    if cur < 0:
        return blind
    lo = 0 if window is None else max(0, i - window)
    idx = np.where(lab[lo:i] == cur)[0] + lo
    if len(idx) < MIN_REG:
        return blind
    return blend * shrunk_corr(rets[idx]) + (1 - blend) * blind


# ---------------------------------------------------------------- optimisers
def min_var(cov, cap=CAP):
    n = cov.shape[0]
    w0 = np.full(n, 1.0 / n)
    r = minimize(lambda w: w @ cov @ w, w0, jac=lambda w: 2 * cov @ w, method="SLSQP", bounds=[(0, cap)] * n,
                 constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones(n)}], options={"maxiter": 200, "ftol": 1e-12})
    w = np.clip(r.x, 0, cap)
    return w / w.sum()


def risk_parity(cov):
    """equal risk contributions (long-only): minimise 0.5 x'Sx - (1/n) sum log x, then normalise."""
    n = cov.shape[0]
    x0 = 1.0 / np.sqrt(np.diag(cov))
    r = minimize(lambda x: 0.5 * x @ cov @ x - np.log(x).sum() / n, x0, jac=lambda x: cov @ x - 1.0 / (n * x),
                 method="L-BFGS-B", bounds=[(1e-9, None)] * n, options={"maxiter": 500})
    return r.x / r.x.sum()


# ---------------------------------------------------------------- weights schedule and simulation
def decision_days(dates):
    return [i for i in range(1, len(dates)) if dates[i][:7] != dates[i - 1][:7] and i >= MIN_HIST]


def schedule(rets, dates, bucket, quad, lag_bucket=None, quad_lab=None):
    """weights for every portfolio at every decision day. lag_bucket: alternative (21-day lag) label series."""
    days = decision_days(dates)
    lab_b = bucket if lag_bucket is None else lag_bucket
    n = rets.shape[1]
    names = ["B1", "B2", "B3", "B4", "B5", "C1", "C1rp", "C1q", "C1pure", "B4roll"]
    W = {k: [] for k in names}
    for i in days:
        hist = rets[:i]
        d = rets[i - 60:i].std(axis=0, ddof=1)
        blind = shrunk_corr(hist)
        cov_b = np.outer(d, d) * blind
        rc = regime_corr(rets, lab_b, i, blind, BLEND)
        cov_c = np.outer(d, d) * rc
        cov_q = np.outer(d, d) * regime_corr(rets, quad, i, blind, BLEND)
        cov_p = np.outer(d, d) * regime_corr(rets, lab_b, i, blind, 1.0)
        cov_r = np.outer(d, d) * shrunk_corr(rets[i - 756:i])
        w60 = np.zeros(n); w60[SLEEVES.index("SPY")] = 0.6; w60[SLEEVES.index("IEF")] = 0.4
        iv = 1.0 / d
        W["B1"].append(np.full(n, 1.0 / n)); W["B2"].append(w60); W["B3"].append(iv / iv.sum())
        W["B4"].append(min_var(cov_b)); W["B5"].append(risk_parity(cov_b))
        W["C1"].append(min_var(cov_c)); W["C1rp"].append(risk_parity(cov_c))
        W["C1q"].append(min_var(cov_q)); W["C1pure"].append(min_var(cov_p)); W["B4roll"].append(min_var(cov_r))
    return days, {k: np.array(v) for k, v in W.items()}


def simulate(rets, days, Wk, costs=None):
    """net daily returns from the first decision day; weights decided at the close before the decision day, drifting between decisions."""
    cost = np.array([COST_BPS[s] for s in SLEEVES]) / 1e4 if costs is None else costs
    T = len(rets)
    out = np.zeros(T - days[0]); turn = []
    w = np.zeros(rets.shape[1]); k = 0
    for t in range(days[0], T):
        if k < len(days) and t == days[k]:
            tv = np.abs(Wk[k] - w); turn.append(tv.sum()); fee = (tv * cost).sum()
            w = Wk[k].copy(); k += 1
        else:
            fee = 0.0
        r = rets[t]
        pr = w @ r
        out[t - days[0]] = pr - fee
        w = w * (1 + r) / (1 + pr)
    return out, np.array(turn)


# ---------------------------------------------------------------- stats
def maxdd(r):
    eq = np.cumprod(1 + r, axis=-1)
    return (1 - eq / np.maximum.accumulate(eq, axis=-1)).max(axis=-1)


def ann_ret(r):
    return np.prod(1 + r, axis=-1) ** (252 / r.shape[-1]) - 1


def ann_vol(r):
    return r.std(axis=-1, ddof=1) * np.sqrt(252)


def sharpe(r, rf):
    e = r - rf
    return e.mean(axis=-1) / e.std(axis=-1, ddof=1) * np.sqrt(252)


def calmar(r):
    return ann_ret(r) / maxdd(r)


def block_idx(T, n_boot, rng, block=BLOCK):
    nb = int(np.ceil(T / block))
    st = rng.integers(0, T - block + 1, size=(n_boot, nb))
    return (st[:, :, None] + np.arange(block)).reshape(n_boot, -1)[:, :T]


def paired(a, b, stat, idx, rf=None):
    """difference stat(a) - stat(b): point estimate and 95% percentile interval over paired block resamples."""
    def f(x, i=None):
        xx = x if i is None else x[i]
        if rf is None:
            return stat(xx)
        return stat(xx, rf if i is None else rf[i])
    pt = float(f(a) - f(b))
    bs = np.concatenate([f(a, idx[c:c + 250]) - f(b, idx[c:c + 250]) for c in range(0, len(idx), 250)])
    return pt, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def claim_dd(better, worse, idx):
    """better/worse: net daily return arrays; positive diff = `better` has the smaller drawdown."""
    return paired(worse, better, lambda x: maxdd(x), idx)


def scale_to_vol(r, v=0.10):
    return r * (v / ann_vol(r))


def claim_vol(better, worse, idx):
    """positive diff = `better` has the lower annual volatility."""
    return paired(worse, better, ann_vol, idx)


def primary_claim(R, idx, metric="vol"):
    """R: dict name->net daily returns. The primary rule (PREREG Amendment 1: volatility): C1 beats B3 AND B4, both intervals above zero.
    metric="dd" is the original max-drawdown version, kept as a secondary."""
    f = claim_vol if metric == "vol" else claim_dd
    a = f(R["C1"], R["B3"], idx)
    b = f(R["C1"], R["B4"], idx)
    return (a[1] > 0 and b[1] > 0), a, b


# ---------------------------------------------------------------- descriptive diagnostics
def enb(corr):
    """effective number of bets: exp of the entropy of normalised eigenvalues of the correlation matrix (Meucci-style on PCA variance shares)."""
    ev = np.clip(np.linalg.eigvalsh(corr), 1e-12, None)
    p = ev / ev.sum()
    return float(np.exp(-(p * np.log(p)).sum()))


def div_ratio(w, vol, corr):
    cov = np.outer(vol, vol) * corr
    return float((w @ vol) / np.sqrt(w @ cov @ w))
