"""
latent.py -- a one-factor Kalman filter over the drivers of one axis, and the
logistic bridge from the filtered factor to P(flip). numpy only.

THE MODEL (deliberately small -- see parameter_count)
  y_tk = lam_k * f_t + e_tk,   e_tk ~ N(0, R_k)      k = 1..K drivers, standardized
  f_t  = phi * f_{t-1} + eta_t, var(f) = 1 (stationary)

  lam_k  leading eigenvector of the pairwise-complete correlation matrix
  R_k    1 - lam_k^2 (floored)  -- standardized, so the residual is what is left
  phi    lag-1 autocorrelation of the first-component score
That is K + 1 estimated numbers, no free noise variances: with ~100-200 windows a
factor model that fits its own R and Q will fit noise beautifully.

WHY A KALMAN FILTER AND NOT JUST AN AVERAGE
Drivers arrive at mixed frequencies and each window has a ragged edge: some
readings are missing. The filter takes whichever are observed at each window and
weights them by lam_k^2 / R_k, which an equal-weight tercile table cannot do.

THE BRIDGE
  P(flip) = sigmoid(b0 + b1*s + b2*f + b3*f*s),  s = current state (0/1)
ridge-regularised, 4 parameters. The factor's sign is arbitrary and absorbed by
b2/b3.
"""
from __future__ import annotations

import numpy as np

LAM_CLIP = 0.95
R_FLOOR = 0.05
MIN_PAIRS = 20


def fit_standardizer(Y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = np.nanmean(Y, axis=0)
    sd = np.nanstd(Y, axis=0)
    sd = np.where((sd == 0) | np.isnan(sd), 1.0, sd)
    return np.nan_to_num(mu), sd


def _pairwise_corr(Z: np.ndarray) -> np.ndarray:
    K = Z.shape[1]
    C = np.eye(K)
    for i in range(K):
        for j in range(i + 1, K):
            m = ~np.isnan(Z[:, i]) & ~np.isnan(Z[:, j])
            if m.sum() >= MIN_PAIRS and Z[m, i].std() > 0 and Z[m, j].std() > 0:
                C[i, j] = C[j, i] = float(np.corrcoef(Z[m, i], Z[m, j])[0, 1])
    return C


def fit_factor(Y_train: np.ndarray) -> dict:
    """Loadings, residual variances and persistence from TRAINING rows only."""
    mu, sd = fit_standardizer(Y_train)
    Z = (Y_train - mu) / sd
    C = _pairwise_corr(Z)
    w, V = np.linalg.eigh(C)
    v, ev = V[:, -1], max(w[-1], 1e-9)
    lam = np.clip(v * np.sqrt(ev), -LAM_CLIP, LAM_CLIP)
    if lam.sum() < 0:                       # fix the sign: majority of drivers load positively
        lam = -lam
    R = np.maximum(1.0 - lam ** 2, R_FLOOR)
    # persistence from a simple weighted score
    num = np.nansum(Z * lam, axis=1)
    den = np.nansum(np.where(np.isnan(Z), 0.0, lam ** 2), axis=1)
    ok = den > 0
    score = np.where(ok, num / np.where(ok, den, 1.0), np.nan)
    a, b = score[:-1], score[1:]
    m = ~np.isnan(a) & ~np.isnan(b)
    phi = float(np.clip(np.corrcoef(a[m], b[m])[0, 1], 0.0, 0.95)) if m.sum() >= MIN_PAIRS else 0.0
    return {"mu": mu, "sd": sd, "lam": lam, "R": R, "phi": phi, "K": Y_train.shape[1]}


def parameter_count(fit: dict) -> int:
    return fit["K"] + 1                      # K loadings + phi; R and Q are derived


def filter_factor(Y: np.ndarray, fit: dict) -> tuple[np.ndarray, np.ndarray]:
    """Causal Kalman filter: f_{t|t} and its variance, using only rows <= t."""
    Z = (Y - fit["mu"]) / fit["sd"]
    lam, R, phi = fit["lam"], fit["R"], fit["phi"]
    q = 1.0 - phi ** 2
    f, P = 0.0, 1.0
    fs, Ps = np.empty(len(Z)), np.empty(len(Z))
    for t in range(len(Z)):
        if t > 0:
            f, P = phi * f, phi * phi * P + q
        o = ~np.isnan(Z[t])
        if o.any():
            info = 1.0 / P + np.sum(lam[o] ** 2 / R[o])
            P_new = 1.0 / info
            f = P_new * (f / P + np.sum(lam[o] * Z[t, o] / R[o]))
            P = P_new
        fs[t], Ps[t] = f, P
    return fs, Ps


# ── logistic bridge ─────────────────────────────────────────────────────────

def _design(f: np.ndarray, s: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones_like(f), s, f, f * s])


def fit_logistic(f: np.ndarray, s: np.ndarray, y: np.ndarray, ridge: float = 1.0, iters: int = 50) -> np.ndarray:
    X = _design(f, s.astype(float))
    b = np.zeros(X.shape[1])
    pen = np.diag([0.0] + [ridge] * (X.shape[1] - 1))
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ b, -30, 30)))
        W = p * (1 - p) + 1e-9
        g = X.T @ (y - p) - pen @ b
        H = X.T @ (X * W[:, None]) + pen
        step = np.linalg.solve(H, g)
        b = b + step
        if np.max(np.abs(step)) < 1e-8:
            break
    return b


def predict_logistic(b: np.ndarray, f: np.ndarray, s: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(_design(f, s.astype(float)) @ b, -30, 30)))
