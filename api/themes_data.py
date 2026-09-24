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

# Megatrends are structurally different from rotations: multi-year secular
# build-outs whose runs are not drawn from the same distribution as a sector
# rotation. The survival curve below is measured over rotational runs, so
# applying it to a megatrend reads "0% runway" when what it actually means is
# "this is the longest run in the sample" -- true, but not a warning. For
# these the runway figure is reported as context, not as a countdown.
MEGATRENDS = {"AI", "semis / memory"}

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
    # DXJ (yen-hedged) leads: EWJ is unhedged USD and hands the currency back,
    # which is why the detector read Japan as 33 days old when Japan in yen had
    # been strong for a year. Measured over the Takaichi window: Japan +13.8%
    # in yen vs EWJ +5.3% in USD. The gap between the two legs IS the currency.
    "Japan": ["DXJ", "EWJ"],
    # Korea is the memory trade -- Samsung and SK Hynix are about half the
    # index, so EWY is the cleanest liquid DRAM proxy available at ETF level.
    "Korea / DRAM": ["EWY"],
    "agriculture": ["DBA", "CORN", "WEAT"],
}


# ---------------------------------------------------------------------------
# Layer 1: standing themes. Edited by hand, deliberately -- this is the slow
# layer whose whole purpose is NOT to change when the regime rotates. Review
# monthly against the detector below; promote or drop, then hold.
STANDING: list[dict] = [
    {
        "name": "Hyperscaler capex — the $1T build-out",
        "since": "2026-09-24",
        "horizon": "12 months",
        "review_on": "2026-10-24",
        "thesis": (
            "Mag 7 spending on the AI layer cake: energy, chips, infrastructure, "
            "models, applications. Read the layers separately, because they are "
            "not moving together. "
            "APPLICATIONS are starting to emerge inside the software names -- CRM "
            "and TWLO building on DDOG -- and this is the layer where a "
            "fundamentals model is needed to tell real revenue from press release. "
            "MODELS are about to become listable: SPCX is the first IPO, with "
            "OpenAI and Anthropic expected to follow. "
            "INFRASTRUCTURE (datacentre build-outs) appears to have slowed. "
            "CHIPS are splitting -- AMD is still working while NVDA and others "
            "have started to decelerate. "
            "ENERGY on the utilities side has fallen over the last few months. "
            "Held for the capex cycle, not the quarter. "
            "Caveat carried deliberately: the regime is C3 (liquidity tightening, "
            "credit easing) and the holding period shortens with each further "
            "hike -- rate rises compress the multiple on long-duration growth "
            "even when the capex itself is unchanged."
        ),
        # Tracked proxies -- what CGI actually monitors (ETF-level by design).
        "expressions": ["SMH", "WCLD", "SKYY", "CIBR", "GRID", "XLU"],
        # Named equities are the user's expression list, not tracked series:
        # onboarding individual stocks is unbounded scope and would sidetrack
        # the ETF-level architecture.
        "watchlist": ["AMD", "TWLO", "DDOG", "CRM", "PLTR", "PANW"],
        "exit_rule": (
            "Any of: lead proxy RS below its 200d trend for 6 consecutive weeks; "
            "oil sustained higher driving CPI and a faster hiking path; or the "
            "capex guidance itself cut at earnings. Watch the layers separately -- "
            "infrastructure slowing and utilities falling are already partial "
            "breaks, not yet a thesis break."
        ),
    },
    {
        "name": "Energy pricing power — routes and shortage",
        "since": "2026-09-24",
        "horizon": "while the disruptions persist",
        "review_on": "2026-10-24",
        "thesis": (
            "Two separate legs on the oil side. SHIPPING: additional trade routes "
            "and Middle East disruption mean vessels are repositioned and voyages "
            "lengthened, so BDI and SEA hold pricing power for as long as those "
            "conditions run. PRODUCERS: XLE and XOP have pricing power through "
            "shortage, which feeds directly back into inflation and therefore into "
            "the hiking path -- making this theme the main risk to the capex theme "
            "above rather than an independent bet. Event-driven and not repeatable: "
            "this is narrative, held on the condition persisting, not a factor."
        ),
        "expressions": ["SEA", "XLE", "XOP", "IEO", "CRAK"],
        "watchlist": ["BDI"],
        "exit_rule": (
            "Routes normalise or the conflict de-escalates; BDI rolls over; or "
            "crude falls far enough that the inflation linkage stops mattering."
        ),
    },
]


def _standing() -> list[dict]:
    today = dt.date.today()
    out = []
    for t in STANDING:
        d = dict(t)
        try:
            d["days_to_review"] = (dt.date.fromisoformat(t["review_on"]) - today).days
        except Exception:
            d["days_to_review"] = None
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Empirical run-length distribution. Measured 2026-09-24 over every theme
# proxy's history with THIS detector's own definition of a run (RS above its
# 200d trend, dips shorter than 15 days merged, runs under 20 days discarded
# as noise): 727 completed runs, median 82d, mean 138d, p75 182d, p90 328d.
#
# Measuring raw EMA crossings instead gives a median of 3 days and is
# meaningless -- RS crosses its trend constantly. That mistake is why the
# first version of this module shipped with invented 120/400-day cut-offs,
# which called a 100-day run "emerging" when it was already past the median.
#
# Stages are terciles of the real distribution; survival answers the question
# that actually matters -- not how old a run is, but how much runway runs of
# that age have historically had left.
STAGE_EARLY, STAGE_MID = 51, 137          # tercile boundaries, days
SURVIVAL = [(6, 1.00), (33, 0.83), (43, 0.73), (50, 0.67), (68, 0.55), (89, 0.46),
            (100, 0.42), (117, 0.39), (162, 0.28), (328, 0.10), (433, 0.04),
            (506, 0.03), (644, 0.02), (1333, 0.00)]


def _stage(age: int) -> str:
    return "early" if age <= STAGE_EARLY else "mid" if age <= STAGE_MID else "late"


def _survival(age: int) -> float:
    """Share of historical runs that lasted longer than `age`, interpolated."""
    if age <= SURVIVAL[0][0]:
        return SURVIVAL[0][1]
    for (a0, s0), (a1, s1) in zip(SURVIVAL, SURVIVAL[1:]):
        if age <= a1:
            f = (age - a0) / (a1 - a0) if a1 > a0 else 0
            return round(s0 + f * (s1 - s0), 3)
    return 0.0


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
            "class": "megatrend" if theme in MEGATRENDS else "rotation",
            "stage": None if not lead else _stage(lead["age_days"]),
            "survival_pct": None if not lead else _survival(lead["age_days"]),
        })
    out.sort(key=lambda t: (t["class"] != "megatrend", t["age_days"] is None, t["age_days"] or 0))
    return {
        "as_of": max(bench) if bench else None,
        "benchmark": BENCH,
        "method": (f"RS = ticker/{BENCH}; trend = {TREND_DAYS}d EMA of RS; onset = earliest day "
                   f"from which RS stayed above trend on >= {int(PERSISTENCE * 100)}% of days since."),
        "run_stats": {"n_runs": 727, "median_days": 82, "mean_days": 138,
                      "p75_days": 182, "p90_days": 328, "measured_on": "2026-09-24"},
        "note": ("Discovery only. Promotion to a standing theme is a monthly human decision; "
                 "once promoted a theme is held for its horizon rather than re-decided daily."),
        "standing": _standing(),
        "themes": out,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
