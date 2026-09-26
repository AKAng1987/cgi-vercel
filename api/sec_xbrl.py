"""
sec_xbrl.py -- Company fundamentals straight from SEC XBRL.

WHY THIS AND NOT A VENDOR
Mapped the alternatives on 2026-09-25 and this one won on every axis that
matters:

  FMP free        gates PER SYMBOL. AMD and NVDA returned data; MU, CRM and
                  most of the theme universe returned ACCESS DENIED on the
                  identical call. It also caps quarterly history at 5 rows
                  and returns SEQUENTIAL quarter-on-quarter growth, which is
                  seasonally contaminated and has to be chained back into
                  YoY. ETF holdings and transcripts need the Ultimate plan.
  TradingView     no server-side API at all -- only the MCP, so data can
                  reach CGI only through a scheduled routine. Its scanner
                  host was also returning 429 across every endpoint while
                  this was being built, and the ECONOMICS group is already
                  broken (see axis_drivers.py), so two factors would share
                  one point of failure.
  SEC XBRL        free, no key, no per-symbol gating, all 10,413 filers,
                  full history (MU has 30 quarters back to 2017 against
                  FMP's 5), TRUE year-on-year with no chaining needed, and
                  it is the filed number itself rather than someone's
                  normalisation of it.

Render needs only a User-Agent header, so the API fetches this live. That
removed the whole "no FMP key on Render" constraint the first draft of the
fundamentals factor was built around.

WHAT THIS MODULE HANDLES, AND WHY EACH PART EXISTS
  concept fallbacks   companies do not use the same tags. GrossProfit is
                      absent for XOM, VST and FCX (energy and miners do not
                      report it), Liabilities is absent for AMD, and
                      PaymentsOfDividendsCommonStock is absent for most.
                      Each measure therefore resolves through an ordered
                      fallback chain, and a derived fallback (revenue minus
                      cost of revenue) where no single tag exists.
  restatements        the same period appears once per filing that mentions
                      it. The LATEST filed value wins -- that is the
                      restated, most accurate figure.
  Q4 derivation       many filers never tag Q4 as a 90-day period; it only
                      appears inside the 10-K annual figure. MU is missing
                      three Augusts for exactly this reason. Where an annual
                      fact and exactly three quarters of the same fiscal
                      year exist, Q4 is derived as the difference. Without
                      this, a quarter of the history silently disappears.
  duration windows    80-100 days counts as a quarter, 350-380 as a year.
                      Filers' periods wobble by a few days around 13 weeks.

SEC asks for a descriptive User-Agent and allows 10 requests/second. One
companyfacts call returns every concept for a company, so the universe
costs one request per name, not one per measure.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import urllib.error
import urllib.request
from typing import Optional

UA = "CGI macro-regime research (ang.arvin@ymail.com)"
FACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
TICKERS = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

QUARTER_DAYS = (80, 100)
SEMIANNUAL_DAYS = (165, 200)
ANNUAL_DAYS = (350, 380)
YOY_DAYS = (330, 400)      # same quarter, prior year

# How long a filer may go between reports before its newest figure is stale.
# Derived from the filer's OWN cadence rather than one global constant: BHP at
# 453 days is not a dead company, it is an annual filer between filings, and a
# single quarterly-shaped bound cannot express that difference.
# An annual filer's figure is expected once a year PLUS a filing lag of up to
# ~4 months, so 500 days tolerates BHP between filings (453) while still
# refusing KB (999) and TSM (633), whose SEC data genuinely stops in 2023-24.
STALE_BY_CADENCE = {"quarterly": 200, "semiannual": 300, "annual": 500}

# A filer reports at least every ~92 days. If the newest quarter this module
# can see is older than this, something is wrong with the CONCEPT MAPPING, not
# with the company -- that is exactly how the NVDA tag-switch bug presented
# (a dead series read as current, reporting FY2020 as the latest quarter).
# Callers must treat a stale series as no data rather than as a reading.
STALE_DAYS = 200

_logger = logging.getLogger("cgi_api.sec_xbrl")

# measure -> ordered tag fallback chain. First tag present wins.
CONCEPTS: dict[str, list[str]] = {
    "revenue": [
        # Banks first: revenue for a bank is net of interest expense, and JPM
        # and WFC let their plain "Revenues" tag go stale (2025-12 and 2020-09)
        # while RevenuesNetOfInterestExpense stayed current. Non-banks do not
        # carry this tag at all, so leading with it costs them nothing.
        "RevenuesNetOfInterestExpense",
        # HWC and ONB use this and nothing else that is current -- their
        # RevenuesNetOfInterestExpense stops in 2011, so without it both looked
        # like dead companies. It is GROSS interest income, not net of interest
        # expense, so a bank whose history spans both concepts has a genuine
        # discontinuity at the join; that is still better than losing 15 years.
        "InterestAndDividendIncomeOperating",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
    ],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfServices"],
    "gross_profit": ["GrossProfit"],
    "operating_income": [
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock", "PaymentsForRepurchaseOfEquity"],
    "dividends": ["PaymentsOfDividendsCommonStock", "PaymentsOfDividends"],
    "interest_expense": ["InterestExpense", "InterestExpenseDebt", "InterestIncomeExpenseNet"],
    "op_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    # instant (balance sheet) concepts
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "debt_current": ["DebtCurrent", "LongTermDebtCurrent"],
    "debt_noncurrent": ["LongTermDebtNoncurrent", "LongTermDebt"],
    # the refinancing wall, where the filer tags it
    "debt_due_1y": ["LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths",
                    "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextRollingTwelveMonths"],
}

# Foreign private issuers file under IFRS, in the ifrs-full namespace, and
# carry no us-gaap facts worth reading -- AEM's us-gaap revenue stops in 2010
# while ifrs-full:Revenue runs to 2025. Checked only after us-gaap yields
# nothing, so a domestic filer is unaffected.
IFRS_CONCEPTS: dict[str, list[str]] = {
    "revenue": ["Revenue", "RevenueFromContractsWithCustomers"],
    "cost_of_revenue": ["CostOfSales"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["ProfitLossFromOperatingActivities"],
    "net_income": ["ProfitLoss"],
    "buybacks": ["PaymentsForRepurchaseOfEntitysOwnEquityInstruments"],
    "dividends": ["DividendsPaidClassifiedAsFinancingActivities", "DividendsPaid"],
    "interest_expense": ["FinanceCosts", "InterestExpense"],
    "op_cash_flow": ["CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["Equity", "EquityAttributableToOwnersOfParent"],
    "retained_earnings": ["RetainedEarnings"],
    "cash": ["CashAndCashEquivalents"],
    "current_assets": ["CurrentAssets"],
    "current_liabilities": ["CurrentLiabilities"],
    "debt_current": ["ShorttermBorrowings", "CurrentPortionOfLongtermBorrowings"],
    "debt_noncurrent": ["LongtermBorrowings", "NoncurrentPortionOfLongtermBorrowings"],
}

INSTANT = {"assets", "liabilities", "equity", "retained_earnings", "cash",
           "current_assets", "current_liabilities", "debt_current",
           "debt_noncurrent", "debt_due_1y"}


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        return json.loads(raw.decode("utf-8"))


_cik_cache: Optional[dict[str, int]] = None


def cik_map() -> dict[str, int]:
    """ticker -> CIK, from the SEC's own file. Cached per process."""
    global _cik_cache
    if _cik_cache is None:
        d = _get(TICKERS)
        _cik_cache = {v["ticker"]: int(v["cik_str"]) for v in d.values()}
    return _cik_cache


# Every tag this module can use, flattened once at import. A companyfacts
# payload carries 350-780 tags and decompresses to 3-8MB per company; the
# universe is ~314MB, and parsed into Python dicts it is several times that
# again. Render's instance would not survive holding it, so each payload is
# trimmed to these tags INSIDE the worker and the full object is released
# immediately -- peak memory becomes one payload per worker rather than the
# whole universe. This ran fine locally on a machine with room and would have
# died in production; it is the same mistake class as the 33s LIVE load.
_WANTED: frozenset[str] = frozenset(
    [t for tags in CONCEPTS.values() for t in tags]
    + [t for tags in IFRS_CONCEPTS.values() for t in tags]
)


def company_facts(ticker: str) -> Optional[dict]:
    """Fetch and immediately trim to the tags CONCEPTS can actually use.

    Returns the same {"facts": {"us-gaap": {...}}} shape callers expect, so
    series() is unchanged -- only the volume is different.
    """
    cik = cik_map().get(ticker.upper())
    if cik is None:
        return None
    try:
        full = _get(FACTS.format(cik=cik))
    except urllib.error.HTTPError as e:
        _logger.warning("[sec] %s (CIK %s) -> HTTP %s", ticker, cik, e.code)
        return None
    except Exception as e:                      # network/timeout: one name, not the page
        _logger.warning("[sec] %s (CIK %s) -> %s", ticker, cik, e)
        return None
    src = full.get("facts", {})
    keep = {ns: {k: v for k, v in src.get(ns, {}).items() if k in _WANTED}
            for ns in ("us-gaap", "ifrs-full") if ns in src}
    return {"entityName": full.get("entityName"), "cik": full.get("cik"), "facts": keep}


_sector_cache: dict[str, Optional[str]] = {}


def sector(ticker: str) -> Optional[str]:
    """The filer's own SIC description, e.g. "Semiconductors & Related Devices".

    Taken from the SEC rather than a vendor's sector taxonomy: it is the
    classification the company files under, it is free, and it needs no extra
    mapping table to maintain. Memoised per process because it never changes.
    """
    t = ticker.upper()
    if t in _sector_cache:
        return _sector_cache[t]
    cik = cik_map().get(t)
    if cik is None:
        _sector_cache[t] = None
        return None
    try:
        # _get already returns parsed JSON here (unlike etf_holdings._get,
        # which returns bytes) -- an easy confusion between the two modules.
        d = _get(SUBMISSIONS.format(cik=cik))
        _sector_cache[t] = d.get("sicDescription") or None
    except Exception:
        _sector_cache[t] = None
    return _sector_cache[t]


def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def _nodes(facts: dict, measure: str) -> list[tuple[str, dict]]:
    """EVERY tag in the chain that this filer uses, in chain order.

    Taking only the first present tag was a real bug: NVDA used
    RevenueFromContractWithCustomerExcludingAssessedTax from 2017 to 2022 and
    then switched to Revenues, so "first present tag" silently read a series
    that had been dead for four years and reported FY2020 as the latest
    quarter. Filers switch concepts, so the chain has to be MERGED, not
    chosen between.
    """
    f = facts.get("facts", {})
    g = f.get("us-gaap", {})
    ifrs = f.get("ifrs-full", {})
    # BOTH namespaces, us-gaap first, appended rather than chosen between.
    # Returning early on any us-gaap hit was wrong: AEM carries a us-gaap
    # Revenues tag that died in 2010 alongside a live ifrs-full Revenue, so
    # "us-gaap exists" short-circuited to the dead one -- the same mistake as
    # taking the first tag in a chain. series() merges per period, so the
    # freshest source wins where they overlap.
    return ([(t, g[t]) for t in CONCEPTS.get(measure, []) if t in g]
            + [(t, ifrs[t]) for t in IFRS_CONCEPTS.get(measure, []) if t in ifrs])


def _usd_rows(node: dict) -> list[dict]:
    units = node.get("units", {})
    for k in ("USD", "USD/shares"):
        if k in units:
            return units[k]
    return next(iter(units.values()), []) if units else []


def series(facts: dict, measure: str) -> dict[str, float]:
    """end_date -> value.

    Duration measures return QUARTERLY values, with Q4 derived from the annual
    figure where the filer never tagged it. Instant measures return the
    balance-sheet value as of that date.

    Two merges happen here, and both matter:
      across FILINGS   the same period appears once per filing that mentions
                       it; the LATEST filed value wins, which is the restated
                       and most accurate figure.
      across TAGS      a filer that switched concepts mid-history has its
                       periods filled from every tag in the chain, with
                       earlier-in-chain (more specific) tags preferred where
                       both cover the same period. Without this, a switch
                       truncates the series at the switch date.

    The join between two tags can carry a small definitional discontinuity,
    which can make the single YoY point spanning it slightly off. That is
    strictly better than losing four years of history.
    """
    nodes = _nodes(facts, measure)
    if not nodes:
        return {}

    if measure in INSTANT:
        merged: dict[str, float] = {}
        for _tag, node in nodes:
            best: dict[str, tuple[str, float]] = {}
            for r in _usd_rows(node):
                e, filed, v = r.get("end"), r.get("filed", ""), r.get("val")
                if e is None or v is None:
                    continue
                if e not in best or filed > best[e][0]:
                    best[e] = (filed, float(v))
            for e, (_f, v) in best.items():
                merged.setdefault(e, v)
        return merged

    q_all: dict[str, float] = {}
    a_all: dict[tuple, float] = {}
    for _tag, node in nodes:
        q: dict[str, tuple[str, float]] = {}
        a: dict[tuple, tuple[str, float]] = {}
        for r in _usd_rows(node):
            st, e, filed, v = r.get("start"), r.get("end"), r.get("filed", ""), r.get("val")
            if not (st and e) or v is None:
                continue
            n = _days(st, e)
            if QUARTER_DAYS[0] <= n <= QUARTER_DAYS[1]:
                if e not in q or filed > q[e][0]:
                    q[e] = (filed, float(v))
            elif ANNUAL_DAYS[0] <= n <= ANNUAL_DAYS[1]:
                k = (st, e)
                if k not in a or filed > a[k][0]:
                    a[k] = (filed, float(v))
        for e, (_f, v) in q.items():
            q_all.setdefault(e, v)
        for k, (_f, v) in a.items():
            a_all.setdefault(k, v)

    out = dict(q_all)
    # Derive the missing Q4: an annual window containing exactly three known
    # quarters implies the fourth. Only fills a date that is genuinely absent.
    for (st, e), tot in a_all.items():
        inside = [(d, v) for d, v in out.items() if st < d <= e]
        if len(inside) == 3 and e not in out:
            out[e] = tot - sum(v for _d, v in inside)
    return out


def tags_used(facts: dict, measure: str) -> list[str]:
    """Which tags actually fed a measure -- for auditing a filer that switched."""
    return [t for t, _ in _nodes(facts, measure)]


def fiscal_periods(facts: dict, measure: str) -> dict[str, str]:
    """end_date -> fiscal period label (Q1/Q2/Q3/Q4/FY) as the filer reports it.

    Needed to compare like with like when seasonally adjusting: a retailer's Q4
    is not comparable to its Q1, so the norm has to be per fiscal quarter, not
    pooled. Falls back to the period-end MONTH where `fp` is absent, which
    separates the same four periods for any filer with a stable year end.
    """
    out: dict[str, str] = {}
    for _tag, node in _nodes(facts, measure):
        for r in _usd_rows(node):
            st, e, fp = r.get("start"), r.get("end"), r.get("fp")
            if not (st and e):
                continue
            if not (QUARTER_DAYS[0] <= _days(st, e) <= QUARTER_DAYS[1]):
                continue
            out.setdefault(e, fp if fp in ("Q1", "Q2", "Q3", "Q4") else f"M{e[5:7]}")
    return out


def qoq(s: dict[str, float]) -> list[tuple[str, float]]:
    """[(end_date, sequential growth)] newest first.

    Sequential growth is the FASTEST read a filing can give -- it is the first
    thing that moves at an inflection -- but it is seasonally contaminated,
    which is why the factor reads YoY. seasonal_qoq() below removes the
    seasonality without giving up the speed.
    """
    ds = sorted(s)
    out = []
    for i in range(1, len(ds)):
        prev = s[ds[i - 1]]
        # only consecutive quarters; a gap makes the comparison meaningless
        if prev and prev > 0 and 60 <= _days(ds[i - 1], ds[i]) <= 130:
            out.append((ds[i], s[ds[i]] / prev - 1.0))
    out.reverse()
    return out


def _duration_series(facts: dict, measure: str, window: tuple[int, int]) -> dict[str, float]:
    """end_date -> value for facts whose period length falls inside `window`.
    Latest filing wins on restatement, as everywhere else."""
    best: dict[str, tuple[str, float]] = {}
    for _tag, node in _nodes(facts, measure):
        for r in _usd_rows(node):
            st, e, filed, v = r.get("start"), r.get("end"), r.get("filed", ""), r.get("val")
            if not (st and e) or v is None:
                continue
            if window[0] <= _days(st, e) <= window[1]:
                if e not in best or filed > best[e][0]:
                    best[e] = (filed, float(v))
    return {e: v for e, (_f, v) in best.items()}


def semiannual(facts: dict, measure: str) -> dict[str, float]:
    """Half-year periods. Australian and several Asian issuers report this way
    -- BHP has 8 half-year revenue facts and no quarterly ones at all, so
    without this it reads as a company with no data."""
    return _duration_series(facts, measure, SEMIANNUAL_DAYS)


def cadence(facts: dict, measure: str = "revenue") -> str:
    """What rhythm this filer actually reports on.

    Decided from the facts themselves rather than guessed from domicile: a
    foreign issuer may file quarterly and a domestic one may not, and the
    filing tells you which. Whichever period length yields the most USABLE
    year-on-year pairs wins, because that is the thing the factor needs -- a
    filer with many stale quarterly facts and a live annual series should be
    read annually.
    """
    scored = []
    for name, fn in (("quarterly", series), ("semiannual", semiannual), ("annual", annual)):
        try:
            scored.append((len(yoy(fn(facts, measure))), name))
        except Exception:
            scored.append((0, name))
    scored.sort(key=lambda x: (-x[0], ("quarterly", "semiannual", "annual").index(x[1])))
    return scored[0][1] if scored[0][0] else "quarterly"


def periods(facts: dict, measure: str, how: str) -> dict[str, float]:
    """The series at a given cadence -- one entry point so callers never have
    to remember which of the three functions matches which rhythm."""
    return {"quarterly": series, "semiannual": semiannual, "annual": annual}[how](facts, measure)


def annual(facts: dict, measure: str) -> dict[str, float]:
    """end_date -> value, for ANNUAL periods only.

    20-F and 40-F filers report once a year, so they have no quarterly facts to
    derive anything from. Reading them annually is the difference between the
    company appearing with a slower measure and vanishing entirely.
    """
    nodes = _nodes(facts, measure)
    if not nodes or measure in INSTANT:
        return {}
    best: dict[str, tuple[str, float]] = {}
    for _tag, node in nodes:
        for r in _usd_rows(node):
            st, e, filed, v = r.get("start"), r.get("end"), r.get("filed", ""), r.get("val")
            if not (st and e) or v is None:
                continue
            if ANNUAL_DAYS[0] <= _days(st, e) <= ANNUAL_DAYS[1]:
                if e not in best or filed > best[e][0]:
                    best[e] = (filed, float(v))
    return {e: v for e, (_f, v) in best.items()}


def yoy(s: dict[str, float]) -> list[tuple[str, float]]:
    """[(end_date, yoy_fraction)] newest first. TRUE year-on-year: the same
    quarter a year earlier, matched by date, so no chaining and no seasonal
    contamination."""
    ds = sorted(s)
    out = []
    for e in ds:
        base = [x for x in ds if YOY_DAYS[0] <= _days(x, e) <= YOY_DAYS[1]]
        if not base:
            continue
        prev = s[base[-1]]
        if prev and prev > 0:
            out.append((e, s[e] / prev - 1.0))
    out.reverse()
    return out


def latest(s: dict[str, float]) -> Optional[tuple[str, float]]:
    if not s:
        return None
    k = max(s)
    return k, s[k]
