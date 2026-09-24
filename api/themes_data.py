"""
themes_data.py -- Theme detection for the LIVE brief (layer 2).

The regime model moves on a weeks-to-months clock. If the front page shows
only regime output it asks the user to re-decide constantly, which is the
"I keep flipping" problem. The fix is a slower layer on top: themes, which
are promoted deliberately and then held for their horizon.

This module does the *discovery* half mechanically. For each theme proxy:

  RS          = ticker / SPY
  trend       = 200-day EMA of RS
  onset       = the start of the current run -- the earliest day from which
                RS has stayed above its trend on at least 80% of days since
                (a strict "every day above" test would restart the clock on
                every one-day dip, which is how you end up calling a mature
                theme "new")
  age         = days since onset, which is what tells you whether a theme
                has runway left or is already consensus

Pure arithmetic, no model, no LLM -- it is a table to read, not a forecast.
A theme with no active run is reported as such: that is the most useful
output when a narrative is loud but absent from the price.

Promotion to a standing theme (layer 1) stays a human decision, reviewed
monthly against this shortlist.
"""
from __future__ import annotations

import datetime as dt

import axis_drivers as ad

BENCH = "SPY"
TREND_DAYS = 200
PERSISTENCE = 0.80     # share of days since onset that RS must be above trend
MIN_HISTORY = 400

# Theme -> proxies, ordered so the leading indicator comes first where the
# sequence matters (miners lead the metal: COPX turned 68 days before CPER,
# GDX is running while GLD is not -- that gap is itself the signal).
THEMES: dict[str, list[str]] = {
    "AI": ["AIQ", "ROBO", "BOTZ"],
    "semis / memory": ["SMH", "SOXX"],
    "cloud / software": ["WCLD", "SKYY", "FDN"],
    "cyber": ["CIBR", "HACK"],
    "copper": ["COPX", "CPER"],
    "gold": ["GDX", "GDXJ", "GLD"],
    "silver": ["SIL", "SLV"],
    "steel / metals": ["SLX", "XME"],
    "uranium / nuclear": ["URA", "NLR"],
    "power / grid": ["GRID", "XLU"],
    "defense": ["ITA", "XAR"],
    "energy: upstream": ["XOP", "IEO", "OIH"],
    "energy: refiners": ["CRAK"],
    "energy: midstream": ["MLPX"],
    "biotech / healthcare": ["IBB", "IHI", "XLV"],
    "banks": ["KBE", "KRE"],
    "retail / consumer": ["XRT", "IBUY", "XLY"],
    "homebuilders": ["XHB"],
    "real estate": ["VNQ", "XLRE"],
    "shipping / logistics": ["SEA", "IYT"],
    "infrastructure": ["IGF"],
    "EV / battery": ["IDRV", "KARS", "BATT"],
    "solar / clean": ["TAN", "ICLN", "FAN"],
    "crypto equities": ["BLOK", "BITO"],
    "China": ["KWEB", "FXI"],
    "Japan": ["EWJ"],
    "agriculture": ["DBA", "CORN", "WEAT"],
}


def _ema(vals: list[float], n: int) -> list[float]:
    k = 2.0 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _load(sym: str) -> dict[str, float]:
    try:
        d, c = ad._load_close(sym)
        return {k: v for k, v in zip(d, c) if v}
    except Exception:
        return {}


def _run(px: dict[str, float], bench: dict[str, float]) -> dict:
    d = sorted(set(px) & set(bench))
    if len(d) < MIN_HISTORY:
        return {"status": "insufficient history", "n_days": len(d)}
    rs = [px[x] / bench[x] for x in d]
    trend = _ema(rs, TREND_DAYS)
    above = [rs[i] > trend[i] for i in range(len(d))]

    if not above[-1]:
        # how long has it been out of favour?
        i = len(d) - 1
        while i >= 0 and not above[i]:
            i -= 1
        since = d[i] if i >= 0 else None
        return {"status": "no active run", "last_above": since,
                "rs_vs_trend_pct": round((rs[-1] / trend[-1] - 1) * 100, 1)}

    start = len(d) - 1
    while start > TREND_DAYS:
        seg = above[start - 1:]
        if sum(seg) / len(seg) >= PERSISTENCE:
            start -= 1
        else:
            break
    age = (dt.date.fromisoformat(d[-1]) - dt.date.fromisoformat(d[start])).days
    seg = above[start:]
    return {
        "status": "running",
        "onset": d[start],
        "age_days": age,
        "rs_gain_pct": round((rs[-1] / rs[start] - 1) * 100, 1),
        "price_gain_pct": round((px[d[-1]] / px[d[start]] - 1) * 100, 1),
        "persistence": round(sum(seg) / len(seg), 3),
        "rs_vs_trend_pct": round((rs[-1] / trend[-1] - 1) * 100, 1),
    }


def build_themes_response() -> dict:
    bench = _load(BENCH)
    out = []
    for theme, syms in THEMES.items():
        legs = []
        for s in syms:
            px = _load(s)
            if not px:
                legs.append({"symbol": s, "status": "not in price-history"})
                continue
            legs.append({"symbol": s, **_run(px, bench)})
        running = [l for l in legs if l.get("status") == "running"]
        lead = min(running, key=lambda l: l["onset"]) if running else None
        out.append({
            "theme": theme,
            "legs": legs,
            "n_running": len(running),
            "n_legs": len([l for l in legs if l.get("status") in ("running", "no active run")]),
            "onset": lead["onset"] if lead else None,
            "age_days": lead["age_days"] if lead else None,
            "lead_symbol": lead["symbol"] if lead else None,
            # a theme where the leading proxy runs and the lagging one does not
            # is early; one where every leg runs is consensus
            "stage": None if not lead else (
                "emerging" if lead["age_days"] <= 120 else
                "established" if lead["age_days"] <= 400 else "mature"),
        })
    out.sort(key=lambda t: (t["age_days"] is None, t["age_days"] or 0))
    return {
        "as_of": max(bench) if bench else None,
        "benchmark": BENCH,
        "method": (f"RS = ticker/{BENCH}; trend = {TREND_DAYS}d EMA of RS; onset = earliest day "
                   f"from which RS stayed above trend on >= {int(PERSISTENCE * 100)}% of days since."),
        "note": ("Discovery only. Promotion to a standing theme is a monthly human decision; "
                 "once promoted a theme is held for its horizon rather than re-decided daily."),
        "themes": out,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
