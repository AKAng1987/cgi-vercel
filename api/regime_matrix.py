"""
Regime -> country / currency matrix.

Answers, for any of the 16 Compass x Grid regimes, "what does this regime
mean for each country and each currency" -- the equity leg and the FX leg
side by side, because the country ETF and the USD pair are two expressions
of one view.

NO NEW DATA. Everything here is a re-slice of Cache/backtest/occurrences.json,
which already holds 24 country ETFs and 17 USD pairs (11 of them the majors
this covers). That is why this ships before any foreign yield or policy rate
is onboarded: the question was already answerable.

Three rules this module exists to enforce, each from a defect earlier in the
build:

1. **n travels with every number.** There are only ~8 occurrences of a given
   regime, and a hit rate without its sample size is not a fact. No cell is
   returned without `occurrences`.
2. **The FX sign is stated in words, not left to the reader.** Every pair here
   is quoted USDXXX, so a POSITIVE return is dollar strength and local-currency
   weakness. Inverting that would flip every country read while looking
   entirely normal, so each FX leg carries `usd`/`local` labels derived from
   the sign rather than a bare number.
3. **Absent is not zero.** A country whose ETF is not in the blob returns
   `null` with a reason, never a blank row that reads as flat.
"""

from __future__ import annotations

import backtest_data

SCHEMA_VERSION = 3   # 3: PIN retired (stopped trading 2023)

# Countries in the user's stated order of interest, then the rest of what the
# backtest already covers. `etfs` is ordered: the first one that exists in the
# blob is the headline, the others are kept as alternates (FXI vs KWEB is a
# real distinction -- broad China vs China tech).
#
# `trade` is hand-set, NOT derived, because it decides the SIGN of the currency
# read: an importer wants its own currency strong, an exporter wants it weak.
# This is a first pass for the user to correct -- it is an economic judgement,
# not a measurement, and it is labelled as such in the response.
COUNTRIES: list[dict] = [
    {"code": "PH", "name": "Philippines",   "etfs": ["EPHE"],         "pair": "USDPHP", "trade": "importer", "trade_why": "remittance-driven; imports energy and food"},
    {"code": "CN", "name": "China",         "etfs": ["FXI", "KWEB"],  "pair": "USDCNY", "trade": "exporter", "trade_why": "manufacturing surplus"},
    {"code": "JP", "name": "Japan",         "etfs": ["EWJ", "DXJ"],   "pair": "USDJPY", "trade": "exporter", "trade_why": "autos and capital goods; weak yen flatters earnings"},
    {"code": "KR", "name": "South Korea",   "etfs": ["EWY"],          "pair": "USDKRW", "trade": "exporter", "trade_why": "semiconductors and autos"},
    {"code": "GB", "name": "United Kingdom","etfs": ["EWU"],          "pair": "USDGBP", "trade": "mixed",    "trade_why": "services surplus against a goods deficit"},
    {"code": "EU", "name": "Euro area",     "etfs": ["EWG", "EWI", "EWP", "EWQ"], "pair": "USDEUR", "trade": "mixed", "trade_why": "German surplus inside a mixed bloc"},
    # --- the rest of what the blob already covers, same treatment ---
    {"code": "IN", "name": "India",         "etfs": ["INDA"],        "pair": "USDINR", "trade": "importer", "trade_why": "energy importer"},
    {"code": "ID", "name": "Indonesia",     "etfs": ["EIDO", "IDX"],  "pair": "USDIDR", "trade": "exporter", "trade_why": "commodity exporter"},
    {"code": "TW", "name": "Taiwan",        "etfs": ["EWT"],          "pair": "USDTWD", "trade": "exporter", "trade_why": "semiconductors; TWD is actively managed, so the FX leg is a weak read"},
    {"code": "HK", "name": "Hong Kong",     "etfs": ["EWH"],          "pair": "USDHKD", "trade": "mixed",    "trade_why": "entrepot; HKD is pegged, so the FX leg is near-meaningless"},
    {"code": "SG", "name": "Singapore",     "etfs": ["EWS"],          "pair": "USDSGD", "trade": "exporter", "trade_why": "trade entrepot and refining"},
    {"code": "MY", "name": "Malaysia",      "etfs": ["EWM"],          "pair": "USDMYR", "trade": "exporter", "trade_why": "commodities and electronics"},
    {"code": "VN", "name": "Vietnam",       "etfs": ["VNM"],          "pair": None,     "trade": "exporter", "trade_why": "manufacturing; the dong is a crawling peg (1.7% range over 7 months), so an FX line would read as information it does not carry"},
    {"code": "AU", "name": "Australia",     "etfs": ["EWA"],          "pair": "USDAUD", "trade": "exporter", "trade_why": "iron ore, coal, LNG"},
    {"code": "CA", "name": "Canada",        "etfs": ["EWC"],          "pair": "USDCAD", "trade": "exporter", "trade_why": "energy"},
    {"code": "CH", "name": "Switzerland",   "etfs": ["EWL"],          "pair": "USDCHF", "trade": "exporter", "trade_why": "pharma and precision goods"},
    {"code": "BR", "name": "Brazil",        "etfs": ["EWZ"],          "pair": "USDBRL", "trade": "exporter", "trade_why": "agriculture and iron ore"},
    {"code": "MX", "name": "Mexico",        "etfs": ["EWW"],          "pair": "USDMXN", "trade": "exporter", "trade_why": "manufacturing into the US"},
    {"code": "ZA", "name": "South Africa",  "etfs": ["EZA"],          "pair": "USDZAR", "trade": "exporter", "trade_why": "metals"},
]

# Currencies the central bank manages rather than lets float. An FX leg on one
# of these is a weak or empty read, and the page must say so in words -- a
# managed rate that renders like a floating one invites a conclusion the data
# cannot carry. Explicit set, not inferred from the prose in `trade_why`.
MANAGED_FX = {"TW", "HK", "VN"}

FOCUS = ("PH", "CN", "JP", "KR", "GB", "EU")

# USD pairs with no country block of their own, still worth showing on the
# currency side of the matrix.
EXTRA_PAIRS = ["DXY", "USDTHB", "USDTRY", "USDRUB"]

# Below this, a cell is reported but marked thin rather than ranked. Regimes
# have roughly 8 occurrences each, so this is deliberately low -- the point is
# to flag 1-2 observation cells, not to hide 8-observation ones.
THIN_N = 4


def _cell(blob: dict, symbol: str) -> dict:
    """Presence and history of one symbol, before any regime slicing."""
    entry = blob["tickers"].get(symbol)
    if entry is None:
        return {"symbol": symbol, "present": False,
                "reason": "not in the backtest blob"}
    return {"symbol": symbol, "present": True, "group": entry["group"]}


def _stats(blob: dict, symbol: str, compass_q: int, grid_q: int) -> dict | None:
    entry = blob["tickers"].get(symbol)
    if entry is None:
        return None
    occ = entry["combos"].get(backtest_data._combo_key(grid_q, compass_q), [])
    s = backtest_data.compute_stats(occ)
    if s is None:
        return {"symbol": symbol, "occurrences": 0,
                "reason": "no occurrences of this regime for this symbol"}
    return {
        "symbol": symbol,
        "occurrences": s["count"],
        "thin": s["count"] < THIN_N,
        "hit_rate": s["hit_rate"],
        "avg_return_pct": s["avg_return"],
        "avg_high_pct": s["avg_high_pct"],
        "avg_low_pct": s["avg_low_pct"],
        "edge": s["edge"],
    }


def _fx_read(stats: dict | None) -> dict | None:
    """Put the FX sign into words.

    Every pair in this set is quoted USDXXX. A positive average return is the
    DOLLAR appreciating and the local currency depreciating. This function
    exists so that direction is never inferred from a raw number downstream --
    an inverted FX sign is silent and would flip every country read.
    """
    if stats is None or not stats.get("occurrences"):
        return None
    r = stats["avg_return_pct"]
    if r > 0:
        usd, local = "stronger", "weaker"
    elif r < 0:
        usd, local = "weaker", "stronger"
    else:
        usd, local = "flat", "flat"
    return {**stats, "quoted": "USD per local unit (USDXXX)",
            "usd": usd, "local": local,
            "note": f"USD{usd} vs the local currency, on average, in this regime"}


def _regime_ns(blob: dict, symbol: str) -> dict:
    """Occurrence count for this symbol in all 16 regimes, so the UI can show
    where a country's sample is thin before the user switches to that cell."""
    entry = blob["tickers"].get(symbol)
    if entry is None:
        return {}
    out = {}
    for c in (1, 2, 3, 4):
        for g in (1, 2, 3, 4):
            out[f"C{c}G{g}"] = len(entry["combos"].get(backtest_data._combo_key(g, c), []))
    return out


def _best_and_worst(blob: dict, symbol: str, min_n: int = 5) -> dict | None:
    """Which regime this symbol actually pays in, across all 16 -- the
    "EPHE is a G1 trade" claim, computed rather than asserted."""
    entry = blob["tickers"].get(symbol)
    if entry is None:
        return None
    scored = []
    for c in (1, 2, 3, 4):
        for g in (1, 2, 3, 4):
            occ = entry["combos"].get(backtest_data._combo_key(g, c), [])
            s = backtest_data.compute_stats(occ)
            if s and s["count"] >= min_n:
                scored.append({"regime": f"C{c}G{g}", "occurrences": s["count"],
                               "hit_rate": s["hit_rate"],
                               "avg_return_pct": s["avg_return"],
                               "edge": s["edge"]})
    if not scored:
        return None
    scored.sort(key=lambda r: -r["avg_return_pct"])
    return {"min_n": min_n, "best": scored[0], "worst": scored[-1],
            "ranked": scored}


def build_matrix(compass_q: int, grid_q: int, min_n: int = 5) -> dict:
    """One regime, every country and currency."""
    blob = backtest_data._read_blob()
    if blob is None:
        return {"schema_version": SCHEMA_VERSION, "error": "no backtest data refreshed yet",
                "compass_q": compass_q, "grid_q": grid_q, "countries": []}

    countries = []
    for c in COUNTRIES:
        etfs = [_stats(blob, s, compass_q, grid_q) for s in c["etfs"]]
        etfs = [e for e in etfs if e is not None]
        absent = [s for s in c["etfs"] if blob["tickers"].get(s) is None]
        headline = etfs[0] if etfs else None
        pair_stats = _stats(blob, c["pair"], compass_q, grid_q) if c["pair"] else None
        countries.append({
            "code": c["code"], "name": c["name"], "focus": c["code"] in FOCUS,
            "trade": c["trade"], "trade_why": c["trade_why"],
            "trade_basis": "hand-set economic judgement, not measured -- it sets the sign of the currency read",
            "equity": headline,
            "equity_alternates": etfs[1:],
            "equity_absent": absent or None,
            "currency": _fx_read(pair_stats),
            "currency_absent": (c["pair"] is None) or (pair_stats is None),
            # Three different states, previously two. A pair that is SET but
            # missing from the blob rendered a bare "no pair" with no reason
            # -- indistinguishable from a country that never had one. Every
            # newly onboarded pair passes through that state between being
            # loaded and the next backtest rebuild.
            "currency_state": (
                "managed_untracked" if c["pair"] is None and c["code"] in MANAGED_FX
                else "untracked" if c["pair"] is None
                else "pending" if pair_stats is None
                else "managed" if c["code"] in MANAGED_FX
                else "ok"),
            # One sentence of why, for every non-"ok" state, so the page never
            # has to show a bare "no pair".
            "currency_note": (
                c["trade_why"] if c["pair"] is None and c["code"] in MANAGED_FX
                else "no USD pair tracked for this currency" if c["pair"] is None
                else (f"{c['pair']} is loaded but has no entry in the backtest blob yet, "
                      f"so the regime stats are pending the next refresh")
                if pair_stats is None
                else c["trade_why"] if c["code"] in MANAGED_FX
                else None),
            "regime_n": _regime_ns(blob, c["etfs"][0]),
            "regime_ranking": _best_and_worst(blob, c["etfs"][0], min_n=min_n),
        })

    extras = []
    for p in EXTRA_PAIRS:
        s = _stats(blob, p, compass_q, grid_q)
        if s is not None:
            extras.append(_fx_read(s) or s)

    return {
        "schema_version": SCHEMA_VERSION,
        "last_refreshed_at": blob.get("last_refreshed_at"),
        "compass_q": compass_q,
        "grid_q": grid_q,
        "regime": f"C{compass_q}G{grid_q}",
        "min_n": min_n,
        "thin_below": THIN_N,
        "focus_order": list(FOCUS),
        "countries": countries,
        "extra_pairs": extras,
        "fx_convention": "All pairs quoted USDXXX: a positive return is USD strength and local-currency weakness.",
        "caveat": ("Each regime has roughly 8 occurrences in the record. Every cell "
                   "carries its own n and none should be read without it."),
    }
