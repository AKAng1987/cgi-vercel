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
  on arrival and up to ten before the next one
- extremes persist. 2011 sat pinned at extreme short for months while price
  kept falling. This is a condition, not a trigger -- price has to stop
  confirming before it becomes one
- contracts get renamed. NYMEX natural gas was "NATURAL GAS" until Feb 2022
  and "NAT GAS NYME" after, which is why history has to be stitched
"""
from __future__ import annotations

import datetime as dt
import json
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
    ],
    "AGRICULTURE": [
        ("Corn", ["CORN - CHICAGO BOARD OF TRADE"]),
        ("Soybeans", ["SOYBEANS - CHICAGO BOARD OF TRADE"]),
        ("Wheat", ["WHEAT-SRW - CHICAGO BOARD OF TRADE"]),
        ("Sugar", ["SUGAR NO. 11 - ICE FUTURES U.S."]),
        ("Coffee", ["COFFEE C - ICE FUTURES U.S."]),
        ("Cotton", ["COTTON NO. 2 - ICE FUTURES U.S."]),
        ("Live Cattle", ["LIVE CATTLE - CHICAGO MERCANTILE EXCHANGE"]),
        ("Lean Hogs", ["LEAN HOGS - CHICAGO MERCANTILE EXCHANGE"]),
    ],
    "RATES": [
        ("2-Year Note", ["UST 2Y NOTE - CHICAGO BOARD OF TRADE"]),
        ("10-Year Note", ["UST 10Y NOTE - CHICAGO BOARD OF TRADE"]),
    ],
    "FX": [
        ("US Dollar Index", ["USD INDEX - ICE FUTURES U.S."]),
        ("Euro FX", ["EURO FX - CHICAGO MERCANTILE EXCHANGE"]),
        ("Japanese Yen", ["JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE"]),
    ],
    "EQUITY": [
        ("S&P 500 (E-mini)", ["E-MINI S&P 500 STOCK INDEX - CHICAGO MERCANTILE EXCHANGE"]),
        ("Nasdaq 100 (E-mini)", ["NASDAQ-100 STOCK INDEX (MINI) - CHICAGO MERCANTILE EXCHANGE"]),
        ("VIX", ["VIX FUTURES - CBOE FUTURES EXCHANGE"]),
    ],
}


def _fetch(name: str) -> list[dict]:
    w = urllib.parse.quote(f"market_and_exchange_names = '{name}'")
    url = f"{BASE}?$select={FIELDS}&$where={w}&$order=report_date_as_yyyy_mm_dd&$limit=50000"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def _series(names: list[str]) -> list[dict]:
    rows: list[dict] = []
    for n in names:
        try:
            rows += _fetch(n)
        except Exception:
            continue
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


def _index(vals: list[float], i: int, weeks: int | None) -> float | None:
    seg = vals[max(0, i - weeks + 1):i + 1] if weeks else vals[:i + 1]
    lo, hi = min(seg), max(seg)
    return None if hi == lo else round(100 * (vals[i] - lo) / (hi - lo), 1)


def build_cot_response() -> dict:
    groups = []
    for group, items in CONTRACTS.items():
        rows = []
        for label, names in items:
            s = _series(names)
            if len(s) < 60:
                rows.append({"contract": label, "status": "no data"})
                continue
            i = len(s) - 1
            spec = [x["spec"] for x in s]
            pct = [x["spec_pct_oi"] for x in s]
            idx = {k: _index(spec, i, v) for k, v in LOOKBACKS.items()}
            idx_oi = {k: _index(pct, i, v) for k, v in LOOKBACKS.items()}
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
                "signal": signal,
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
    return {
        "as_of": max((c["as_of"] for c in ok), default=None),
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
        "caveat": ("Tuesday's close, published Friday -- three days stale on arrival. "
                   "Extremes persist: 2011 sat pinned at extreme short for months while "
                   "price kept falling. This is a condition, not a trigger; price has to "
                   "stop confirming before it becomes one. The raw and %-of-open-interest "
                   "indices disagree by design -- open interest has grown enormously, so "
                   "the OI measure is the fairer one over long spans."),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
