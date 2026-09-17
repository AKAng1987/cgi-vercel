"""
Release calendar for the event-driven Markov layer.

Each Tesseract axis moves on exactly one release type:
  liquidity  <- FOMC decision         (compass)
  credit     <- SLOOS publication      (compass)
  inflation  <- CPI (BLS)              (grid)
  growth     <- GDP (BEA; adv/2nd/3rd all count -- model-history shows
                transitions on 2026-06-25 (Q1 third) and 07-30 (Q2 adv))

Dates are hardcoded from the official schedules. VERIFY when extending:
  FOMC : https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
         (also scraped live by macro_data.get_upcoming_meetings)
  SLOOS: https://www.federalreserve.gov/data/sloos.htm  (Mon after the
         Feb/May/Aug/Nov FOMC; model sees it when FRED DRTSCILM updates)
  CPI  : https://www.bls.gov/schedule/news_release/cpi.htm
  GDP  : https://www.bea.gov/news/schedule

Verified 2026-09-16 against the official pages: all CPI 2026, GDP
Sep-Dec 2026 (Sep 30 = Q2 third; Jan-Aug not shown on the page but
06-25 and 07-30 match model-history transitions), all FOMC 2026 + 2027.
SLOOS: the Fed page lists survey periods, not publication dates; credit
transitions in model-history since 2023 land on the publication Monday
(2026-05-04 and 2026-08-03 confirmed), 11-02 follows that pattern.

Emergency / unscheduled FOMC moves are not in this table by definition;
they surface as a transition on a non-calendar date and the event log
labels them "unscheduled".
"""

from __future__ import annotations

import datetime as dt
from typing import Optional

AXIS_OF = {"FOMC": "liquidity", "SLOOS": "credit", "CPI": "inflation", "GDP": "growth"}
MODEL_OF = {"liquidity": "compass", "credit": "compass", "growth": "grid", "inflation": "grid"}
# Which tuple slot each axis occupies in Q_TO_AXES (first, second).
SLOT_OF = {"liquidity": 0, "credit": 1, "growth": 0, "inflation": 1}
# Releases per year -- used to turn dwell-days into expected release counts.
PER_YEAR = {"FOMC": 8, "SLOOS": 4, "CPI": 12, "GDP": 12}

# Quadrant -> (first_axis_up, second_axis_up). Compass: (Liquidity, Credit).
# Grid: (Growth, Inflation). Same table for both.
Q_TO_AXES = {1: (1, 0), 2: (1, 1), 3: (0, 1), 4: (0, 0)}
AXES_TO_Q = {v: k for k, v in Q_TO_AXES.items()}

_CPI_2026 = [
    "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10",
    "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14", "2026-11-10", "2026-12-10",
]
_GDP_2026 = [
    "2026-01-29", "2026-02-26", "2026-03-26", "2026-04-29", "2026-05-28", "2026-06-25",
    "2026-07-30", "2026-08-27", "2026-09-30", "2026-10-29", "2026-11-25", "2026-12-23",
]
_FOMC = [  # decision day (second day of the meeting); 2026 + 2027
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
        "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
]
_SLOOS_2026 = ["2026-02-02", "2026-05-04", "2026-08-03", "2026-11-02"]


def _rows(kind: str, dates: list[str]) -> list[dict]:
    axis = AXIS_OF[kind]
    return [{"date": d, "type": kind, "axis": axis, "model": MODEL_OF[axis]} for d in dates]


RELEASES: list[dict] = sorted(
    _rows("CPI", _CPI_2026) + _rows("GDP", _GDP_2026) + _rows("FOMC", _FOMC) + _rows("SLOOS", _SLOOS_2026),
    key=lambda r: r["date"],
)


def next_releases(after: Optional[str] = None, one_per_type: bool = True) -> list[dict]:
    """Upcoming releases strictly after `after` (default: today UTC)."""
    after = after or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    out, seen = [], set()
    for r in RELEASES:
        if r["date"] < after:  # same-day counts: at 00:55 UTC every US release is still ahead
            continue
        if one_per_type and r["type"] in seen:
            continue
        seen.add(r["type"])
        out.append(r)
    return out


def releases_between(start: str, end: str) -> list[dict]:
    """Releases with start < date <= end."""
    return [r for r in RELEASES if start < r["date"] <= end]


def release_on(date: str) -> list[dict]:
    return [r for r in RELEASES if r["date"] == date]


# ── Watch tier ──────────────────────────────────────────────────────────────
# Events that don't set an axis but feed the nowcasts and the narrative.
# Most are rule-generated (nth business day / nth weekday), so they never
# need re-hardcoding; BOJ is hardcoded like FOMC. Each carries `informs`:
# the axis its print is a leading read for.
#
#   ISM Manufacturing   1st business day of month     -> growth, inflation (prices paid)
#   ISM Services        3rd business day of month     -> growth, inflation
#   Challenger job cuts business day before NFP        -> growth
#   NFP (jobs)          1st Friday (BLS occasionally shifts; verify Jan/Jul) -> growth
#   BOJ decision        hardcoded 2026               -> liquidity (global)
#   Quad witching       3rd Friday Mar/Jun/Sep/Dec    -> positioning
#   Opex                3rd Friday other months       -> positioning
#
# US holidays that move a "1st business day" are not modelled; the ISM
# publishes on the first business day *it* observes, which is the same
# except around Jan 1 / Jul 4 / Labor Day (ISM Mfg on 2026-09-01 is
# correct: Sep 1 was a Tuesday after Labor Day 8/31... verify each year).

# BOJ decision days (last day of each MPM), verified 2026-09-17 against
# boj.or.jp/en/mopo/mpmsche_minu -- 2026 and 2027.
_BOJ = {
    2026: ["2026-01-23", "2026-03-19", "2026-04-28", "2026-06-16", "2026-07-31", "2026-09-18", "2026-10-30", "2026-12-18"],
    2027: ["2027-01-22", "2027-03-18", "2027-04-28", "2027-06-11", "2027-07-22", "2027-09-22", "2027-10-29", "2027-12-17"],
}

WATCH_INFORMS = {
    "ISM_MFG": ["growth", "inflation"],
    "ISM_SVC": ["growth", "inflation"],
    "CHALLENGER": ["growth"],
    "NFP": ["growth"],
    "BOJ": ["liquidity"],
    "QUAD_WITCH": ["positioning"],
    "OPEX": ["positioning"],
}
WATCH_LABEL = {
    "ISM_MFG": "ISM Manufacturing", "ISM_SVC": "ISM Services", "CHALLENGER": "Challenger job cuts",
    "NFP": "Jobs report (NFP)", "BOJ": "BOJ decision", "QUAD_WITCH": "Quad witching", "OPEX": "Monthly opex",
}


def _nth_business_day(year: int, month: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    count = 0
    while True:
        if d.weekday() < 5:
            count += 1
            if count == n:
                return d
        d += dt.timedelta(days=1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    while d.weekday() != weekday:
        d += dt.timedelta(days=1)
    return d + dt.timedelta(days=7 * (n - 1))


def _prev_business_day(d: dt.date) -> dt.date:
    d -= dt.timedelta(days=1)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def watch_events(year: int) -> list[dict]:
    out = []
    for m in range(1, 13):
        ism_m = _nth_business_day(year, m, 1)
        ism_s = _nth_business_day(year, m, 3)
        nfp = _nth_weekday(year, m, 4, 1)  # Friday = 4
        chal = _prev_business_day(nfp)
        third_fri = _nth_weekday(year, m, 4, 3)
        out += [
            {"date": ism_m.isoformat(), "type": "ISM_MFG"},
            {"date": ism_s.isoformat(), "type": "ISM_SVC"},
            {"date": chal.isoformat(), "type": "CHALLENGER"},
            {"date": nfp.isoformat(), "type": "NFP"},
            {"date": third_fri.isoformat(), "type": "QUAD_WITCH" if m in (3, 6, 9, 12) else "OPEX"},
        ]
    out += [{"date": d, "type": "BOJ"} for d in _BOJ.get(year, [])]
    for r in out:
        r["tier"] = "watch"
        r["label"] = WATCH_LABEL[r["type"]]
        r["informs"] = WATCH_INFORMS[r["type"]]
    return sorted(out, key=lambda r: r["date"])


def timeline(start: Optional[str] = None, days: int = 45) -> list[dict]:
    """Axis releases + watch events from `start` (default today) for `days`,
    sorted, each tagged tier=axis|watch."""
    start = start or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    end = (dt.date.fromisoformat(start) + dt.timedelta(days=days)).isoformat()
    years = {int(start[:4]), int(end[:4])}
    ax = [{**r, "tier": "axis", "label": r["type"], "informs": [r["axis"]]} for r in RELEASES if start <= r["date"] <= end]
    wt = [r for y in sorted(years) for r in watch_events(y) if start <= r["date"] <= end]
    return sorted(ax + wt, key=lambda r: (r["date"], 0 if r["tier"] == "axis" else 1))
