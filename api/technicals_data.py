"""
technicals_data.py -- The daily breadth glance for LIVE.

Built to the user's own reading, in his priority order:

  NET NEW HIGHS (NYSE highs minus lows) is the primary.
    red   (net < 0)  -- after a sell-off; historically the best buying
                        window, held in the names stronger than the market
    white (chop)     -- the 8 and 20 day EMAs converged; take profits near
                        a cross down from the top side
    green (net > 0)  -- participation broad
    The EMAs mark the transitions: a cross DOWN from the top starts chop;
    a cross UP from below while net is still red is where risk goes back on.

  NCFD / MMTW / MMFI below 30 are the confirmations -- oversold on the
  5-day, 20-day and 50-day participation measures. They distinguish "hold
  more" from "this is a shorter-term hold".

Thresholds are 30/70, not medians: these are oscillators and a median split
washes them out (see docs/BREADTH_STUDY.md -- the 30/70 cut roughly triples
the drawdown spread).

The study's honest finding is carried through: breadth does not predict
direction (|r| <= 0.10 against SPY forward returns at 5/20/60d). What it
prices is RISK -- MMTH above 70 has meant a -1.9% drawdown over 20 days,
below 30 has meant -5.0%.
"""
from __future__ import annotations

import datetime as dt

import axis_drivers as ad

FAST, SLOW = 8, 20
OVERSOLD, OVERBOUGHT = 30.0, 70.0
GAUGES = [
    ("NCFD", "Nasdaq above 5d"),
    ("MMFD", "S&P above 5d"),
    ("MMTW", "S&P above 20d"),
    ("MMFI", "S&P above 50d"),
    ("MMTH", "S&P above 200d"),
    ("NCTH", "Nasdaq above 200d"),
]


def _load(sym: str) -> dict[str, float]:
    try:
        d, c = ad._load_close(sym)
        return {k: v for k, v in zip(d, c) if v is not None}
    except Exception:
        return {}


def _ema(vals: list[float], n: int) -> list[float]:
    k = 2.0 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def build_technicals_response() -> dict:
    hi, lo = _load("HIGN"), _load("LOWN")
    dates = sorted(set(hi) & set(lo))
    net = [hi[d] - lo[d] for d in dates]
    f, s = _ema(net, FAST), _ema(net, SLOW)
    i = len(dates) - 1

    above = [f[j] > s[j] for j in range(len(dates))]
    cross_i, cross_dir = None, None
    for j in range(len(dates) - 1, 0, -1):
        if above[j] != above[j - 1]:
            cross_i, cross_dir = j, ("up" if above[j] else "down")
            break
    days_since = (dt.date.fromisoformat(dates[-1]) - dt.date.fromisoformat(dates[cross_i])).days if cross_i else None

    # colour, in the user's language
    colour = "red" if net[i] < 0 else "green"
    spread = f[i] - s[i]
    scale = max(abs(x) for x in net[-250:]) or 1.0
    chop = abs(spread) / scale < 0.05
    if chop:
        colour = "white"

    if colour == "red" and cross_dir == "up":
        state = "risk-on window — net still negative but the 8 has crossed up from below"
    elif cross_dir == "down" and not chop:
        state = "crossed down from the top — chop starts here, take profits near this point"
    elif colour == "white":
        state = "chop — the EMAs have converged"
    elif colour == "red":
        state = "red — after a sell-off; the buying window, held in names stronger than the market"
    else:
        state = "green — participation broad"

    gauges = []
    for sym, label in GAUGES:
        g = _load(sym)
        if not g:
            continue
        gd = sorted(g)
        v = g[gd[-1]]
        prev = g[gd[-2]] if len(gd) > 1 else None
        gauges.append({
            "symbol": sym, "label": label, "as_of": gd[-1],
            "value": round(v, 1),
            "change": round(v - prev, 1) if prev is not None else None,
            "zone": "oversold" if v < OVERSOLD else "overbought" if v > OVERBOUGHT else "neutral",
            "days_below_30_of_60": sum(1 for d in gd[-60:] if g[d] < OVERSOLD),
        })

    oversold = [g["symbol"] for g in gauges if g["zone"] == "oversold"]
    return {
        "as_of": dates[-1],
        "net_new_highs": {
            "value": round(net[i], 1),
            "ema_fast": round(f[i], 1),
            "ema_slow": round(s[i], 1),
            "spread": round(spread, 1),
            "colour": colour,
            "state": state,
            "last_cross": {"date": dates[cross_i], "direction": cross_dir, "days_ago": days_since} if cross_i else None,
            "series": [{"date": dates[j], "net": round(net[j], 1),
                        "fast": round(f[j], 1), "slow": round(s[j], 1)}
                       for j in range(max(0, len(dates) - 120), len(dates))],
        },
        "gauges": gauges,
        "oversold": oversold,
        "confirmation": (
            f"{len(oversold)} of {len(gauges)} participation gauges below 30"
            + (f" ({', '.join(oversold)})" if oversold else "")
        ),
        "caveat": ("Breadth prices risk, not direction: |r| <= 0.10 against SPY forward "
                   "returns. MMTH above 70 has meant -1.9% of 20-day drawdown, below 30 -5.0%."),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
