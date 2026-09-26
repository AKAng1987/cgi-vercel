"""
fundamentals_data.py -- FUNDAMENTALS: who actually earns the theme.

Layer 3 of the LIVE brief. Themes (layer 2) say a trade is working; this says
which companies inside it are capturing the money. That is the gap the AI
capex thesis names out loud -- the applications layer is where real revenue
has to be told apart from a press release.

SOURCE: SEC XBRL, via sec_xbrl.py. See that module's header for why, at
length: FMP's free tier gates per symbol (MU and CRM denied on the same call
AMD and NVDA answered) and caps history at 5 sequential quarters;
TradingView has no server-side API. SEC has full history, true year-on-year,
every filer, and needs no key.

ORGANISED BY THEME, NOT BY WATCHLIST
Constituents hang off the theme names in themes_data.THEMES, so the factor
inherits the universe CGI already tracks rather than a hand-kept list that
goes stale. Keys are checked against that dict, so a theme renamed there
fails loudly instead of silently emptying this table.

DAMODARAN'S FIVE, ALL AS RATE OF CHANGE
Levels are priced; the change in the level re-rates the stock. The read
throughout is the SECOND derivative -- a company going from +30% to +20%
revenue growth is decelerating while still growing fast, and that is exactly
what separates "the theme is working" from "this company is capturing it".

  1 revenue growth     YoY, and the change in YoY (percentage points)
  2 margin growth      gross and operating margin in pp, and their change
  3 return to holders  (buybacks + dividends) as a share of operating cash
                       flow -- "what share of the cash it generated came
                       back". A share, not a yield: SEC filings carry no
                       market cap, and inventing one would be worse.
  4 interest rate risk interest burden (interest / operating income) and the
                       refinancing wall (debt due within a year vs cash)
  5 risk of ruin       Altman Z'' plus cash runway against burn

WHAT IS DELIBERATELY NOT HERE
No valuation. SEC filings do not carry a share price, and a P/E stapled on
from elsewhere would make this look like a stock screen. This factor answers
"is the business capturing the theme", not "is it cheap".
"""
from __future__ import annotations

import datetime as dt
import logging
import statistics
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import cache
import cgi_state
import etf_holdings as eh
import fundamentals_history as fh
import sec_xbrl as sx
import themes_data as td

MIN_YOY_POINTS = 2

# A 20-F/40-F filer reports annually, so 270 days old is current for them and
# would be four quarters stale for anyone else.
ANNUAL_STALE_DAYS = 400

# Seasonally-adjusted sequential growth.
#
# WHY IT EXISTS: year-on-year cannot see a one-quarter inflection. MU turned on
# 2025-05-29 (sequential -7.5% -> +15.5%) while its YoY was still falling, so
# the acceleration metric read -1.7pp -- "decelerating" -- at the exact quarter
# the business turned, and YoY did not confirm for two more.
#
# WHY IT IS NOT AN ALERT: it was backtested before being allowed to notify, and
# it failed. Across 134 companies and 4,949 company-quarters, the share of
# fires followed by YoY acceleration turning positive the NEXT quarter was:
#
#     surprise >= 0.0pp   750 fires   46.3%
#     surprise >= 4.0pp   223 fires   45.7%
#     surprise >= 12.2pp   67 fires   52.2%
#     surprise >= 20.6pp   26 fires   46.2%
#     base rate (any quarter)         50.5%
#
# Lift 0.91x to 1.03x -- a coin flip at every threshold. MU was one anecdote.
# So this is reported as DESCRIPTIVE only: it says how the latest quarter
# compares with that company's own typical same-quarter, which is genuinely
# useful to read, and it makes no claim about what happens next.
SEASONAL_MIN_OBS = 4
SEASONAL_PCTL = {"p50": 0.0, "p75": 4.0, "p90": 12.2, "p95": 20.6, "p5": -16.6,
                 "n": 5262, "companies": 134, "on": "2026-09-26"}
_logger = logging.getLogger("cgi_api.fundamentals_data")

# ---------------------------------------------------------------------------
# FALLBACK constituents only.
#
# The live list is DERIVED from what each theme's ETFs actually hold (see
# etf_holdings.py). This hand-picked list is kept solely so a failed fetch
# degrades to something labelled rather than to an empty table -- it is never
# silently mixed with real holdings.
#
# It was the weakest input in the factor and the derivation proved it: the
# hand list for "steel / metals" was NUE, STLD, X, while XME actually holds
# CLF, STLD, RS, RGLD, NUE, FCX, NEM and CMC -- and X had been acquired.
FALLBACK_CONSTITUENTS: dict[str, list[str]] = {
    "AI": ["NVDA", "MSFT", "GOOGL", "META"],
    "semis / memory": ["NVDA", "AMD", "AVGO", "MU", "INTC"],
    "Korea / DRAM": ["MU"],            # the listable DRAM pure-play; Samsung/SK are local
    "cloud / software": ["MSFT", "AMZN", "CRM", "NOW", "DDOG", "SNOW"],
    "cyber": ["PANW", "CRWD", "FTNT"],
    "power / grid": ["VST", "CEG", "NRG", "ETN"],
    "energy: upstream": ["XOM", "COP", "EOG", "DVN"],
    "energy: refiners": ["VLO", "MPC", "PSX"],
    "energy: midstream": ["WMB", "KMI", "ET"],
    "copper": ["FCX", "SCCO"],
    "gold": ["NEM", "AEM"],
    "steel / metals": ["NUE", "STLD", "X"],
    "uranium / nuclear": ["CCJ", "LEU"],
    "defense": ["LMT", "RTX", "NOC", "GD"],
    "shipping / logistics": ["MATX", "FDX", "UNP"],
    "banks": ["JPM", "BAC", "WFC", "USB"],
    "homebuilders": ["DHI", "LEN", "PHM"],
    "retail / consumer": ["WMT", "COST", "TGT"],
    "biotech / healthcare": ["LLY", "ABBV", "AMGN"],
}

# Top N by weight per theme, after unioning that theme's ETF proxies. Five
# keeps the whole universe near 116 names; the SEC pull is ~0.3s each, and the
# page is rendered by a Vercel server component with a hard function timeout,
# so this number is a LATENCY budget as much as an editorial choice.
TOP_PER_THEME = 5


def _unreachable() -> set[str]:
    """Symbols the last build could not read, so the next derivation can skip
    them and take the next holding by weight instead.

    Without this a theme loses a slot for every OTC line N-PORT names that is
    not an SEC filer at all (CAHPF, GLCNF and four others), leaving three
    usable constituents where five were asked for. Self-healing: a name that
    starts filing drops off the list on the next build.
    """
    try:
        return set(cgi_state.get("unreachable_symbols").get("symbols", []))
    except Exception:
        return set()


def derive_constituents() -> dict:
    """theme -> constituents, from the funds' own books, with provenance.

    Cached for 7 days: reading 60 ETFs takes ~90s and their holdings barely
    move week to week.
    """
    def _compute() -> dict:
        out, prov = {}, {}
        for theme, proxies in td.THEMES.items():
            tickers, p = eh.top_constituents(proxies, n=20, min_weight=0.5)
            skip = _unreachable()
            usable = [t for t in tickers if t not in skip]
            out[theme] = usable[:TOP_PER_THEME]
            prov[theme] = p
        return {"as_of": dt.date.today().isoformat(),
                "top_per_theme": TOP_PER_THEME,
                "constituents": out, "provenance": prov}

    return cache.get_or_fetch("etf_constituents", _compute)


def theme_constituents() -> tuple[dict[str, list[str]], dict, list[str]]:
    """(theme -> names, provenance, themes that fell back to the hand list)."""
    try:
        d = derive_constituents()
    except Exception:
        _logger.exception("[fundamentals] constituent derivation failed; using fallback")
        return dict(FALLBACK_CONSTITUENTS), {}, sorted(FALLBACK_CONSTITUENTS)
    derived = d.get("constituents") or {}
    out, fell_back = {}, []
    for theme in td.THEMES:
        names = derived.get(theme) or []
        if not names:
            names = FALLBACK_CONSTITUENTS.get(theme, [])
            if names:
                fell_back.append(theme)
        if names:
            out[theme] = names
    return out, d.get("provenance", {}), fell_back


# The AI layer cake, in your words. Kept SEPARATE from the theme map because
# the thesis claim is that these layers are NOT moving together --
# infrastructure slowing, utilities falling, chips splitting AMD from NVDA.
# A per-layer rollup is the only way to see that, and it is what to check
# each month.
AI_LAYERS: dict[str, list[str]] = {
    "energy": ["VST", "CEG", "NRG", "ETN"],
    "chips": ["NVDA", "AMD", "AVGO", "MU"],
    "infrastructure": ["VRT", "ANET", "DLR", "SMCI"],
    # SPCX is included at the user's instruction, on his thesis that the listed
    # entity is primarily an AI-model exposure. Recorded for accuracy: CIK
    # 1181412 is SPACE EXPLORATION TECHNOLOGIES CORP (Nasdaq, SIC 7370), and
    # Grok is built by xAI -- a separate Musk company SpaceX invested in, not
    # this filer. It also produces no reading yet: only 2 quarterly revenue
    # points exist, so it cannot yield a year-on-year figure until it has four
    # more quarters. It will start contributing on its own once it does.
    # PLTR also appears under applications; a name can sit in two layers.
    "models": ["SPCX", "PLTR"],
    "applications": ["CRM", "NOW", "PLTR", "DDOG", "TWLO", "PANW"],
}

# ---------------------------------------------------------------------------
# The "who pays whom" map. One row per link, per the spec's data model.
#
# The half no vendor sells, and the reason it is hand-built: the only HARD
# number is the SEC 10% customer-concentration disclosure. Everything else is
# direction and importance -- which is what matters for reading one company's
# result through to a name that has NOT reported yet.
#
# Never assume a link. Each row carries its source and confidence, and
# speculative rows stay labelled speculative rather than quietly averaged in.
LINKS: list[dict] = [
    {"payer": "MSFT", "payee": "NVDA", "for": "GPUs / accelerators",
     "importance": "key vendor", "source": "capex guidance + vendor commentary",
     "found": "2026-09-25", "confidence": "confirmed"},
    {"payer": "META", "payee": "NVDA", "for": "GPUs / accelerators",
     "importance": "key vendor", "source": "public capex guidance",
     "found": "2026-09-25", "confidence": "confirmed"},
    {"payer": "NVDA", "payee": "MU", "for": "HBM / high-bandwidth memory",
     "importance": "key vendor", "source": "MU commentary: HBM sold out",
     "found": "2026-09-25", "confidence": "confirmed"},
    {"payer": "NVDA", "payee": "VRT", "for": "power / thermal for racks",
     "importance": "key vendor", "source": "reference architectures",
     "found": "2026-09-25", "confidence": "likely"},
    {"payer": "CRM", "payee": "TWLO", "for": "messaging / customer comms",
     "importance": "minor", "source": "your thesis: CRM messaging strength implies TWLO spend",
     "found": "2026-09-25", "confidence": "speculative"},
    {"payer": "CRM", "payee": "DDOG", "for": "observability",
     "importance": "minor", "source": "vendor case studies",
     "found": "2026-09-25", "confidence": "likely"},
    {"payer": "DLR", "payee": "VST", "for": "power purchase for datacentres",
     "importance": "key vendor", "source": "PPA announcements",
     "found": "2026-09-25", "confidence": "likely"},
]


def _pp(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(x * 100.0, 2)


def _trend(series: list[tuple[str, float]], label: str) -> dict:
    """Latest YoY, prior YoY, and the change in percentage points. The sign
    of that change is accelerating vs decelerating."""
    if len(series) < MIN_YOY_POINTS:
        return {"status": "insufficient history", "n_points": len(series)}
    latest, prior = series[0][1], series[1][1]
    d = (latest - prior) * 100.0
    return {
        "status": "ok", "measure": label, "as_of": series[0][0],
        "yoy_pct": _pp(latest), "prior_yoy_pct": _pp(prior),
        "acceleration_pp": round(d, 2),
        "direction": ("accelerating" if d > 0.5 else "decelerating" if d < -0.5 else "flat"),
        "history": [{"period": p, "yoy_pct": _pp(v)} for p, v in series[:12]],
    }


def _margin_series(f: dict) -> tuple[list[tuple[str, float]], str]:
    """Gross margin as a RATIO per quarter, newest first, plus how it was
    derived. GrossProfit is absent for energy and miners (XOM, VST, FCX), so
    revenue minus cost of revenue is the fallback."""
    rev = sx.series(f, "revenue")
    gp = sx.series(f, "gross_profit")
    basis = "GrossProfit / Revenue"
    if not gp:
        cost = sx.series(f, "cost_of_revenue")
        if not cost:
            return [], "unavailable"
        gp = {d: rev[d] - cost[d] for d in set(rev) & set(cost)}
        basis = "(Revenue - CostOfRevenue) / Revenue"
    common = sorted(set(rev) & set(gp), reverse=True)
    return [(d, gp[d] / rev[d]) for d in common if rev[d]], basis


def _margin_trend(f: dict) -> dict:
    """Margin is a level in pp, so the rate of change is the DIFFERENCE in
    margin year on year, not a percentage growth of a percentage -- which
    would be unreadable."""
    s, basis = _margin_series(f)
    if len(s) < 5:
        return {"status": "insufficient history", "n_points": len(s), "basis": basis}
    d = dict(s)
    ds = sorted(d, reverse=True)
    pts = []
    for e in ds:
        base = [x for x in ds if sx.YOY_DAYS[0] <= sx._days(x, e) <= sx.YOY_DAYS[1]]
        if base:
            pts.append((e, d[e] - d[base[0]]))
    if len(pts) < MIN_YOY_POINTS:
        return {"status": "insufficient history", "n_points": len(pts), "basis": basis}
    return {
        "status": "ok", "basis": basis, "as_of": pts[0][0],
        "margin_pct": _pp(d[ds[0]]),
        "margin_change_yoy_pp": round(pts[0][1] * 100, 2),
        "prior_change_yoy_pp": round(pts[1][1] * 100, 2),
        "direction": ("expanding" if pts[0][1] > 0.002
                      else "compressing" if pts[0][1] < -0.002 else "flat"),
        "history": [{"period": p, "change_yoy_pp": round(v * 100, 2)} for p, v in pts[:12]],
    }


def _ttm(s: dict[str, float], n: int = 4) -> Optional[float]:
    if len(s) < n:
        return None
    return sum(s[d] for d in sorted(s, reverse=True)[:n])


def _seasonal_qoq(f: dict) -> dict:
    """Latest sequential growth against that company's own median for the same
    fiscal quarter. Descriptive -- see SEASONAL_PCTL for why it is not a signal."""
    rev = sx.series(f, "revenue")
    fp = sx.fiscal_periods(f, "revenue")
    q = sx.qoq(rev)
    if not q:
        return {"status": "no data"}
    buckets: dict[str, list[float]] = {}
    for d, v in q:
        buckets.setdefault(fp.get(d) or f"M{d[5:7]}", []).append(v)
    d, v = q[0]
    key = fp.get(d) or f"M{d[5:7]}"
    peers = buckets.get(key, [])
    if len(peers) < SEASONAL_MIN_OBS:
        return {"status": "insufficient history", "n_same_quarter": len(peers),
                "qoq_pct": round(v * 100, 2)}
    norm = statistics.median(peers)
    return {
        "status": "ok", "as_of": d, "fiscal_period": key,
        "qoq_pct": round(v * 100, 2),
        "seasonal_norm_pct": round(norm * 100, 2),
        "surprise_pp": round((v - norm) * 100, 2),
        "n_same_quarter": len(peers),
        "note": ("how this quarter compares with this company's own typical "
                 + key + ". Descriptive: backtested and it does NOT predict "
                 "year-on-year turning (0.91-1.03x lift, 4,949 company-quarters)."),
    }


def _company(sym: str) -> dict:
    f = sx.company_facts(sym)
    if not f:
        return {"symbol": sym, "status": "no SEC data",
                "read": {"verdict": "unknown", "why": "not found in SEC XBRL"}}

    out: dict = {"symbol": sym, "status": "ok",
                 "name": f.get("entityName"), "cik": f.get("cik"),
                 "sector": sx.sector(sym)}

    today = dt.date.today()

    def _age(d: str) -> int:
        return (today - dt.date.fromisoformat(d)).days

    # Read the filer at ITS OWN cadence rather than assuming quarterly.
    # Decided from the facts, not from domicile: a foreign issuer may file
    # quarterly and a domestic one may not, and only the filing tells you
    # which. BHP has eight half-year revenue facts and no quarterly ones at
    # all, so a quarterly-shaped read saw a company with no data.
    how = sx.cadence(f, "revenue")
    rev = sx.periods(f, "revenue", how)
    stale_days = sx.STALE_BY_CADENCE[how]
    annual_mode = how != "quarterly"

    # Staleness guard. A dead concept reads exactly like a current one, which
    # is how the NVDA tag-switch bug reported FY2020 revenue as the latest
    # quarter and produced a confident, wrong verdict. The bound now follows
    # the cadence: 453 days is stale for a quarterly filer and normal for an
    # annual one between filings.
    if rev:
        newest = max(rev)
        age = _age(newest)
        if age > stale_days:
            return {"symbol": sym, "status": "stale",
                    "name": f.get("entityName"), "cik": f.get("cik"),
                    "sector": sx.sector(sym), "cadence": how,
                    "latest_quarter": newest, "stale_days": age,
                    "tags_seen": sx.tags_used(f, "revenue"),
                    "read": {"verdict": "unknown",
                             "why": (f"newest {how} figure ends {newest}, {age}d ago -- "
                                     f"past the {stale_days}d bound for a {how} filer")}}

    out["cadence"] = how
    out["basis"] = ("quarterly" if how == "quarterly"
                    else f"{how} (20-F/40-F filer)")
    # Kept under the old name because rollups, the watchlist and the page all
    # key off it: it means "not quarterly", i.e. excluded from quarterly medians.
    out["annual_only"] = annual_mode
    out["revenue"] = _trend(sx.yoy(rev), "revenue")
    out["margin"] = _margin_trend(f)
    # Quarterly filers only: a 20-F filer has no sequential quarters at all.
    out["seasonal_qoq"] = {"status": "n/a (annual filer)"} if annual_mode else _seasonal_qoq(f)
    out["operating_income"] = _trend(sx.yoy(sx.series(f, "operating_income")), "operating income")

    # 3 return to shareholders, as a share of the cash actually generated.
    bb, dv, ocf = (sx.series(f, k) for k in ("buybacks", "dividends", "op_cash_flow"))
    t_bb, t_dv, t_ocf = _ttm(bb), _ttm(dv), _ttm(ocf)
    if t_ocf and t_ocf > 0:
        returned = (t_bb or 0.0) + (t_dv or 0.0)
        out["return_to_shareholders"] = {
            "status": "ok", "basis": "trailing 4 quarters, share of operating cash flow",
            "buybacks_ttm": t_bb, "dividends_ttm": t_dv, "op_cash_flow_ttm": t_ocf,
            "payout_of_ocf_pct": round(returned / t_ocf * 100, 1),
        }
    else:
        out["return_to_shareholders"] = {"status": "no data"}

    # 4 interest rate risk: the burden now, and the wall next year.
    ie, cash = sx.series(f, "interest_expense"), sx.series(f, "cash")
    oi = sx.series(f, "operating_income")
    t_ie, t_oi = _ttm(ie), _ttm(oi)
    due = sx.latest(sx.series(f, "debt_due_1y"))
    l_cash = sx.latest(cash)
    dc, dn = sx.latest(sx.series(f, "debt_current")), sx.latest(sx.series(f, "debt_noncurrent"))
    rr: dict = {"status": "ok"}
    if t_ie and t_oi and t_oi > 0:
        rr["interest_burden_pct"] = round(t_ie / t_oi * 100, 1)
        rr["interest_burden_note"] = "interest expense as a share of operating income, trailing 4q"
    if due and l_cash and l_cash[1]:
        rr["debt_due_1y"] = due[1]
        rr["cash"] = l_cash[1]
        rr["wall_covered_by_cash_x"] = round(l_cash[1] / due[1], 2) if due[1] else None
    if dc or dn:
        rr["total_debt"] = (dc[1] if dc else 0) + (dn[1] if dn else 0)
    if len(rr) == 1:
        rr = {"status": "no data"}
    out["rate_risk"] = rr

    # 5 risk of ruin. Altman Z'' (the non-manufacturing / private variant)
    # because it uses BOOK equity -- SEC filings carry no market cap, and the
    # original Z needs one. Z'' bands are 1.1 / 2.6, not 1.81 / 2.99.
    ta, tl = sx.latest(sx.series(f, "assets")), sx.latest(sx.series(f, "liabilities"))
    ca, cl = sx.latest(sx.series(f, "current_assets")), sx.latest(sx.series(f, "current_liabilities"))
    re_, eq = sx.latest(sx.series(f, "retained_earnings")), sx.latest(sx.series(f, "equity"))
    ruin: dict = {"status": "no data"}
    if ta and ta[1]:
        A = ta[1]
        # AMD does not tag Liabilities; derive it from assets minus equity.
        liab = tl[1] if tl else (A - eq[1] if eq else None)
        wc = (ca[1] - cl[1]) if (ca and cl) else None
        ebit = t_oi
        if liab and wc is not None and re_ and ebit is not None and eq:
            z = (6.56 * wc / A + 3.26 * re_[1] / A + 6.72 * ebit / A + 1.05 * eq[1] / liab)
            # A company that has never cumulatively earned (accumulated
            # deficit) is pushed deep into the distress band by the retained-
            # earnings term alone -- SNOW scored -4.7 that way while holding
            # net cash. That is the formula meeting a company it was not
            # designed for, not a solvency warning, so the band is suppressed
            # and the reason is reported instead of a misleading label.
            deficit = re_[1] < 0
            ruin = {
                "status": "ok", "altman_z2": round(z, 2),
                "band": (None if deficit
                         else "distress" if z < 1.1 else "grey" if z < 2.6 else "safe"),
                "variant": "Z'' (book equity), bands 1.1 / 2.6",
                "accumulated_deficit": deficit,
                "note": ("Z'' is used because SEC filings carry no market cap. "
                         + ("This company has an accumulated deficit, which dominates Z'' "
                            "and drags it negative regardless of solvency -- the band is "
                            "withheld rather than shown as distress; read FCF and cash instead."
                            if deficit else
                            "Asset-light balance sheets still score high; read the band loosely.")),
            }
    cap = _ttm(sx.series(f, "capex"))
    if t_ocf is not None and cap is not None:
        fcf = t_ocf - cap
        ruin = dict(ruin)
        ruin["fcf_ttm"] = fcf
        if fcf < 0 and l_cash:
            ruin["cash_runway_quarters"] = round(l_cash[1] / (abs(fcf) / 4), 1)
    out["risk_of_ruin"] = ruin

    # The verdict uses revenue and margin only -- the two measures that are
    # quarterly and therefore current. Folding in a trailing-year figure
    # would date the verdict without saying so.
    r, m = out["revenue"], out["margin"]
    if r.get("status") == "ok" and m.get("status") == "ok":
        ra, ma = r["acceleration_pp"], m["margin_change_yoy_pp"]
        if ra > 0.5 and ma > 0.2:
            v, w = "capturing", "revenue accelerating into expanding margin"
        elif ra > 0.5:
            v, w = "buying growth", "revenue accelerating but margin not expanding"
        elif ra < -0.5 and ma < -0.2:
            v, w = "rolling over", "revenue decelerating into compressing margin"
        elif ra < -0.5:
            v, w = "slowing", "revenue decelerating"
        else:
            v, w = "holding", "no clear acceleration either way"
        out["read"] = {"verdict": v, "why": w, "basis": "quarterly, true YoY from SEC XBRL"}
    elif r.get("status") == "ok":
        ra = r["acceleration_pp"]
        out["read"] = {"verdict": "accelerating" if ra > 0.5 else "slowing" if ra < -0.5 else "holding",
                       "why": "revenue only; margin unavailable", "basis": "quarterly, true YoY"}
    else:
        out["read"] = {"verdict": "unknown", "why": r.get("status", "no data")}
    return out


def _rollup(names: list[str], comp: dict[str, dict]) -> dict:
    have = [comp[s] for s in names if s in comp and comp[s]["read"]["verdict"] != "unknown"]
    if not have:
        return {"status": "no data", "n": 0}
    counts: dict[str, int] = {}
    for c in have:
        counts[c["read"]["verdict"]] = counts.get(c["read"]["verdict"], 0) + 1
    # Annual filers are excluded from the acceleration median on purpose: a
    # change in YoY measured over a YEAR is not the same quantity as one
    # measured over a quarter, and averaging them would quietly corrupt every
    # theme rollup an annual name happens to sit in.
    def _acc(annual: bool) -> list[float]:
        return sorted(c["revenue"]["acceleration_pp"] for c in have
                      if c.get("revenue", {}).get("acceleration_pp") is not None
                      and bool(c.get("annual_only")) is annual)

    accel = _acc(False)
    # Reported SEPARATELY rather than folded in. Gold, China and Japan derive
    # entirely from 20-F/40-F filers, so a quarterly median is genuinely None
    # for them -- but showing nothing at all would hide a real reading. Two
    # numbers, never one blended number.
    accel_annual = _acc(True)
    return {
        "status": "ok", "n": len(have), "verdicts": counts,
        "median_revenue_acceleration_pp": accel[len(accel) // 2] if accel else None,
        "n_annual_excluded": sum(1 for c in have if c.get("annual_only")),
        "median_annual_acceleration_pp": (accel_annual[len(accel_annual) // 2]
                                          if accel_annual else None),
        "capturing": [c["symbol"] for c in have if c["read"]["verdict"] == "capturing"],
        "rolling_over": [c["symbol"] for c in have if c["read"]["verdict"] == "rolling over"],
        "leaders": [c["symbol"] for c in sorted(
            have, key=lambda x: -(x.get("revenue", {}).get("acceleration_pp") or -1e9))[:3]],
    }


def build_fundamentals_response(active_themes: list[str] | None = None) -> dict:
    active = set(active_themes or [])
    constituents, provenance, fell_back = theme_constituents()
    universe = sorted({s for v in constituents.values() for s in v}
                      | {s for v in AI_LAYERS.values() for s in v})

    # One companyfacts request per name. Workers are held to 3 deliberately:
    # SEC would allow 10/sec, but each payload is multi-megabyte before
    # sec_xbrl trims it, so the ceiling here is MEMORY on Render's instance,
    # not the rate limit.
    with ThreadPoolExecutor(max_workers=3) as ex:
        rows = list(ex.map(_company, universe))
    comp = {r["symbol"]: r for r in rows}
    ok = {k: v for k, v in comp.items() if v.get("status") == "ok"}

    # Feed the fall-through. Only names that genuinely could not be read are
    # recorded, so a transient SEC hiccup does not permanently exile a company.
    try:
        bad = sorted(k for k, v in comp.items()
                     if v.get("status") in ("no SEC data", "stale"))
        if bad:
            cgi_state.put("unreachable_symbols", {"symbols": bad,
                                                  "as_of": dt.date.today().isoformat()})
    except Exception:
        _logger.exception("[fundamentals] could not record unreachable symbols")

    # Record any newly-filed quarter and collect what changed. Safe on every
    # build: a company whose as_of is unchanged writes nothing.
    try:
        changes = fh.record(list(ok.values()))
    except Exception:
        _logger.exception("[fundamentals] history record failed")
        changes = []

    themes = [{"theme": t, "constituents": names, "is_live": t in active,
               "source": ("hand-seeded fallback" if t in fell_back
                          else "derived from ETF holdings"),
               **_rollup(names, ok)} for t, names in constituents.items()]
    themes.sort(key=lambda t: (not t["is_live"], t["theme"]))
    layers = [{"layer": k, "constituents": v, **_rollup(v, ok)} for k, v in AI_LAYERS.items()]

    return {
        "as_of": dt.date.today().isoformat(),
        "source": "SEC XBRL companyfacts (data.sec.gov) -- free, no key, all filers",
        "method": ("Damodaran's five as rate of change. True year-on-year per quarter "
                   "(same quarter prior year), so no seasonal contamination. The read is "
                   "the change in YoY, in percentage points -- the second derivative."),
        "coverage": {"universe": len(universe), "with_data": len(ok),
                     "missing": sorted(set(universe) - set(ok)),
                     "themes_on_fallback": fell_back},
        "constituent_provenance": provenance,
        "limits": [
            "No valuation: SEC filings carry no share price, so this says whether a business is capturing the theme, not whether it is cheap.",
            "Constituents are the top 5 by weight of what each theme's ETFs actually hold (State Street daily files, else SEC N-PORT).",
            "N-PORT names holdings but never tickers, so foreign listings that do not resolve to a US symbol are dropped -- EWY is 55% SK Hynix and Samsung, neither of which can be reached this way.",
            "Korea/DRAM has no readable constituent at all: SK Hynix's OTC line files no XBRL, and the Korean bank ADRs (KB, SHG) last filed usable figures in 2023 and 2024. This is a wall in what the SEC holds, not a gap in the code.",
            "Seasonal sequential growth is DESCRIPTIVE, not a signal: it was backtested over 4,949 company-quarters and does not predict year-on-year turning (0.91-1.03x lift vs a 50.5% base rate).",
            "20-F/40-F filers are read ANNUALLY and marked so; their acceleration is reported as a separate annual median and never mixed into the quarterly one.",
            "MTH files no consolidated revenue concept in companyfacts at all -- its largest 2026 fact is operating cash flow -- so it cannot be read from this source.",
            "An ETF does not always mean what its theme label says: KBE/KRE are equal-weighted REGIONAL banks, so the banks theme derives small regionals rather than the majors.",
            "Return to shareholders is a share of operating cash flow, not a yield, for the same reason.",
            "Altman Z'' uses book equity and still flatters asset-light balance sheets.",
            "Q4 is derived from the annual figure where a filer never tagged it; that recovered 5 of MU's 35 quarters.",
            "Concept chains are MERGED, not chosen between: filers switch tags mid-history and reading only the first would truncate the series silently.",
            "Any series whose newest quarter is over 200 days old is refused as stale rather than reported -- IFRS filers (AEM) have no us-gaap revenue concept and drop out here.",
        ],
        "changes": changes,
        "surprise_thresholds": {"up_pp": fh.SURPRISE_UP, "down_pp": fh.SURPRISE_DOWN,
                                "measured": fh.MEASURED},
        "companies": [ok[s] for s in sorted(ok)],
        "themes": themes,
        "ai_layers": layers,
        "links": LINKS,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    }


def assert_theme_keys() -> list[str]:
    return [k for k in FALLBACK_CONSTITUENTS if k not in td.THEMES]
