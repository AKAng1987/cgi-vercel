"""
notes_data.py -- The accumulation layer.

CGI produces two kinds of knowledge and both decay if they are not written
down. Test results live in commit messages and chat; narrative context lives
in the user's head and in office conversations. Neither survives a month.

A note is a dated, scoped, attributed statement:

  kind    data      something a test established, with its numbers
          narrative something known but not derivable from price
          policy    a dated event and its expected read-through
  scope   theme:<name> | regime:<CxGy> | driver:<name> | factor:<name> | global
  source  where it came from, so a claim can be re-checked
  confidence  confirmed | likely | speculative   (narrative and policy only)

Notes surface on whatever object they are scoped to -- a theme note appears
under that theme on LIVE, a regime note on MARKOV -- and all of them appear
chronologically on the NOTES page. That is what makes the mix work: the
tested number and the thing the user knows sit on the same object, neither
pretending to be the other.

Edited by hand. Every entry keeps its date, so a claim that ages badly is
visibly old rather than silently wrong.
"""
from __future__ import annotations

import datetime as dt

NOTES: list[dict] = [
    # ── data: what tests established ────────────────────────────────────────
    {
        "date": "2026-09-23", "kind": "data", "scope": "factor:technicals",
        "title": "Breadth prices risk, not direction",
        "body": ("Over 4,969 aligned days every breadth measure correlates |r| <= 0.10 "
                 "with SPY forward returns at 5, 20 and 60 days. What separates is "
                 "drawdown: MMTH above 70 has meant -1.9% over 20 days, below 30 -5.0% "
                 "(60d: -3.1% vs -8.8%), while the hit rate moves only 71% -> 61%."),
        "source": "docs/BREADTH_STUDY.md",
    },
    {
        "date": "2026-09-23", "kind": "data", "scope": "factor:technicals",
        "title": "The same breadth reading inverts by regime",
        "body": ("MMTH < 30, 60-day forward: in C1 it is 49% up, -1.7% return, -11.0% "
                 "drawdown -- a falling knife. In C2 it is 97% up and +10.9% -- the best "
                 "setup in the study (n=153, concentrated in 2009-10 and 2020, so read "
                 "the direction not the magnitude). Read in isolation the two average to "
                 "a useless middle."),
        "source": "regime-conditioned breadth run, 2026-09-23",
    },
    {
        "date": "2026-09-23", "kind": "data", "scope": "factor:technicals",
        "title": "MMTH falling through 30 is the only negative-expectancy state found",
        "body": ("n=41: 44% up over 20 days, -1.8% return, -11.2% drawdown at 60 days. "
                 "Reclaiming 30 is still bad (-2.0% at 60d), so that line is not an "
                 "all-clear. Losing 70, by contrast, is harmless (69% up, +1.5%)."),
        "source": "30/70 threshold run, 2026-09-23",
    },
    {
        "date": "2026-09-23", "kind": "data", "scope": "factor:technicals",
        "title": "Caruso's 8/20 net-new-high cross does not separate on index direction",
        "body": ("251 crosses each way over 20 years: 8 above 20 gives 65% up over 20 "
                 "days, 8 below gives 66%. It may still work as a trigger alongside other "
                 "conditions or for single-stock timing -- but not as a standalone index "
                 "direction signal."),
        "source": "docs/BREADTH_STUDY.md",
    },
    {
        "date": "2026-09-24", "kind": "data", "scope": "global",
        "title": "Theme runs: median 82 days",
        "body": ("727 completed sustained runs across every theme proxy. Median 82d, mean "
                 "138d, p75 182d, p90 328d. Measuring raw EMA crossings instead gives a "
                 "median of 3 days and is meaningless. This distribution is what the "
                 "runway column reports against."),
        "source": "scripts/ run-length study, 2026-09-24",
    },
    {
        "date": "2026-09-24", "kind": "data", "scope": "theme:Japan",
        "title": "EWJ hands back the currency; DXJ is the real Japan read",
        "body": ("DXJ (yen-hedged) has been running 608 days; EWJ 33. Takaichi window: "
                 "Japan +13.8% in yen vs EWJ +5.3% in USD. Abenomics: +50.0% vs +18.5%. "
                 "The 2024 carry unwind ran the other way -- Japan -6.0% in yen while EWJ "
                 "rose 5.5%. For a weak-yen thesis the instrument decides the outcome."),
        "source": "EWJ x USDJPY decomposition, 2026-09-24",
    },
    {
        "date": "2026-09-19", "kind": "data", "scope": "driver:Challenger cuts (k)",
        "title": "The Fed cuts before the layoff spike",
        "body": ("In the tightening state, LOW Challenger -> 53% chance of a cut, HIGH -> "
                 "6%. 2001, 2008 and 2020 all show the first cut months ahead of the 150k "
                 "crossing. So 150k is a severity marker for a regime already flipped, "
                 "not a trigger for the next flip."),
        "source": "docs/TRADING_SYSTEM.md, Liquidity addendum",
    },
    {
        "date": "2026-09-24", "kind": "data", "scope": "global",
        "title": "MarketStack served three different securities under MAGS",
        "body": ("Pre-2023 rows were a penny stock, June 2023 another instrument, only "
                 "2023-04 onward and 2023-11 onward were the real ETF. Purged and "
                 "reloaded from CBOE:MAGS; MAGS removed from the MarketStack refresh so "
                 "it cannot re-corrupt. Also repaired 32 unadjusted splits (83,204 rows) "
                 "and 118 zero-close rows. Any backtest number read before 2026-09-24 "
                 "contained fabricated moves for ~28 tickers."),
        "source": "scripts/fix_splits.py",
    },

    # ── narrative: known, not derivable from price ──────────────────────────
    {
        "date": "2026-09-24", "kind": "narrative", "scope": "theme:energy: refiners",
        "title": "The refiner run began on the trade war",
        "body": ("CRAK's run starts 2025-05-05. The cause was the trade war, not anything "
                 "in the price series. One-off and not repeatable, so it is recorded here "
                 "rather than built into a factor."),
        "source": "user, 2026-09-24", "confidence": "confirmed",
    },
    {
        "date": "2026-09-24", "kind": "narrative", "scope": "theme:agriculture",
        "title": "El Nino acts like policy but is not policy",
        "body": ("Weather shocks propagate through agriculture the way fiscal policy does, "
                 "but they are not a policy factor. Unlike a trade war this one IS "
                 "measurable and repeatable -- NOAA publishes the Oceanic Nino Index free, "
                 "monthly back to 1950 -- so it is a candidate driver rather than only a "
                 "note. Untested so far."),
        "source": "user, 2026-09-24", "confidence": "likely",
    },
    {
        "date": "2026-09-24", "kind": "narrative", "scope": "global",
        "title": "Edge is in the range, not the trend",
        "body": ("NATGAS in C2G4: avg high +13.2%, avg low -9.7%, avg return +1.8% over 21 "
                 "occurrences. The trade went the right way at some point in nearly every "
                 "window, but holding to the regime's end gave most of it back. Read 'edge' "
                 "as a range statistic and size the exit accordingly."),
        "source": "user trade review + backtest, 2026-09-23", "confidence": "confirmed",
    },

    # ── policy: dated events and their read-through ─────────────────────────
    {
        "date": "2025-10-01", "kind": "policy", "scope": "theme:Japan",
        "title": "Takaichi becomes PM, proposes spending",
        "body": ("New Japanese PM with a spending programme. Yen depreciated, market "
                 "rallied on currency plus spending -- the classic exporter response. "
                 "Oct 2025 to Mar 2026: Japan +13.8% in yen, USDJPY +8.1%, EWJ only "
                 "+5.3%. The read-through is that the trade needs a hedged instrument."),
        "source": "user, 2026-09-24", "confidence": "confirmed",
    },
    {
        "date": "2026-09-16", "kind": "policy", "scope": "regime:C3",
        "title": "FOMC hiked; compass moved C2 -> C3",
        "body": ("History put the flip at 8%, fed funds futures at 94%. Market was right. "
                 "The model recorded the flip ~32 hours later because DFEDTARU carries an "
                 "effective date and FRED publishes on a lag -- hence the 3-day settlement "
                 "window and 'pending' state on MARKOV."),
        "source": "MARKOV event log", "confidence": "confirmed",
    },
    {
        "date": "2026-09-24", "kind": "policy", "scope": "global",
        "title": "Policy takes about a year to reach the system",
        "body": ("User's working prior for fiscal policy: roughly twelve months from "
                 "enactment to the spend showing up in the economy. Worth testing against "
                 "the market clock, which front-runs it -- Abenomics delivered +50% in "
                 "seven months. The POLICY event study should measure at 3, 6, 12 and 24 "
                 "months rather than assume."),
        "source": "user, 2026-09-24", "confidence": "likely",
    },
]


def build_notes_response(scope: str | None = None) -> dict:
    rows = [n for n in NOTES if not scope or n.get("scope") == scope]
    rows = sorted(rows, key=lambda n: n["date"], reverse=True)
    today = dt.date.today()
    for n in rows:
        try:
            n = n
            n["age_days"] = (today - dt.date.fromisoformat(n["date"])).days
        except Exception:
            n["age_days"] = None
    by_kind: dict[str, int] = {}
    for n in NOTES:
        by_kind[n["kind"]] = by_kind.get(n["kind"], 0) + 1
    return {
        "as_of": today.isoformat(),
        "count": len(rows),
        "by_kind": by_kind,
        "scopes": sorted({n["scope"] for n in NOTES}),
        "notes": rows,
    }
