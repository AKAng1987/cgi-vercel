"""
hmm.py -- a 2-state Gaussian hidden Markov model fitted by Baum-Welch (EM), for daily returns.

The Renaissance idea in its simplest honest form: the market has a hidden "calm" and "stormy" state, each with its
own volatility, and switches between them with fixed odds. We use it for RISK only -- how much to hold -- never for
direction (research/latent_state showed a latent model does not beat the base rate as a flip probability).
"""
from __future__ import annotations

import numpy as np

LOG2PI = np.log(2 * np.pi)


def _emis(x: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """Per-day, per-state Gaussian density, shape (T, 2)."""
    z = (x[:, None] - mu[None, :]) / sd[None, :]
    return np.exp(-0.5 * (z ** 2 + LOG2PI)) / sd[None, :]


def fit(x: np.ndarray, iters: int = 60, tol: float = 1e-6) -> dict:
    """Baum-Welch. State 0 = calm (lower sd), state 1 = stormy. Each EM step cannot make the fit worse."""
    s = x.std()
    mu = np.array([x.mean(), x.mean()])
    sd = np.array([0.7 * s, 1.6 * s])
    A = np.array([[0.98, 0.02], [0.05, 0.95]])
    pi = np.array([0.8, 0.2])
    prev = -np.inf
    T = len(x)
    for _ in range(iters):
        B = _emis(x, mu, sd) + 1e-300
        alpha = np.empty((T, 2)); c = np.empty(T)
        alpha[0] = pi * B[0]; c[0] = alpha[0].sum(); alpha[0] /= c[0]
        for t in range(1, T):
            alpha[t] = (alpha[t - 1] @ A) * B[t]
            c[t] = alpha[t].sum(); alpha[t] /= c[t]
        beta = np.empty((T, 2)); beta[-1] = 1.0
        for t in range(T - 2, -1, -1):
            beta[t] = (A @ (B[t + 1] * beta[t + 1])) / c[t + 1]
        gamma = alpha * beta
        gamma /= gamma.sum(1, keepdims=True)
        xi = (alpha[:-1, :, None] * A[None] * (B[1:] * beta[1:])[:, None, :]) / c[1:, None, None]
        ll = np.log(c).sum()
        pi = gamma[0]
        A = xi.sum(0) / xi.sum(0).sum(1, keepdims=True)
        w = gamma.sum(0)
        mu = (gamma * x[:, None]).sum(0) / w
        sd = np.sqrt((gamma * (x[:, None] - mu) ** 2).sum(0) / w) + 1e-8
        if ll - prev < tol:
            break
        prev = ll
    if sd[0] > sd[1]:  # keep state 0 = calm
        mu, sd, pi = mu[::-1], sd[::-1], pi[::-1]
        A = A[::-1, ::-1]
    return {"mu": mu, "sd": sd, "A": A, "pi": pi, "loglik": ll}


def filter_next(x: np.ndarray, p: dict) -> np.ndarray:
    """P(stormy TOMORROW | returns up to today), for each day -- filtering only, never smoothing (no look-ahead)."""
    B = _emis(x, p["mu"], p["sd"]) + 1e-300
    a = p["pi"].copy()
    out = np.empty(len(x))
    for t in range(len(x)):
        a = a * B[t]; a /= a.sum()           # belief about today given today's return
        nxt = a @ p["A"]                      # belief about tomorrow
        out[t] = nxt[1]
        a = nxt
    return out
