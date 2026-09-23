"""
technicals_data.py -- TECHNICALS factor: breadth and leadership.

CONDITIONING, not a Markov axis. Breadth does not predict direction --
over 4,969 aligned days every measure correlates |r| <= 0.10 with SPY
forward returns. What it prices is *risk*: how much drawdown a dip has
historically cost, given where structural participation sits.

Series (TradingView INDEX:, loaded into price-history):
  MMFD / MMTW / MMFI / MMTH   S&P 500 % above 5 / 20 / 50 / 200-day MA
  NCFD / NCTH                 Nasdaq Composite % above 5 / 200-day MA
  HIGN / LOWN                 NYSE new 52-week highs / lows
Leadership: QQQ/XLP (offense vs defense) and XLY/XLP, 20-day change.

Thresholds are 30/70, not medians -- these are oscillators and a median
split washes them out (the 30/70 cut roughly triples the spread).

Headline read: MMTH's zone, because that is where the study found the
separation, plus the leadership split that distinguishes a buyable
washout from a real one when MMTH is broken.
"""
from __future__ import annotations

import datetime as dt
import statistics as st

import axis_drivers as ad

HORIZONS = (5, 20, 60)
FAST, SLOW = 8, 20  # net-new-high EMAs (Caruso)

SERIES = {
    "MMFD": ("S&P above 5d", "sp"), "MMTW": ("S&P above 20d", "sp"),
    "MMFI": ("S&P above 50d", "sp"), "MMTH": ("S&P above 200d", "sp"),
    "NCFD": ("Nasdaq above 5d", "ndx"), "NCTH": ("Nasdaq above 200d", "ndx"),
}


def _load(sym: str) -> dict[str, float]:
    d, c = ad._load_close(sym)
    return dict(zip(d, c))


def _ema(vals: list[float], n: int) -> list[float]:
    k = 2.0 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _zone(v: float) -> str:
    return "oversold" if v < 30 else "overbought" if v > 70 else "neutral"


def _stats(idx: list[int], fwd: dict, dd: dict) -> dict:
    out = {}
    for h in HORIZONS:
        rs = [fwd[h][i] for i in idx if fwd[h][i] is not None]
        ds = [dd[h][i] for i in idx if dd[h][i] is not None]
        out[f"{h}d"] = None if not rs else {
            "n": len(rs),
            "up_rate": round(sum(1 for r in rs if r > 0) / len(rs), 3),
            "mean_return": round(st.mean(rs), 2),
            "mean_drawdown": round(st.mean(ds), 2) if ds else None,
        }
    return out


def build_technicals_response() -> dict:
    raw = {s: _load(s) for s in SERIES}
    for s in ("SPY", "QQQ", "XLP", "HIGN", "LOWN"):
        raw[s] = _load(s)
    core = ("MMTW", "MMTH", "SPY", "QQQ", "XLP")
    dates = sorted(d for d in set.intersection(*[set(raw[s]) for s in core])
                   if all(raw[s].get(d) for s in core))
    px = [raw["SPY"][d] for d in dates]
    fwd = {h: [((px[i + h] / px[i] - 1) * 100 if i + h < len(px) else None) for i in range(len(px))] for h in HORIZONS}
    dd = {h: [((min(px[i + 1:i + h + 1]) / px[i] - 1) * 100 if i + h < len(px) else None) for i in range(len(px))] for h in HORIZONS}

    mmth = [raw["MMTH"][d] for d in dates]
    lead = [None if i < 20 else ((raw["QQQ"][d] / raw["XLP"][d]) / (raw["QQQ"][dates[i - 20]] / raw["XLP"][dates[i - 20]]) - 1) * 100
            for i, d in enumerate(dates)]

    # --- current readings -------------------------------------------------
    last = dates[-1]
    gauges = []
    for sym, (label, fam) in SERIES.items():
        s = raw[sym]
        if last not in s and not s:
            continue
        ds = sorted(s)
        d0 = ds[-1]
        v = s[d0]
        prev = s[ds[-2]] if len(ds) > 1 else None
        below30 = sum(1 for d in ds[-60:] if s[d] < 30)
        gauges.append({"symbol": sym, "label": label, "family": fam, "as_of": d0,
                       "value": round(v, 2), "change": round(v - prev, 2) if prev is not None else None,
                       "zone": _zone(v), "days_below_30_of_60": below30})

    # --- net new highs ----------------------------------------------------
    nnh_dates = sorted(set(raw["HIGN"]) & set(raw["LOWN"]))
    net = [raw["HIGN"][d] - raw["LOWN"][d] for d in nnh_dates]
    e_f, e_s = _ema(net, FAST), _ema(net, SLOW)
    nnh = {"as_of": nnh_dates[-1], "net": round(net[-1], 1),
           "ema_fast": round(e_f[-1], 1), "ema_slow": round(e_s[-1], 1),
           "fast_above_slow": e_f[-1] > e_s[-1],
           "note": "the 8/20 cross did not separate on index direction in the study "
                   "(65% up over 20d above vs 66% below, 251 crosses each way) -- shown as context"}

    # --- the tables that did separate ------------------------------------
    by_zone = []
    for label, sel in (("overbought (>70)", lambda i: mmth[i] > 70),
                       ("neutral (30-70)", lambda i: 30 <= mmth[i] <= 70),
                       ("oversold (<30)", lambda i: mmth[i] < 30)):
        idx = [i for i in range(len(dates)) if sel(i)]
        by_zone.append({"zone": label, "n": len(idx), **{"h": _stats(idx, fwd, dd)}})

    washout = []
    for ml, msel in (("MMTH<30", lambda i: mmth[i] < 30), ("MMTH 30-70", lambda i: 30 <= mmth[i] <= 70),
                     ("MMTH>70", lambda i: mmth[i] > 70)):
        for ll, lsel in (("offense leading", lambda i: lead[i] is not None and lead[i] > 0),
                         ("defense leading", lambda i: lead[i] is not None and lead[i] <= 0)):
            idx = [i for i in range(len(dates)) if msel(i) and lsel(i)]
            if len(idx) < 20:
                continue
            washout.append({"structural": ml, "leadership": ll, "n": len(idx), "h": _stats(idx, fwd, dd)})

    i = len(dates) - 1
    cur_zone = _zone(mmth[i])
    cur_lead = "offense leading" if (lead[i] or 0) > 0 else "defense leading"
    match = next((w for w in washout
                  if w["leadership"] == cur_lead
                  and w["structural"] == ("MMTH<30" if cur_zone == "oversold" else "MMTH>70" if cur_zone == "overbought" else "MMTH 30-70")), None)

    return {
        "as_of": last,
        "window": {"start": dates[0], "end": dates[-1], "n_days": len(dates)},
        "gauges": gauges,
        "net_new_highs": nnh,
        "leadership": {"qqq_xlp_20d": round(lead[i], 2) if lead[i] is not None else None, "state": cur_lead},
        "structural": {"mmth": round(mmth[i], 2), "zone": cur_zone},
        "today_bucket": match,
        "by_structural_zone": by_zone,
        "washout_table": washout,
        "caveat": "Breadth prices risk, not direction: over this window every measure "
                  "correlates |r| <= 0.10 with SPY forward returns, while the drawdown "
                  "spread between MMTH>70 and MMTH<30 is roughly 3x.",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
