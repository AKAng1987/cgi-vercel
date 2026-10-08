"""
study.py -- when speculators are crowded (COT index at a 3-year extreme), how long until price turns against them,
does waiting for price to confirm help, and does trend strength (ADX) or volatility (ATR%) tell turns from run-overs?
Offline; ships nothing.

  crowd sign   +1 crowded long (index >= HI), -1 crowded short (index <= LO); first week of each episode only
  dated        the Friday the report is published (data as of Tuesday), next trading day -- never earlier
  against      return in the direction AGAINST the crowd, minus the instrument's own average move over the same
               horizon (so a market that simply trends up all sample does not count as a 'turn')
  turn         first close beyond the prior 20-day extreme against the crowd (a 4-week breakout the other way)
  confirmed    enter at that breakout instead of at the report; compared with ALL such breakouts (no COT)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

HI, LO = 95.0, 5.0
LOOKBACK_W = 156
BREAK_N = 20
HORIZONS = (10, 20, 40, 65)     # trading days: ~2, 4, 8, 13 weeks
TURN_WINDOW = 65


def cot_index(spec: pd.Series) -> pd.Series:
    """3-year index of speculator net position, using only weeks up to each date."""
    lo = spec.rolling(LOOKBACK_W, min_periods=104).min()
    hi = spec.rolling(LOOKBACK_W, min_periods=104).max()
    return 100 * (spec - lo) / (hi - lo)


def events(idx: pd.Series) -> pd.DataFrame:
    """First week of each extreme episode, dated at publication (Tuesday + 3 days)."""
    side = pd.Series(0, index=idx.index)
    side[idx >= HI] = 1
    side[idx <= LO] = -1
    start = (side != 0) & (side != side.shift(1))
    ev = pd.DataFrame({"crowd": side[start], "index": idx[start]})
    ev.index = ev.index + pd.Timedelta(days=3)
    return ev


def indicators(df: pd.DataFrame) -> pd.DataFrame:
    """ADX(14) and ATR%(14) relative to its own 1-year median, from daily high/low/close (Wilder)."""
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False).mean()
    up, dn = h.diff(), -l.diff()
    pdm = up.where((up > dn) & (up > 0), 0.0)
    ndm = dn.where((dn > up) & (dn > 0), 0.0)
    pdi = 100 * pdm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    ndi = 100 * ndm.ewm(alpha=1 / 14, adjust=False).mean() / atr
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi)
    adx = dx.ewm(alpha=1 / 14, adjust=False).mean()
    atrp = atr / c
    return pd.DataFrame({"adx": adx, "atr_rel": atrp / atrp.rolling(252, min_periods=120).median()})


def _fwd(c: pd.Series, i: int, h: int) -> float:
    return c.iloc[i + h] / c.iloc[i] - 1 if i + h < len(c) else np.nan


def breakouts(c: pd.Series, direction: int) -> pd.Series:
    """True where the close breaks the prior BREAK_N-day extreme in `direction` (+1 up, -1 down)."""
    if direction > 0:
        return c > c.shift(1).rolling(BREAK_N).max()
    return c < c.shift(1).rolling(BREAK_N).min()


def analyse(px: pd.DataFrame, ev: pd.DataFrame, sign: int) -> list[dict]:
    """px: daily high/low/close (some may lack high/low); ev: events; sign maps contract-long to price-up."""
    c = px["close"].dropna()
    ind = indicators(px) if {"high", "low"} <= set(px.columns) and px["high"].notna().mean() > 0.9 else None
    mean_h = {h: c.pct_change(h).mean() for h in HORIZONS}
    rows = []
    for d, e in ev.iterrows():
        pos = c.index.searchsorted(d)
        if pos >= len(c) - 1 or pos < BREAK_N + 1:
            continue
        against = -int(e["crowd"]) * sign          # +1: price should rise against this crowd
        r = {"date": c.index[pos], "crowd": int(e["crowd"]), "against": against}
        for h in HORIZONS:
            f = _fwd(c, pos, h)
            r[f"ev_{h}"] = against * (f - mean_h[h]) if not np.isnan(f) else np.nan
        brk = breakouts(c, against)
        hits = np.where(brk.iloc[pos + 1:pos + 1 + TURN_WINDOW].to_numpy())[0]
        r["days_to_turn"] = int(hits[0] + 1) if len(hits) else np.nan
        if len(hits):
            j = pos + 1 + int(hits[0])
            for h in HORIZONS:
                f = _fwd(c, j, h)
                r[f"conf_{h}"] = against * (f - mean_h[h]) if not np.isnan(f) else np.nan
        if ind is not None and c.index[pos] in ind.index:
            r["adx"] = float(ind.loc[c.index[pos], "adx"])
            r["atr_rel"] = float(ind.loc[c.index[pos], "atr_rel"])
        rows.append(r)
    return rows


def breakout_baseline(px: pd.DataFrame, sign_dirs=(1, -1)) -> list[dict]:
    """Every 20-day breakout (either direction), first day of each, with demeaned forward returns in its direction."""
    c = px["close"].dropna()
    mean_h = {h: c.pct_change(h).mean() for h in HORIZONS}
    out = []
    for d in sign_dirs:
        b = breakouts(c, d)
        first = b & ~b.shift(1, fill_value=False)
        for pos in np.where(first.to_numpy())[0]:
            r = {"date": c.index[pos]}
            for h in HORIZONS:
                f = _fwd(c, pos, h)
                r[f"brk_{h}"] = d * (f - mean_h[h]) if not np.isnan(f) else np.nan
            out.append(r)
    return out


def random_turn_baseline(c: pd.Series, n: int = 400, seed: int = 0) -> np.ndarray:
    """Days to a 20-day breakout in a random direction from random dates (what 'a turn within N days' means by chance)."""
    rng = np.random.default_rng(seed)
    c = c.dropna()
    out = []
    for _ in range(n):
        pos = int(rng.integers(BREAK_N + 1, len(c) - TURN_WINDOW - 1))
        d = int(rng.choice([1, -1]))
        hits = np.where(breakouts(c, d).iloc[pos + 1:pos + 1 + TURN_WINDOW].to_numpy())[0]
        out.append(hits[0] + 1 if len(hits) else np.nan)
    return np.array(out, dtype=float)


def week_boot(df: pd.DataFrame, col: str, reps: int = 2000, seed: int = 0) -> dict:
    """Mean of `col` with a bootstrap over event WEEKS (events in the same week are not independent)."""
    d = df[["date", col]].dropna()
    if len(d) < 10:
        return {"mean": float("nan"), "ci95": [float("nan")] * 2, "n": int(len(d))}
    d = d.assign(wk=pd.to_datetime(d["date"]).dt.to_period("W"))
    groups = [g[col].to_numpy() for _, g in d.groupby("wk")]
    rng = np.random.default_rng(seed)
    ms = []
    for _ in range(reps):
        pick = rng.integers(0, len(groups), len(groups))
        ms.append(np.concatenate([groups[i] for i in pick]).mean())
    return {"mean": float(d[col].mean()), "ci95": [float(np.percentile(ms, 2.5)), float(np.percentile(ms, 97.5))],
            "n": int(len(d)), "hit": float((d[col] > 0).mean())}
