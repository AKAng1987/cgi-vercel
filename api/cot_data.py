"""
cot_data.py -- POSITIONING: Commitments of Traders.

Free, direct from the CFTC's public reporting API. Verified against the
user's officemate's own dashboard: NAT GAS NYME large specs -221,587 on
2026-09-15 against his -222K.

WHAT THE REPORT IS
Every futures contract has a long and a short, so the report only says who
is on each side:
  commercials      producers, refiners, utilities, merchants -- hedging a
                   business, price-insensitive
  large specs      managed money, CTAs, macro funds -- momentum. Most long
                   at tops and most short at bottoms, which is the edge
  small traders    non-reportable, usually with the specs

WHY EXTREMES MATTER
Specs are trend followers. When they are maximally short, nearly everyone
who wanted to sell has sold: the marginal seller is gone, so a catalyst
forces buying-to-cover into no supply. Extreme positioning does not cause a
reversal -- it removes the fuel for continuation and makes the risk
asymmetric.

THE COT INDEX (Williams)
Where this week's net sits within its own range over a lookback. 0 = the
most short it has been, 100 = the most long. Reported on two bases because
they disagree and the disagreement matters:
  raw        net contracts -- what the report prints
  pct_oi     net as a share of open interest -- fairer across decades,
             because open interest has grown enormously. Natural gas in
             Sept 2026 was 12th percentile on raw contracts but 34th on
             share of OI, and 2011 was far more extreme on the OI measure.

LIMITS, CARRIED DELIBERATELY
- the data is Tuesday's close, published Friday 15:30 ET: three days stale
  on arrival and up to ten before the next one. The CFTC plans twice-weekly
  reports by the end of 2026 (Wednesday, data through Monday; Friday, data
  through Wednesday). Everything here is therefore built on ONE FINAL
  OBSERVATION A WEEK (the last as-of date in each ISO week), with windows in
  calendar days; an earlier-in-the-week read is INTERIM and shown separately,
  never used for the headline, extremes or alerts. See _weekly/_split/_cadence.
- extremes persist. 2011 sat pinned at extreme short for months while price
  kept falling. This is a condition, not a trigger -- price has to stop
  confirming before it becomes one
- contracts get renamed. NYMEX natural gas was "NATURAL GAS" until Feb 2022
  and "NAT GAS NYME" after, which is why history has to be stitched
"""
from __future__ import annotations

import datetime as dt
import json
import time
import urllib.parse
import urllib.request

BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
FIELDS = ("report_date_as_yyyy_mm_dd,open_interest_all,"
          "noncomm_positions_long_all,noncomm_positions_short_all,"
          "comm_positions_long_all,comm_positions_short_all,"
          "nonrept_positions_long_all,nonrept_positions_short_all")
LOOKBACKS = {"3y": 156, "5y": 260, "all": None}
EXTREME_LOW, EXTREME_HIGH = 10.0, 90.0

# group -> label -> the CFTC market names, newest first. Several contracts
# were renamed, so more than one name can feed a single series.
CONTRACTS: dict[str, list[tuple[str, list[str]]]] = {
    "ENERGY": [
        ("Natural Gas", ["NAT GAS NYME - NEW YORK MERCANTILE EXCHANGE",
                         "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE"]),
        ("Crude Oil", ["WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE",
                       "CRUDE OIL, LIGHT SWEET-WTI - NEW YORK MERCANTILE EXCHANGE"]),
        ("Gasoline", ["GASOLINE RBOB - NEW YORK MERCANTILE EXCHANGE"]),
    ],
    "METALS": [
        ("Gold", ["GOLD - COMMODITY EXCHANGE INC."]),
        ("Silver", ["SILVER - COMMODITY EXCHANGE INC."]),
        ("Copper", ["COPPER- #1 - COMMODITY EXCHANGE INC."]),
        ("Platinum", ["PLATINUM - NEW YORK MERCANTILE EXCHANGE"]),
        ("Palladium", ["PALLADIUM - NEW YORK MERCANTILE EXCHANGE"]),
        # Steel only exists from 2022-02. The 3y index is fine; the 5y and
        # "all" lookbacks will quietly be the same window, and the response
        # carries n so that is visible rather than implied.
        ("Steel (HRC)", ["STEEL-HRC - COMMODITY EXCHANGE INC."]),
        ("Aluminum", ["ALUMINUM MWP - COMMODITY EXCHANGE INC.",
                      "ALUMINUM - COMMODITY EXCHANGE INC."]),
    ],
    "AGRICULTURE": [
        ("Corn", ["CORN - CHICAGO BOARD OF TRADE"]),
        ("Soybeans", ["SOYBEANS - CHICAGO BOARD OF TRADE"]),
        ("Soybean Oil", ["SOYBEAN OIL - CHICAGO BOARD OF TRADE"]),
        ("Soybean Meal", ["SOYBEAN MEAL - CHICAGO BOARD OF TRADE"]),
        ("Wheat", ["WHEAT-SRW - CHICAGO BOARD OF TRADE"]),
        ("Sugar", ["SUGAR NO. 11 - ICE FUTURES U.S."]),
        ("Coffee", ["COFFEE C - ICE FUTURES U.S."]),
        ("Cocoa", ["COCOA - ICE FUTURES U.S."]),
        ("Cotton", ["COTTON NO. 2 - ICE FUTURES U.S."]),
        ("Live Cattle", ["LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE"]),
        ("Lean Hogs", ["LEAN HOGS - CHICAGO MERCANTILE EXCHANGE"]),
    ],
    "RATES": [
        ("2-Year Note", ["UST 2Y NOTE - CHICAGO BOARD OF TRADE"]),
        ("5-Year Note", ["UST 5Y NOTE - CHICAGO BOARD OF TRADE"]),
        ("10-Year Note", ["UST 10Y NOTE - CHICAGO BOARD OF TRADE"]),
        ("30-Year Bond", ["UST BOND - CHICAGO BOARD OF TRADE",
                          "U.S. TREASURY BONDS - CHICAGO BOARD OF TRADE"]),
    ],
    "FX": [
        ("US Dollar Index", ["USD INDEX - ICE FUTURES U.S."]),
        ("Euro FX", ["EURO FX - CHICAGO MERCANTILE EXCHANGE"]),
        ("Japanese Yen", ["JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"]),
        ("British Pound", ["BRITISH POUND - CHICAGO MERCANTILE EXCHANGE",
                           "BRITISH POUND STERLING - CHICAGO MERCANTILE EXCHANGE"]),
        ("Canadian Dollar", ["CANADIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"]),
        ("Swiss Franc", ["SWISS FRANC - CHICAGO MERCANTILE EXCHANGE"]),
        ("Australian Dollar", ["AUSTRALIAN DOLLAR - CHICAGO MERCANTILE EXCHANGE"]),
        ("Mexican Peso", ["MEXICAN PESO - CHICAGO MERCANTILE EXCHANGE"]),
    ],
    "EQUITY": [
        # Both of these were DEAD. The CFTC renamed a large block of contracts
        # on 2022-02-01, and the two configured here stopped there -- S&P 500
        # and Nasdaq 100 E-mini had shown nothing for four and a half years
        # while still appearing on the page. The old name is kept second so
        # the pre-2022 history still comes through; _series merges on date.
        ("S&P 500 (E-mini)", ["E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE",
                              "E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE"]),
        ("Nasdaq 100 (E-mini)", ["NASDAQ MINI - CHICAGO MERCANTILE EXCHANGE",
                                 "NASDAQ-100 STOCK INDEX (MINI) - CHICAGO MERCANTILE EXCHANGE"]),
        ("Russell 2000 (E-mini)", ["RUSSELL E-MINI - CHICAGO MERCANTILE EXCHANGE"]),
        ("Dow (x $5)", ["DJIA x $5 - CHICAGO BOARD OF TRADE",
                        "DOW JONES INDUSTRIAL AVG- x $5 - CHICAGO BOARD OF TRADE"]),
        ("VIX", ["VIX FUTURES - CBOE FUTURES EXCHANGE"]),
        ("Bitcoin", ["BITCOIN - CHICAGO MERCANTILE EXCHANGE"]),
    ],
}


def _fetch(name: str) -> list[dict]:
    w = urllib.parse.quote(f"market_and_exchange_names = '{name}'")
    url = f"{BASE}?$select={FIELDS}&$where={w}&$order=report_date_as_yyyy_mm_dd&$limit=50000"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def _raw(names: list[str]) -> list[dict]:
    """Every as-of observation the CFTC has for this contract (renamed contracts stitched), oldest first, one per date."""
    rows: list[dict] = []
    for n in names:
        for attempt in (1, 2):                     # one retry: the fetches run side by side now and the CFTC can throttle
            try:
                rows += _fetch(n)
                break
            except Exception:
                if attempt == 2:
                    break
                time.sleep(1.5)
    out, seen = [], set()
    for r in sorted(rows, key=lambda x: x["report_date_as_yyyy_mm_dd"]):
        d = r["report_date_as_yyyy_mm_dd"][:10]
        if d in seen:
            continue
        seen.add(d)
        g = lambda k: float(r.get(k) or 0)
        oi = g("open_interest_all")
        out.append({
            "date": d, "oi": oi,
            "spec": g("noncomm_positions_long_all") - g("noncomm_positions_short_all"),
            "comm": g("comm_positions_long_all") - g("comm_positions_short_all"),
            "small": g("nonrept_positions_long_all") - g("nonrept_positions_short_all"),
        })
    for r in out:
        r["spec_pct_oi"] = (r["spec"] / r["oi"] * 100) if r["oi"] else 0.0
    return out


def _weekday(d: str) -> int:
    return dt.date.fromisoformat(d).weekday()


def _weekly(raw: list[dict]) -> list[dict]:
    """One observation a week: the LAST as-of date in each ISO week. Today that is the Tuesday report; if the CFTC adds a
    Monday and a Wednesday as-of date each week (twice-weekly reports, planned for December 2026) it is the Wednesday, so
    the series stays one row a week and every row-count lookback keeps meaning what it says."""
    last: dict[tuple, dict] = {}
    for r in raw:
        last[dt.date.fromisoformat(r["date"]).isocalendar()[:2]] = r
    return [last[k] for k in sorted(last)]


def _canon_weekday(weekly: list[dict]) -> int | None:
    """The weekday the weekly FINAL observation falls on: the mode over the last 8 weeks before the newest one (the later
    weekday wins a tie, so a changeover reads as the new cadence one week early rather than one late)."""
    prior = weekly[:-1][-8:]
    if len(prior) < 4:
        return None
    counts: dict[int, int] = {}
    for r in prior:
        counts[_weekday(r["date"])] = counts.get(_weekday(r["date"]), 0) + 1
    return max(counts, key=lambda w: (counts[w], w))


def _split(weekly: list[dict]) -> tuple[list[dict], dict | None]:
    """(finals, interim). The newest observation is INTERIM when it falls earlier in the week than the weekly final does
    (a Monday as-of read while finals are Wednesday's): a later one is expected within days. Interim reads are shown
    separately and never feed the headline numbers, the extremes or the alerts, so the 10/90 bands and the alert rate keep
    the meaning they were calibrated on."""
    canon = _canon_weekday(weekly)
    if canon is not None and weekly and _weekday(weekly[-1]["date"]) < canon:
        return weekly[:-1], weekly[-1]
    return weekly, None


def _series(names: list[str]) -> list[dict]:
    """The weekly FINAL series (what every index, extreme and study reads). research/cot_turns/run.py imports this."""
    return _split(_weekly(_raw(names)))[0]


def publish_date(as_of: str) -> dt.date:
    """When the CFTC publishes the report for this as-of date (15:30 ET): Tuesday -> Friday (+3); under the twice-weekly
    schedule Monday -> Wednesday (+2) and Wednesday -> Friday (+2). A holiday only ever moves it later."""
    d = dt.date.fromisoformat(as_of)
    return d + dt.timedelta(days={0: 2, 2: 2}.get(d.weekday(), 3))


def _cadence(dates: list[str]) -> dict:
    """What the report calendar looks like in the data, so a change in it cannot go unnoticed.
    Known: weekly on any of Mon/Tue/Wed, or twice a week (Mon and Wed). Unknown (problem): an as-of weekday outside
    Mon-Wed, or more than ~2 distinct as-of dates a week."""
    ds = sorted(set(dates))
    if not ds:
        return {"pattern": "unknown", "problem": "no as-of dates", "twice_weekly": False}
    last = dt.date.fromisoformat(ds[-1])
    recent = [d for d in ds if (last - dt.date.fromisoformat(d)).days < 42]
    last8 = [d for d in ds if (last - dt.date.fromisoformat(d)).days < 56]
    wd = sorted({_weekday(d) for d in recent})
    per_week = round(len(last8) / 8.0, 2)
    first_non_tue = next((d for d in ds if _weekday(d) != 1), None)
    twice = per_week >= 1.5
    problem = None
    if any(w > 2 for w in wd):
        problem = f"as-of weekday outside Mon-Wed seen ({', '.join(['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][w] for w in wd)})"
    elif per_week > 2.1:
        problem = f"{per_week} as-of dates a week; expected at most two"
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {"pattern": ("twice-weekly" if twice else "weekly") + " " + "/".join(names[w] for w in wd),
            "as_of_weekdays_last_6w": [names[w] for w in wd], "rows_per_week_last_8w": per_week,
            "first_non_tuesday_seen": first_non_tue, "twice_weekly": twice, "problem": problem}


# Every reading carries its trader category explicitly. The module docstring
# has always explained what commercials/large specs/small traders are, but the
# NUMBERS went out as bare `spec`/`comm`/`small` keys, so the category had to be
# inferred from a key name at the point of reading. A net position means the
# opposite thing depending on who holds it -- commercials are price-insensitive
# hedgers and specs are momentum -- so the label travels with the number.
TRADER_CATEGORIES = [
    ("spec", "large_specs", "Large specs",
     "managed money, CTAs, macro funds",
     "momentum; most long at tops and most short at bottoms, which is the edge"),
    ("comm", "commercials", "Commercials",
     "producers, refiners, utilities, merchants",
     "hedging a business, price-insensitive; the other side of the specs"),
    ("small", "small_traders", "Small traders",
     "non-reportable positions",
     "usually positioned with the specs"),
]

# Always reported whether or not they are at an extreme. An extremes-only view
# makes a contract vanish in quiet weeks, which is precisely when knowing it is
# NOT extreme is the useful fact.
ALWAYS_SHOW = ("Gold", "Silver")


def _index(vals: list[float], i: int, weeks: int | None, dates: list[str] | None = None) -> float | None:
    """Williams index of vals[i] over the last `weeks` weeks. With `dates` the window is CALENDAR DAYS (7*(weeks-1) back,
    inclusive), so it means the same thing whatever the report frequency; for strictly weekly rows it selects exactly the
    last `weeks` rows, i.e. what the old row-count window did."""
    if not weeks:
        seg = vals[:i + 1]
    elif dates is None:
        seg = vals[max(0, i - weeks + 1):i + 1]
    else:
        cut = (dt.date.fromisoformat(dates[i]) - dt.timedelta(days=7 * (weeks - 1))).isoformat()
        j = i
        while j > 0 and dates[j - 1] >= cut:
            j -= 1
        seg = vals[j:i + 1]
    lo, hi = min(seg), max(seg)
    return None if hi == lo else round(100 * (vals[i] - lo) / (hi - lo), 1)


def _caveat(as_of: str | None, cadence: dict) -> str:
    wk = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if as_of:
        pub = publish_date(as_of)
        stale = (f"Positions are as of {wk[_weekday(as_of)]} {as_of}, published {wk[pub.weekday()]} {pub.isoformat()}: "
                 f"{(pub - dt.date.fromisoformat(as_of)).days} days stale on arrival")
    else:
        stale = "Positions are days stale on arrival"
    if cadence.get("twice_weekly"):
        stale += "; reports now come twice a week, and the earlier-in-the-week read is shown as interim"
    else:
        stale += " and up to ten before the next one"
    return (stale + ". Extremes persist: 2011 sat pinned at extreme short for months while price kept falling. This is a "
            "condition, not a trigger; price has to stop confirming before it becomes one. The raw and %-of-open-interest "
            "indices disagree by design -- open interest has grown enormously, so the OI measure is the fairer one over long spans.")


def build_cot_response() -> dict:
    groups = []
    cad_dates: list[str] = []
    # ~40 contracts, each a full-history CFTC request or two: one after another this took ~100 s, longer than the web page
    # waits for a cold rebuild (55 s). Four side by side is ~25 s and gentle on the CFTC.
    from concurrent.futures import ThreadPoolExecutor
    flat = [(label, names) for items in CONTRACTS.values() for label, names in items]
    with ThreadPoolExecutor(max_workers=4) as pool:
        raws = dict(zip([label for label, _ in flat], pool.map(lambda it: _raw(it[1]), flat)))
    for group, items in CONTRACTS.items():
        rows = []
        for label, names in items:
            raw = raws[label]
            cad_dates.extend(x["date"] for x in raw[-90:])
            s, interim_obs = _split(_weekly(raw))
            if len(s) < 60:
                rows.append({"contract": label, "status": "no data"})
                continue
            i = len(s) - 1
            spec = [x["spec"] for x in s]
            pct = [x["spec_pct_oi"] for x in s]
            dts = [x["date"] for x in s]
            idx = {k: _index(spec, i, v, dts) for k, v in LOOKBACKS.items()}
            idx_oi = {k: _index(pct, i, v, dts) for k, v in LOOKBACKS.items()}
            interim = None
            if interim_obs is not None:
                sp2, pc2, d2 = spec + [interim_obs["spec"]], pct + [interim_obs["spec_pct_oi"]], dts + [interim_obs["date"]]
                j = len(sp2) - 1
                interim = {"as_of": interim_obs["date"], "spec": round(interim_obs["spec"]),
                           "spec_pct_oi": round(interim_obs["spec_pct_oi"], 1),
                           "change_vs_final": round(interim_obs["spec"] - s[i]["spec"]),
                           "cot_index_3y": _index(sp2, j, LOOKBACKS["3y"], d2),
                           "cot_index_3y_pct_oi": _index(pc2, j, LOOKBACKS["3y"], d2)}
            three = idx.get("3y")
            signal = None
            if three is not None:
                if three <= EXTREME_LOW:
                    signal = "crowd max short — squeeze risk, fuel for continuation is gone"
                elif three >= EXTREME_HIGH:
                    signal = "crowd max long — the marginal buyer is gone"
            rows.append({
                "contract": label, "status": "ok",
                "as_of": s[i]["date"], "open_interest": round(s[i]["oi"]),
                "spec": round(s[i]["spec"]), "comm": round(s[i]["comm"]), "small": round(s[i]["small"]),
                "positions": [
                    {"category": cat, "label": lab, "who": who, "reads_as": reads,
                     "net_contracts": round(s[i][key]),
                     "net_change_4w": round(s[i][key] - s[max(0, i - 4)][key])}
                    for key, cat, lab, who, reads in TRADER_CATEGORIES
                ],
                "spec_pct_oi": round(s[i]["spec_pct_oi"], 1),
                "spec_change_4w": round(s[i]["spec"] - s[max(0, i - 4)]["spec"]),
                "cot_index": idx, "cot_index_pct_oi": idx_oi,
                "signal": signal, "interim": interim,
                "n_weeks": len(s), "history_from": s[0]["date"],
                "spark": [round(x["spec"]) for x in s[-52:]],
            })
        groups.append({"group": group, "contracts": rows})

    ok = [c for g in groups for c in g["contracts"] if c.get("status") == "ok"]
    extremes = sorted(
        [c for c in ok if c["signal"]],
        key=lambda c: (c["cot_index"]["3y"] if c["cot_index"]["3y"] is not None else 50),
    )
    watched = [c for c in ok if c["contract"] in ALWAYS_SHOW]
    as_of = max((c["as_of"] for c in ok), default=None)
    ints = [c for c in ok if c.get("interim")]
    interim_asof = max((c["interim"]["as_of"] for c in ints), default=None)
    cadence = _cadence(cad_dates)
    latest = max([d for d in (as_of, interim_asof) if d], default=None)
    interim_block = None
    if ints:
        interim_block = {"as_of": interim_asof, "published_est": publish_date(interim_asof).isoformat(),
                         "note": ("Read as of a day earlier in the week than the weekly report; a later one is due within days. "
                                  "Shown for information only: the headline numbers, extremes and alerts use the weekly reports."),
                         "contracts": [{"contract": c["contract"], "group": g["group"], "final_as_of": c["as_of"],
                                        "final_cot_index_3y": c["cot_index"]["3y"], **c["interim"]}
                                       for g in groups for c in g["contracts"] if c.get("interim")]}
    return {
        "as_of": as_of,
        "as_of_weekday": (["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][_weekday(as_of)] if as_of else None),
        "published_est": publish_date(as_of).isoformat() if as_of else None,
        "latest_observation": latest,
        "latest_published_est": publish_date(latest).isoformat() if latest else None,
        "interim": interim_block,
        "cadence": cadence,
        # Shown every week, extreme or not -- see ALWAYS_SHOW.
        "watched": [{"contract": c["contract"], "as_of": c["as_of"],
                     "cot_index_3y": c["cot_index"]["3y"],
                     "cot_index_3y_pct_oi": c["cot_index_pct_oi"]["3y"],
                     "positions": c["positions"],
                     "signal": c["signal"],
                     "at_extreme": c["signal"] is not None} for c in watched],
        "trader_categories": [
            {"category": cat, "label": lab, "who": who, "reads_as": reads}
            for _k, cat, lab, who, reads in TRADER_CATEGORIES
        ],
        "source": "CFTC Commitments of Traders, legacy futures-only (public API)",
        "groups": groups,
        "extremes": [{"contract": c["contract"], "cot_index_3y": c["cot_index"]["3y"],
                      "cot_index_3y_pct_oi": c["cot_index_pct_oi"]["3y"],
                      "spec": c["spec"], "signal": c["signal"]} for c in extremes],
        "caveat": _caveat(as_of, cadence),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
