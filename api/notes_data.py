"""
notes_data.py -- The accumulation layer: policy, narrative, findings.

Three separate registers, because they decay differently and are trusted
differently.

POLICY     dated announcements -- monetary, fiscal, trade, geopolitical --
           by country, each with the themes and tickers it should move. This
           is the register the user wants working FORWARD: a policy lands,
           it names the themes to watch, and those themes are then checked
           against RS. The point is to be early rather than to explain a
           rally six months after it happened.

NARRATIVE  things known but not derivable from price: why a run started, how
           an instrument behaves, what an office conversation established.
           Carries a source and a confidence.

FINDING    what a test established, with its numbers. These are the build's
           own results -- useful, but not the same thing as market knowledge,
           so they are kept in their own register rather than mixed in.

A policy note stays on LIVE while any theme it points at is still running on
RS, and lives here permanently for reference either way.

Countries tracked are the markets the user can actually trade: US, JP, KR,
CN, PH, GB, DE, FR, and the rest of the EU periphery when it matters.
"""
from __future__ import annotations

import datetime as dt

# ── POLICY ──────────────────────────────────────────────────────────────────
# announced: the date the policy was ANNOUNCED, not the date it took effect --
# markets move on announcement. effective: when the money or the rule lands.
POLICY: list[dict] = [
    {
        "country": "JP", "type": "fiscal", "announced": "2025-10-01", "effective": None,
        "title": "Takaichi becomes PM, proposes spending programme",
        "detail": ("New Japanese PM with a spending programme. The yen depreciated and "
                   "the market rallied on currency plus spending -- the classic exporter "
                   "response for an export-led economy. Oct 2025 to Mar 2026: Japan "
                   "+13.8% in yen, USDJPY +8.1%, but EWJ only +5.3% because it is "
                   "unhedged. The read-through is as much about instrument as direction."),
        "themes": ["Japan"], "tickers": ["DXJ", "EWJ", "USDJPY"],
        "source": "user, 2026-09-24", "confidence": "confirmed",
    },
    {
        "country": "US", "type": "trade", "announced": "2025-04-02", "effective": "2025-04-02",
        "title": "Reciprocal Tariff Executive Order",
        "detail": ("Tariff regime change. Refiners began their run a month later "
                   "(CRAK from 2025-05-05, now 506 days and a megatrend) -- the user "
                   "attributes that run to the trade war. Trade policy also feeds the "
                   "shipping-route dislocation behind the energy pricing-power theme."),
        "themes": ["energy: refiners", "shipping / logistics"],
        "tickers": ["CRAK", "SEA", "XLI", "SPY"],
        "source": "user fiscal-acts table + user, 2026-09-24", "confidence": "confirmed",
    },
    {
        "country": "US", "type": "monetary", "announced": "2026-09-16", "effective": "2026-09-17",
        "title": "FOMC hikes; compass moves C2 -> C3",
        "detail": ("History put the flip at 8%, fed funds futures at 94% -- the market "
                   "was right. The model recorded it ~32h later because DFEDTARU carries "
                   "an effective date and FRED publishes on a lag, which is why MARKOV "
                   "now has a 3-day settlement window and a pending state. Hikes into a "
                   "steepening curve are the mechanism behind the dollar theme."),
        "themes": ["Japan", "Korea / DRAM"], "tickers": ["UUP", "DXY", "US02Y", "US10Y"],
        "source": "MARKOV event log", "confidence": "confirmed",
    },
    {
        "country": "US", "type": "fiscal", "announced": "2022-08-09", "effective": "2022-08-09",
        "title": "CHIPS and Science Act ($280bn)",
        "detail": ("Semiconductor manufacturing and research subsidies. Semis/memory "
                   "began their current run 2024-12-18, well after enactment -- "
                   "consistent with the user's prior that fiscal policy takes about a "
                   "year to reach the system, though here it took longer."),
        "themes": ["semis / memory", "AI"], "tickers": ["SMH", "SOXX"],
        "source": "user fiscal-acts table", "confidence": "confirmed",
    },
    {
        "country": "US", "type": "fiscal", "announced": "2022-08-16", "effective": "2022-08-16",
        "title": "Inflation Reduction Act ($737bn)",
        "detail": ("Energy and healthcare. Seven days after CHIPS, which is why the two "
                   "cannot be separated in an event study -- a structural limit on the "
                   "POLICY factor rather than a data problem."),
        "themes": ["solar / clean", "power / grid", "biotech / healthcare"],
        "tickers": ["TAN", "ICLN", "XLE", "XLV"],
        "source": "user fiscal-acts table", "confidence": "confirmed",
    },
    {
        "country": "US", "type": "fiscal", "announced": "2021-11-15", "effective": "2021-11-15",
        "title": "Infrastructure Investment and Jobs Act ($1.2tn)",
        "detail": "Infrastructure and energy build-out.",
        "themes": ["infrastructure", "steel / metals", "power / grid"],
        "tickers": ["IGF", "SLX", "XME", "GRID"],
        "source": "user fiscal-acts table", "confidence": "confirmed",
    },
    {
        "country": "US", "type": "fiscal", "announced": "2020-03-27", "effective": "2020-03-27",
        "title": "CARES Act ($2.2tn)",
        "detail": ("The largest fiscal impulse in the sample, and the cleanest example of "
                   "the confounding problem: it lands on the COVID crash bottom, so any "
                   "measured 'policy effect' is really the rebound."),
        "themes": ["cloud / software", "biotech / healthcare"],
        "tickers": ["XLV", "XLY", "SKYY"],
        "source": "user fiscal-acts table", "confidence": "confirmed",
    },
    {
        "country": "XX", "type": "geopolitical", "announced": "2026-01-01", "effective": None,
        "title": "Middle East conflict and route disruption (ongoing)",
        "detail": ("Additional trade routes and Middle East disruption reposition vessels "
                   "and lengthen voyages, giving BDI and SEA pricing power while the "
                   "conditions run. Producers get pricing power through shortage, which "
                   "feeds inflation and therefore the hiking path -- making this the main "
                   "risk to the AI capex theme rather than an independent bet. Date is "
                   "approximate; this is a condition, not an announcement."),
        "themes": ["energy: upstream", "energy: refiners", "shipping / logistics"],
        "tickers": ["SEA", "XLE", "XOP", "CRAK", "USOIL"],
        "source": "user, 2026-09-24", "confidence": "likely",
    },
]

# ── NARRATIVE ───────────────────────────────────────────────────────────────
NARRATIVE: list[dict] = [
    {
        "date": "2026-09-24", "scope": "global",
        "title": "Edge is in the range, not the trend",
        "body": ("NATGAS in C2G4: avg high +13.2%, avg low -9.7%, avg return +1.8% over 21 "
                 "occurrences. The trade went the right way at some point in nearly every "
                 "window, but holding to the regime's end gave most of it back."),
        "source": "user trade review + backtest", "confidence": "confirmed",
    },
    {
        "date": "2026-09-24", "scope": "theme:agriculture",
        "title": "El Nino acts like policy but is not policy",
        "body": ("Weather shocks propagate through agriculture the way fiscal policy does. "
                 "Unlike a trade war this one is measurable and repeatable -- NOAA's "
                 "Oceanic Nino Index is free and monthly back to 1950 -- so it is a "
                 "candidate driver rather than only a note. Untested so far."),
        "source": "user", "confidence": "likely",
    },
    {
        "date": "2026-09-25", "scope": "global",
        "title": "Unhedged country ETFs hand the currency back",
        "body": ("EWJ in USD captured roughly a third of Japan's move under a falling yen "
                 "(Abenomics: +18.5% vs +50.0% in yen). Any weak-currency thesis needs a "
                 "hedged vehicle or local shares. Applies to Korea and the EU markets "
                 "equally."),
        "source": "user + decomposition", "confidence": "confirmed",
    },
]

# ── FINDINGS (the build's own test results) ─────────────────────────────────
FINDINGS: list[dict] = [
    {
        "date": "2026-09-23", "scope": "factor:technicals",
        "title": "Breadth prices risk, not direction",
        "body": ("|r| <= 0.10 against SPY forward returns at 5/20/60d over 4,969 days. "
                 "What separates is drawdown: MMTH above 70 has meant -1.9% over 20 days, "
                 "below 30 -5.0% (60d: -3.1% vs -8.8%)."),
        "source": "docs/BREADTH_STUDY.md",
    },
    {
        "date": "2026-09-23", "scope": "factor:technicals",
        "title": "The same breadth reading inverts by regime",
        "body": ("MMTH < 30 at 60 days: C1 is 49% up and -11.0% drawdown, a falling knife. "
                 "C2 is 97% up and +10.9%, the best setup in the study (n=153, "
                 "concentrated in 2009-10 and 2020 -- read the direction, not the "
                 "magnitude)."),
        "source": "regime-conditioned breadth run",
    },
    {
        "date": "2026-09-23", "scope": "factor:technicals",
        "title": "MMTH falling through 30 is the only negative-expectancy state found",
        "body": ("n=41: 44% up over 20 days, -1.8% return, -11.2% drawdown at 60 days. "
                 "Reclaiming 30 is still bad, so that line is not an all-clear."),
        "source": "30/70 threshold run",
    },
    {
        "date": "2026-09-24", "scope": "global",
        "title": "Theme runs: median 82 days",
        "body": ("727 completed sustained runs. Median 82d, mean 138d, p75 182d, p90 328d. "
                 "Raw EMA crossings instead give a median of 3 days and are meaningless."),
        "source": "run-length study",
    },
    {
        "date": "2026-09-19", "scope": "driver:Challenger cuts (k)",
        "title": "The Fed cuts before the layoff spike",
        "body": ("Tightening state: LOW Challenger -> 53% chance of a cut, HIGH -> 6%. "
                 "2001, 2008 and 2020 all show the first cut months ahead of the 150k "
                 "crossing, so 150k is a severity marker, not a trigger."),
        "source": "docs/TRADING_SYSTEM.md",
    },
    {
        "date": "2026-09-24", "scope": "global",
        "title": "Price history repaired -- earlier backtests were wrong",
        "body": ("MarketStack served three securities under MAGS; 32 splits were "
                 "unadjusted (83,204 rows back-adjusted) and 118 zero-closes deleted. Any "
                 "backtest number read before 2026-09-24 contained fabricated moves for "
                 "~28 tickers."),
        "source": "scripts/fix_splits.py",
    },
]


def _age(d: str, today: dt.date) -> int | None:
    try:
        return (today - dt.date.fromisoformat(d)).days
    except Exception:
        return None


def build_notes_response(active_themes: list[str] | None = None) -> dict:
    """active_themes: theme names currently running on RS. A policy note is
    'live' while any theme it points at is still running -- that is what keeps
    it on the LIVE brief and drops it off when the trade is over."""
    today = dt.date.today()
    active = set(active_themes or [])

    policy = []
    for p in sorted(POLICY, key=lambda x: x["announced"], reverse=True):
        q = dict(p)
        q["age_days"] = _age(p["announced"], today)
        q["live_themes"] = [t for t in p.get("themes", []) if t in active]
        q["is_live"] = bool(q["live_themes"])
        policy.append(q)

    narrative = [dict(n, age_days=_age(n["date"], today))
                 for n in sorted(NARRATIVE, key=lambda x: x["date"], reverse=True)]
    findings = [dict(n, age_days=_age(n["date"], today))
                for n in sorted(FINDINGS, key=lambda x: x["date"], reverse=True)]

    return {
        "as_of": today.isoformat(),
        "counts": {"policy": len(policy), "narrative": len(narrative), "findings": len(findings)},
        "countries": sorted({p["country"] for p in POLICY}),
        "policy": policy,
        "narrative": narrative,
        "findings": findings,
        "note": ("A policy note stays on LIVE while a theme it points at is still running "
                 "on relative strength, and stays here permanently either way."),
    }
