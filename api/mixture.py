"""
mixture.py -- what each ticker pays across the two regimes the next release
can leave us in, weighted by how likely each is.

THE IDEA
Each release moves exactly one axis (markov_data's docstring), so the regime
after the next release is not a 16-way distribution. It is two points: the
regime we are in, or the one with that single axis flipped. CGI already holds
both halves -- the BACKTEST returns in each regime (the "CGI . now" and "CGI .
if next flips" watchlists) and the probability of the flip (markov_data). This
module is only the column that weights one by the other:

    mixture = (1 - p) * E[return | now]  +  p * E[return | if flips]
    spread  = | E[return | now]  -  E[return | if flips] |

THE SPREAD IS THE POINT, NOT THE MIXTURE
Two tickers can sit at the same mixture for opposite reasons. One pays about
the same either way. The other earns its whole edge on the flip NOT happening.
Both look identical in a ranked list. Spread is the number that separates them,
and `sign_flips` marks the extreme case: the answer reverses depending on the
release. Aggregate risk -- a screen full of names that are secretly one bet --
is what hurt in 2024, and this is the column that shows it.

HONESTY
  * Both samples are small (a few occurrences each). The mixture is a
    probability-weighted average of two small samples and is NOT a forecast;
    n for each side travels with every row and nothing is returned without it.
  * p is not known. markov_data gives a historical estimate and, where it
    exists, a market-implied one. Both mixtures are returned so the reader sees
    the range. They are never averaged into one number.
  * Nothing here writes a regime label or touches a threshold. It reads.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics
from typing import Optional

import backtest_data as bd
import markov_data as md
import watchlists as wl

# Bump on any change to the response shape: cache.SCHEMA_FROM_MODULE points at
# this, so the new shape cannot be served stale from a cached old one.
SCHEMA_VERSION = 7   # 7: market_label. 6: 6: symbols no longer guessed. 5: 5: URA retired. 4: 4: retired tickers filtered out of the blob. 3: 3: the market p_flip it reads (driver table) is now publication-lagged

# A thin "if flips" cell is expected -- by construction there are fewer
# occurrences of the destination regime. These floors are deliberately lower
# than the leaderboard's min_occ=5, because that is what the watchlists already
# do for the flip side; a ticker below them is dropped, not shown with a
# number it cannot support.
MIN_NOW = 5
MIN_FLIP = 3


def _mean_return(entry: Optional[dict], grid_q: int, compass_q: int) -> tuple[Optional[float], int, Optional[float]]:
    """(mean return, n, standard error of that mean) for one regime cell."""
    if entry is None:
        return None, 0, None
    occ = entry["combos"].get(bd._combo_key(grid_q, compass_q), [])
    s = bd.compute_stats(occ)
    if s is None:
        return None, 0, None
    rets = [o["return_pct"] for o in occ]
    se = statistics.stdev(rets) / math.sqrt(len(rets)) if len(rets) >= 2 else None
    return s["avg_return"], s["count"], se


def _reverses(r_now: float, r_flip: float, se_now: Optional[float], se_flip: Optional[float]) -> bool:
    """The sign changes AND the gap is bigger than the noise in the two means.

    A bare sign test badges USDCNY (-0.02% -> +0.04%) as a regime reversal,
    which it is not: both means are indistinguishable from zero. Scaling the
    test by each ticker's own standard error needs no hand-picked cutoff and
    keeps a 12-point swing on a volatile name while discarding a 0.06-point
    wobble on a quiet one.
    """
    if r_now == 0 or r_flip == 0 or (r_now > 0) == (r_flip > 0):
        return False
    if se_now is None or se_flip is None:
        return False
    return abs(r_now - r_flip) > math.sqrt(se_now ** 2 + se_flip ** 2)


def _mix(p: Optional[float], now: float, flip: float) -> Optional[float]:
    if p is None:
        return None
    return (1.0 - p) * now + p * flip


def build_mixture_response() -> dict:
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    blob = bd._read_blob()
    if blob is None:
        return {"schema_version": SCHEMA_VERSION, "error": "no backtest data refreshed yet", "rows": []}

    cur, dest, nxt = wl.next_regimes(today)

    # p_flip for THIS release: history, and market-implied where it exists.
    # Matched on date and axis so a calendar reorder cannot pair the wrong p
    # with the wrong regime pair.
    upcoming = md.build_markov_response()["upcoming"]
    match = next((u for u in upcoming if u["date"] == nxt["date"] and u["axis"] == nxt["axis"]), None)
    if match is None:
        return {"schema_version": SCHEMA_VERSION, "rows": [],
                "error": f"no Markov forecast found for {nxt['type']} on {nxt['date']}"}
    p_hist = match["p_flip"]
    p_mkt = (match.get("market") or {}).get("p_flip")

    rows = []
    for sym, entry in blob["tickers"].items():
        r_now, n_now, se_now = _mean_return(entry, cur["grid"], cur["compass"])
        r_flip, n_flip, se_flip = _mean_return(entry, dest["grid"], dest["compass"])
        if r_now is None or r_flip is None or n_now < MIN_NOW or n_flip < MIN_FLIP:
            continue
        mix_h = _mix(p_hist, r_now, r_flip)
        mix_m = _mix(p_mkt, r_now, r_flip)
        rows.append({
            "ticker": sym,
            "group": entry["group"],
            "n_now": n_now,
            "n_flip": n_flip,
            "ret_now": round(r_now, 2),
            "ret_flip": round(r_flip, 2),
            "mix_hist": round(mix_h, 2),
            "mix_market": round(mix_m, 2) if mix_m is not None else None,
            "spread": round(abs(r_now - r_flip), 2),
            "sign_flips": _reverses(r_now, r_flip, se_now, se_flip),
        })
    rows.sort(key=lambda r: -r["mix_hist"])

    return {
        "schema_version": SCHEMA_VERSION,
        "last_refreshed_at": blob.get("last_refreshed_at"),
        "release": {"date": nxt["date"], "type": nxt["type"], "axis": nxt["axis"]},
        "regime_now": f"C{cur['compass']}G{cur['grid']}",
        "regime_if_flips": f"C{dest['compass']}G{dest['grid']}",
        "p_flip_history": p_hist,
        "p_flip_market": p_mkt,
        # What that second probability IS, from markov_data: "Market" (fed funds futures,
        # liquidity only), "Drivers" (in-sample driver table, not a price), or "Model".
        "market_label": (match.get("market") or {}).get("label") or "Market",
        "p_flip_gap": round(p_mkt - p_hist, 3) if p_mkt is not None else None,
        "min_now": MIN_NOW,
        "min_flip": MIN_FLIP,
        "n_tickers": len(rows),
        "rows": rows,
        "unit": "average return per regime occurrence, %",
        "caveat": ("A probability-weighted average of two small samples, not a forecast. "
                   "Every row carries both n. Mixtures are shown at the historical p_flip "
                   "and, where available, the market-implied one -- never averaged. "
                   "Spread is how much the answer depends on the release; sign_flips marks "
                   "tickers whose average return reverses sign if the axis flips by more "
                   "than the combined standard error of the two samples."),
    }
