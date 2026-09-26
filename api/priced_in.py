"""
FUNDAMENTALS: what growth the price is already assuming.

FUNDAMENTALS deliberately shipped with NO valuation -- the factor answers "is
this business capturing the theme", not "is it cheap", and a P/E stapled on
would have turned it into a stock screen. This module adds the layer the user
asked for instead, which is a different and better question: not whether a
multiple is high, but what it implies about growth.

TWO READINGS, SIDE BY SIDE
--------------------------
1. THE GRID -- the user's own 100-cell table (revenue growth 5-50% x domicile
   10Y 2.0-6.5%), interpolated so any pair of inputs returns a multiple.

   It is an ANCHOR, not a model, and the page says so. Solving each cell for
   the discount rate a standard perpetuity would need gives a rate that RISES
   with the growth input -- at a 2.0% 10Y it runs 8.1% at 5% growth to 50.9%
   at 50% growth. A discount rate driven by its own input cannot be a
   derivation. The user's position is reasonable and is why it is kept: "a
   rough approximation of how much the PE should be based on the rev growth
   and interest rate ... keeps a grounded estimate based on the same
   fundamentals". The qualitative behaviour is right (multiple up with growth,
   down with rates) and it ties valuation to revenue growth, which is
   Damodaran's first measure and already the backbone of this factor.

2. THE REVERSE-DCF -- the check, with every assumption visible. See
   implied_growth(): the user's stated objection is to black boxes, so the
   grid is kept but LABELLED, and the transparent alternative sits beside it.

Where the two disagree, the gap is the output worth looking at. It is
information about the grid, not an error to reconcile away.
"""

from __future__ import annotations

from typing import Optional

SCHEMA_VERSION = 1

# The user's grid, verbatim. Rows are revenue growth %, columns are the
# domicile 10-year yield %. Values are the justified P/E.
GRID_GROWTH = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50)
GRID_RATE = (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5)
GRID = {
    5:  (34, 27, 22, 19, 17, 15, 13, 12, 11, 10),
    10: (41, 32, 29, 23, 19, 17, 16, 14, 13, 12),
    15: (50, 39, 32, 27, 23, 20, 18, 16, 15, 13),
    20: (60, 47, 38, 32, 27, 24, 21, 19, 17, 15),
    25: (72, 56, 45, 38, 32, 28, 24, 22, 19, 17),
    30: (86, 66, 54, 44, 38, 32, 28, 25, 22, 19),
    35: (102, 78, 63, 52, 44, 38, 32, 28, 25, 22),
    40: (120, 92, 74, 61, 51, 43, 37, 33, 29, 24),
    45: (141, 108, 86, 70, 59, 50, 43, 37, 32, 28),
    50: (165, 125, 99, 81, 67, 57, 49, 42, 36, 31),
}

GRID_PROVENANCE = (
    "A rough heuristic anchor of unknown provenance, not a valuation model. "
    "Solving its cells for an implied discount rate gives a rate that rises "
    "with the growth you type in, which is circular -- so treat it as a ground "
    "wire, not a derivation."
)


def _bracket(xs: tuple, x: float) -> tuple[int, int, float]:
    """Indices either side of x, and the fraction between them. Clamped at the
    ends; the caller is told separately when clamping happened."""
    if x <= xs[0]:
        return 0, 0, 0.0
    if x >= xs[-1]:
        return len(xs) - 1, len(xs) - 1, 0.0
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            span = xs[i + 1] - xs[i]
            return i, i + 1, (x - xs[i]) / span if span else 0.0
    return len(xs) - 1, len(xs) - 1, 0.0


def grid_multiple(growth_pct: float, rate_pct: float) -> dict:
    """Bilinear interpolation over the grid.

    Inputs outside the grid are CLAMPED and flagged as extrapolation rather
    than silently pinned -- a company growing 120% or a 1% 10-year is outside
    anything the table was built for, and saying so is the difference between
    a lookup and a fabrication.
    """
    gi0, gi1, gf = _bracket(GRID_GROWTH, growth_pct)
    ri0, ri1, rf = _bracket(GRID_RATE, rate_pct)
    g0, g1 = GRID_GROWTH[gi0], GRID_GROWTH[gi1]
    v00, v01 = GRID[g0][ri0], GRID[g0][ri1]
    v10, v11 = GRID[g1][ri0], GRID[g1][ri1]
    top = v00 + (v01 - v00) * rf
    bot = v10 + (v11 - v10) * rf
    val = top + (bot - top) * gf

    out_of_range = []
    if growth_pct < GRID_GROWTH[0] or growth_pct > GRID_GROWTH[-1]:
        out_of_range.append(
            f"growth {growth_pct:.1f}% is outside the grid's {GRID_GROWTH[0]}-{GRID_GROWTH[-1]}%")
    if rate_pct < GRID_RATE[0] or rate_pct > GRID_RATE[-1]:
        out_of_range.append(
            f"10Y {rate_pct:.2f}% is outside the grid's {GRID_RATE[0]}-{GRID_RATE[-1]}%")
    return {
        "justified_multiple": round(val, 1),
        "growth_pct": round(growth_pct, 2),
        "rate_pct": round(rate_pct, 2),
        "extrapolated": bool(out_of_range),
        "extrapolation_note": "; ".join(out_of_range) or None,
        "provenance": GRID_PROVENANCE,
    }


# ── the reverse-DCF, as the transparent check ───────────────────────────
# Defaults are stated here rather than buried, and every one is meant to be
# overridden from the page. The output moves a long way on them, which is the
# point: an assumption you can see is one you can argue with.
DEFAULTS = {
    "equity_risk_premium_pct": 4.5,   # long-run US equity risk premium
    "fade_years": 10,                 # high growth decays linearly over this
    "terminal_growth_pct": 2.5,       # roughly long-run nominal GDP
}


def implied_growth(multiple: float, rate_pct: float,
                   erp_pct: Optional[float] = None,
                   fade_years: Optional[int] = None,
                   terminal_growth_pct: Optional[float] = None) -> dict:
    """The growth rate a given multiple implies, by bisection on a fading-growth
    DCF of earnings.

    Deliberately simple and fully stated: earnings grow at g for `fade_years`,
    decaying linearly to terminal growth, discounted at the 10Y plus an equity
    risk premium, then a Gordon terminal value. It is not a precision
    instrument -- it is the thing that can be argued with, which the grid
    cannot be.
    """
    erp = DEFAULTS["equity_risk_premium_pct"] if erp_pct is None else erp_pct
    yrs = DEFAULTS["fade_years"] if fade_years is None else fade_years
    tg = DEFAULTS["terminal_growth_pct"] if terminal_growth_pct is None else terminal_growth_pct
    r = (rate_pct + erp) / 100.0
    tgf = tg / 100.0
    if r <= tgf:
        return {"error": "discount rate must exceed terminal growth",
                "discount_rate_pct": round(r * 100, 2)}

    def pv(g_pct: float) -> float:
        g = g_pct / 100.0
        e, val = 1.0, 0.0
        for t in range(1, yrs + 1):
            gt = g + (tgf - g) * (t - 1) / max(yrs - 1, 1)   # linear fade
            e *= (1 + gt)
            val += e / ((1 + r) ** t)
        val += (e * (1 + tgf)) / (r - tgf) / ((1 + r) ** yrs)
        return val

    lo, hi = -50.0, 200.0
    if pv(hi) < multiple:
        return {"error": f"multiple {multiple} exceeds anything this model reaches",
                "max_multiple_at_200pct_growth": round(pv(hi), 1)}
    if pv(lo) > multiple:
        return {"error": f"multiple {multiple} is below the model's floor",
                "min_multiple": round(pv(lo), 1)}
    for _ in range(80):
        mid = (lo + hi) / 2
        if pv(mid) < multiple:
            lo = mid
        else:
            hi = mid
    return {
        "implied_growth_pct": round((lo + hi) / 2, 2),
        "multiple": multiple,
        "assumptions": {
            "risk_free_pct": round(rate_pct, 2),
            "equity_risk_premium_pct": erp,
            "discount_rate_pct": round(r * 100, 2),
            "fade_years": yrs,
            "terminal_growth_pct": tg,
        },
        "note": ("Every assumption above is adjustable and the answer moves a "
                 "long way on them. This starts a conversation; it is not a "
                 "target price."),
    }


def compare(actual_growth_pct: float, rate_pct: float,
            actual_multiple: Optional[float] = None, **kw) -> dict:
    """Both readings together, plus the gap between them."""
    g = grid_multiple(actual_growth_pct, rate_pct)
    out = {"grid": g, "reverse_dcf": None, "priced_in_gap": None,
           "actual_multiple": actual_multiple}
    if actual_multiple is None:
        out["actual_multiple_note"] = (
            "Market cap is not in SEC filings, so the actual multiple is not "
            "computed here. Without it the grid gives a justified multiple and "
            "nothing to compare it against -- inventing one from elsewhere "
            "would make this look more precise than it is.")
        return out
    rd = implied_growth(actual_multiple, rate_pct, **kw)
    out["reverse_dcf"] = rd
    if "implied_growth_pct" in rd:
        out["priced_in_gap"] = {
            "implied_minus_actual_pp": round(rd["implied_growth_pct"] - actual_growth_pct, 2),
            "reads_as": ("the price assumes MORE growth than reported"
                         if rd["implied_growth_pct"] > actual_growth_pct
                         else "the price assumes LESS growth than reported"),
        }
        out["grid_vs_dcf"] = {
            "grid_multiple": g["justified_multiple"],
            "actual_multiple": actual_multiple,
            "note": "Where these disagree, that is information about the grid.",
        }
    return out
