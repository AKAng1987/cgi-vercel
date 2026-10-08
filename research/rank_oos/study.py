"""
study.py -- do the regime best/worst-20 lists predict anything out of sample? Offline; ships nothing.

For every past episode of every C x G regime, rank instruments using ONLY earlier episodes of that same regime,
then measure that episode's return of the top 20 minus the bottom 20. Rankings compared:
  RAW     average return over earlier episodes
  SHRUNK  the same average pulled toward the cross-sectional mean by its own sample size (empirical Bayes)
  EDGE    avg high / |avg low| -- what the BACKTEST page ranks by today (backtest_data.compute_stats)
Episodes are the unit of evidence (days inside one episode are not independent), bootstrapped over episodes.
"""
from __future__ import annotations

import numpy as np

MIN_PRIOR_EPISODES = 3     # an episode is scored only if its regime has this many earlier episodes
MIN_PRIOR_OBS = 2          # an instrument is ranked only with this many earlier occurrences in the regime
TOP_N = 20


def _scores(prior: dict[str, list[dict]]) -> dict[str, dict[str, float]]:
    """prior: {ticker: [occurrence, ...]} -> {"RAW": {t: s}, "SHRUNK": {...}, "EDGE": {...}}."""
    m = {t: np.mean([o["return_pct"] for o in occ]) for t, occ in prior.items()}
    n = {t: len(occ) for t, occ in prior.items()}
    var_within = np.mean([np.var([o["return_pct"] for o in occ], ddof=1) for occ in prior.values()])
    means = np.array(list(m.values()))
    g = means.mean()
    tau2 = max(means.var() - np.mean([var_within / n[t] for t in m]), 1e-9)
    shrunk = {t: g + tau2 / (tau2 + var_within / n[t]) * (m[t] - g) for t in m}
    edge = {}
    for t, occ in prior.items():
        hi = np.mean([o["high_pct"] for o in occ]); lo = np.mean([o["low_pct"] for o in occ])
        edge[t] = hi / abs(lo) if lo < 0 else np.nan
    return {"RAW": m, "SHRUNK": shrunk, "EDGE": edge}


def episodes(tickers: dict) -> list[tuple[str, str]]:
    seen = {(ck, o["start_date"]) for e in tickers.values() for ck, occ in e["combos"].items() for o in occ}
    return sorted(seen)


def run(tickers: dict) -> dict:
    by_combo: dict[str, list[str]] = {}
    for ck, start in episodes(tickers):
        by_combo.setdefault(ck, []).append(start)
    rows = []  # one per scored episode: {method: spread, method_ic: ic}
    for ck, starts in by_combo.items():
        for k, start in enumerate(starts):
            if k < MIN_PRIOR_EPISODES:
                continue
            prior, now = {}, {}
            for t, e in tickers.items():
                occ = e["combos"].get(ck, [])
                p = [o for o in occ if o["start_date"] < start]
                cur = [o for o in occ if o["start_date"] == start]
                if len(p) >= MIN_PRIOR_OBS and cur:
                    prior[t] = p
                    now[t] = cur[0]["return_pct"]
            if len(prior) < 10:
                continue
            sc = _scores(prior)
            row = {"combo": ck, "start": start, "n": len(prior)}
            for meth, s in sc.items():
                ok = [t for t in s if not np.isnan(s[t])]
                k2 = min(TOP_N, len(ok) // 2)
                order = sorted(ok, key=lambda t: s[t], reverse=True)
                top, bot = order[:k2], order[-k2:]
                row[meth] = float(np.mean([now[t] for t in top]) - np.mean([now[t] for t in bot]))
                x = np.argsort(np.argsort([s[t] for t in ok])); y = np.argsort(np.argsort([now[t] for t in ok]))
                row[meth + "_ic"] = float(np.corrcoef(x, y)[0, 1])
            rows.append(row)
    return {"rows": rows, "summary": summarise(rows)}


def boot_mean(v: np.ndarray, reps: int = 4000, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    ms = np.array([v[rng.integers(0, len(v), len(v))].mean() for _ in range(reps)])
    return {"mean": float(v.mean()), "ci95": [float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))],
            "share_positive": float((v > 0).mean())}


def summarise(rows: list[dict]) -> dict:
    out = {"episodes_scored": len(rows)}
    for meth in ("RAW", "SHRUNK", "EDGE"):
        out[meth] = {"spread_pct": boot_mean(np.array([r[meth] for r in rows])),
                     "rank_ic": boot_mean(np.array([r[meth + "_ic"] for r in rows]))}
    out["SHRUNK_minus_RAW"] = boot_mean(np.array([r["SHRUNK"] - r["RAW"] for r in rows]))
    out["RAW_minus_EDGE"] = boot_mean(np.array([r["RAW"] - r["EDGE"] for r in rows]))
    return out
