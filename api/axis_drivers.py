"""
axis_drivers.py -- "What moves each axis." Event study + conditional flip
rates for the four Tesseract axes, from price-history and model-history.

For each axis, history is cut into consecutive release-cadence windows
(CPI/GDP ~30 days, FOMC ~45, SLOOS ~91). At the start of each window we
record the axis state and a handful of leading "driver" readings (30-day
moves in commodities, yields, spreads, relative strength). The window is
a "flip" if the axis changed inside it.

Per axis, per starting state, per driver:
  - mean reading in flip windows vs. non-flip windows
  - terciles of the reading over all windows in that state
  - P(flip | reading in low / mid / high tercile)
  - today's reading, its tercile, and P(flip | that tercile)

conditioned_p_flip = mean of the per-driver P(flip | current tercile).
Equal-weight, no fitting -- deliberately a table you can read, not a
model you have to trust. The unconditional base rate is shown next to it.

Windows are fixed-length and anchored to the first available date, not
to actual historical release dates (those aren't stored before 2026).
That is an approximation: a flip is credited to the window it fell in,
which is the release window to within a few days. Good enough for
tercile-level conditional rates; not for anything finer.

Result is cached in S3 (Cache/macro/axis_drivers.json, 24h) because it
needs ~14 full-history DynamoDB pulls.
"""

from __future__ import annotations

import bisect
import datetime as dt
from typing import Optional

import boto3

import markov_data as md
import release_calendar as cal

REGION = "ap-southeast-1"
PRICE_TABLE = "cmon-stage-backend-price-history"
LOOKBACK_ROWS = 21  # ~30 calendar days of trading rows
MIN_TERCILE_N = 8   # a tercile needs this many windows before its rate is used

CADENCE_DAYS = {"inflation": 30, "growth": 30, "liquidity": 45, "credit": 91}

# (label, symbol or (a, b), kind)
#   pct        30-day % change                 (daily price series)
#   diff       30-day change in level          (yields, spreads, breakevens)
#   ratio_pct  30-day % change of a/b          (relative strength)
#   mom_diff   change from prior observation   (monthly series: UNRATE)
#   mom_pct    % change from prior observation (monthly counts: CHALLENGER)
#   level_k    level / 1000                    (CHALLENGER vs the 150k line)
#   yoy_pct    % change vs 12 observations ago (monthly index: CPIAUCSL -> CPI y/y)
#   spread     a - b, level                    (e.g. 3m bill - Fed target)
DRIVERS: dict[str, list[tuple]] = {
    "inflation": [
        ("DBC 30d %", "DBC", "pct"),
        ("DBA 30d %", "DBA", "pct"),
        ("USO 30d %", "USO", "pct"),
        ("Copper 30d %", "COPPER", "pct"),
        ("10y breakeven 30d chg", "T10YIE", "diff"),
    ],
    "growth": [
        ("Copper 30d %", "COPPER", "pct"),
        ("XLY/XLP 30d %", ("XLY", "XLP"), "ratio_pct"),
        ("SPY 30d %", "SPY", "pct"),
        ("KRE/SPY 30d %", ("KRE", "SPY"), "ratio_pct"),
        ("2s10s 30d chg", "T10Y2Y", "diff"),
    ],
    # Liquidity per the user's framework (2026-09-17): the Fed sets rates on
    # its dual mandate (prices, employment); the front end of the curve is
    # the market's vote on the next move -- the 3m bill "has to be followed
    # within that window", the 2y over a longer one. 10y is growth/credit,
    # not liquidity. BOJ/USDJPY carry noted as a candidate; foreign rates
    # not yet in the pipeline; Challenger job cuts has no free series.
    "liquidity": [
        # Spread vs the *effective* rate (DFF, daily, 1954->) rather than the
        # target ceiling (DFEDTARU, 2008-12->): identical hike-side rates
        # (0/0/24%), but the tightening state gets 46 windows instead of 20.
        ("3m bill - Fed target", ("US03MY", "DFF"), "spread"),
        ("2y - Fed target", ("US02Y", "DFF"), "spread"),
        ("3m bill 30d chg", "US03MY", "diff"),
        ("2y yield 30d chg", "US02Y", "diff"),
        ("Unemployment m/m chg", "UNRATE", "mom_diff"),
        ("Challenger cuts (k)", "CHALLENGER", "level_k"),
        ("CPI y/y %", "CPIAUCSL", "yoy_pct"),
    ],
    # Credit per the user's framework (2026-09-17): the curve as the bank
    # lending margin (10y-2y is the user's base line; 10y-3m the cleaner
    # academic form; 10y-5y for mortgages/autos), credit spread change,
    # HY vs IG bonds, bank relative strength (KBE), financial-conditions
    # change, C&I loan growth (banks tighten after a lending boom), and
    # the curve *regime* -- bull/bear steepener/flattener, a four-way label
    # scored as a categorical driver. SPY moved to TECHNICALS/breadth.
    "credit": [
        ("10y-2y (level)", "T10Y2Y", "level"),
        ("10y-3m (level)", ("US10Y", "US03MY"), "spread"),
        ("10y-5y (level)", ("US10Y", "US05Y"), "spread"),
        ("Curve regime 30d", ("US10Y", "US03MY"), "curve_regime"),
        ("Baa-10y 30d chg", "BAA10Y", "diff"),
        ("HYG/LQD 30d %", ("HYG", "LQD"), "ratio_pct"),
        ("KBE/SPY 30d %", ("KBE", "SPY"), "ratio_pct"),
        ("NFCI credit 13w chg", "NFCICREDIT", "diff@13"),
        ("C&I loans 13w %", "BUSLOANS", "pct@13"),
    ],
}

_ddb = boto3.client("dynamodb", region_name=REGION)


# ── data ─────────────────────────────────────────────────────────────────────

def _load_close(symbol: str) -> tuple[list[str], list[float]]:
    dates, closes = [], []
    kwargs = dict(
        TableName=PRICE_TABLE,
        KeyConditionExpression="#s = :s",
        ExpressionAttributeNames={"#s": "symbol", "#d": "date", "#c": "close"},
        ExpressionAttributeValues={":s": {"S": symbol}},
        ProjectionExpression="#d, #c",
    )
    rows = []
    while True:
        page = _ddb.query(**kwargs)
        for it in page["Items"]:
            if "close" in it and "N" in it["close"]:
                rows.append((it["date"]["S"], float(it["close"]["N"])))
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    rows.sort()
    for d, c in rows:
        dates.append(d)
        closes.append(c)
    return dates, closes


class _Series:
    def __init__(self, dates: list[str], values: list[float]):
        self.dates, self.values = dates, values

    def at(self, date: str) -> Optional[tuple[int, float]]:
        """Last row on or before date -> (index, value)."""
        i = bisect.bisect_right(self.dates, date) - 1
        return (i, self.values[i]) if i >= 0 else None

    def move(self, date: str, kind: str) -> Optional[float]:
        r = self.at(date)
        if r is None:
            return None
        i, v = r
        if kind == "level":
            return v
        if kind == "level_k":
            return v / 1000.0
        base_kind, _, n_rows = kind.partition("@")
        if base_kind == "yoy_pct":
            # Calendar-aware: the observation on/before the same date a year
            # earlier. Row-counting breaks on gaps (BLS skipped Oct-2025 CPI
            # in the shutdown; FRED has no row), which put CPI y/y at 3.73%
            # instead of 3.33%.
            d = dt.date.fromisoformat(self.dates[i])
            target = d.replace(year=d.year - 1).isoformat()
            j = bisect.bisect_right(self.dates, target) - 1
            if j < 0 or (d - dt.date.fromisoformat(self.dates[j])).days > 400:
                return None
        else:
            back = int(n_rows) if n_rows else {"mom_diff": 1, "mom_pct": 1}.get(base_kind, LOOKBACK_ROWS)
            j = i - back
            if j < 0:
                return None
        prev = self.values[j]
        if base_kind in ("diff", "mom_diff"):
            return v - prev
        if not prev:
            return None
        return (v / prev - 1.0) * 100.0


CURVE_LABELS = ("bull_steep", "bear_steep", "bull_flat", "bear_flat")


def _build_driver_series(spec: tuple, loaded: dict[str, _Series]) -> _Series:
    label, sym, kind = spec
    if kind == "curve_regime":
        # Over LOOKBACK_ROWS: spread up -> steepener; which end moved names it.
        #   bull steepener: short fell (Fed cutting / expected)
        #   bear steepener: long rose (term premium, inflation, supply)
        #   bull flattener: long fell (flight to quality, growth scare)
        #   bear flattener: short rose (Fed hiking)
        lg, sh = loaded[sym[0]], loaded[sym[1]]
        shd = {d: v for d, v in zip(sh.dates, sh.values)}
        dates, vals = [], []
        for i, (d, l) in enumerate(zip(lg.dates, lg.values)):
            if i < LOOKBACK_ROWS or d not in shd:
                continue
            d0 = lg.dates[i - LOOKBACK_ROWS]
            if d0 not in shd:
                continue
            dl, ds = l - lg.values[i - LOOKBACK_ROWS], shd[d] - shd[d0]
            if dl - ds >= 0:
                lab = "bull_steep" if ds < 0 else "bear_steep"
            else:
                lab = "bull_flat" if dl < 0 else "bear_flat"
            dates.append(d)
            vals.append(lab)
        return _Series(dates, vals)
    if kind == "spread":
        a, b = loaded[sym[0]], loaded[sym[1]]
        dates, vals = [], []
        for d, v in zip(a.dates, a.values):
            rb = b.at(d)  # b may be lower-frequency; use last on/before d
            if rb is not None and (dt.date.fromisoformat(d) - dt.date.fromisoformat(b.dates[rb[0]])).days <= 35:
                dates.append(d)
                vals.append(v - rb[1])
        return _Series(dates, vals)
    if kind.startswith("ratio_pct"):
        a, b = loaded[sym[0]], loaded[sym[1]]
        bd = {d: v for d, v in zip(b.dates, b.values)}
        dates, vals = [], []
        for d, v in zip(a.dates, a.values):
            if d in bd and bd[d]:
                dates.append(d)
                vals.append(v / bd[d])
        return _Series(dates, vals)
    return loaded[sym]


def _reading(spec: tuple, series: _Series, date: str) -> Optional[float]:
    kind = spec[2]
    if kind in ("spread", "curve_regime"):
        return series.move(date, "level")
    if kind.startswith("ratio_pct"):
        return series.move(date, "pct" + kind[len("ratio_pct"):])
    return series.move(date, kind)


# ── stats ────────────────────────────────────────────────────────────────────

def _tercile_bounds(vals: list[float]) -> tuple[float, float]:
    s = sorted(vals)
    n = len(s)
    return s[int(n / 3)], s[int(2 * n / 3)]


def _tercile(x: float, b: tuple[float, float]) -> int:
    return 0 if x < b[0] else (2 if x >= b[1] else 1)


def _axis_stats(axis: str, model: str, rows: list[tuple[str, int]], events: list[dict],
                drivers: list[tuple], series: dict[str, _Series], today: str) -> dict:
    slot = cal.SLOT_OF[axis]
    state_dates = [d for d, _ in rows]
    state_vals = [cal.Q_TO_AXES[q][slot] for _, q in rows]
    flip_dates = sorted(e["date"] for e in events if e["axis"] == axis)
    cadence = CADENCE_DAYS[axis]

    def state_at(date: str) -> Optional[int]:
        i = bisect.bisect_right(state_dates, date) - 1
        return state_vals[i] if i >= 0 else None

    # Windows run from the axis's first known state. A driver whose series
    # starts later simply has None readings in early windows and is scored
    # over the windows it covers -- one short series (e.g. CHALLENGER from
    # 2022) must not truncate the panel for every other driver.
    t = dt.date.fromisoformat(state_dates[0])
    end = dt.date.fromisoformat(today)

    windows = []  # (start, state, flipped, readings)
    while t + dt.timedelta(days=cadence) <= end:
        ts = t.isoformat()
        te = (t + dt.timedelta(days=cadence)).isoformat()
        st = state_at(ts)
        if st is not None:
            lo = bisect.bisect_right(flip_dates, ts)
            hi = bisect.bisect_right(flip_dates, te)
            flipped = hi > lo
            readings = {spec[0]: _reading(spec, series[spec[0]], ts) for spec in drivers}
            windows.append((ts, st, flipped, readings))
        t += dt.timedelta(days=cadence)

    out: dict = {"cadence_days": cadence, "n_windows": len(windows),
                 "window_range": [windows[0][0], windows[-1][0]] if windows else None, "from_state": {}}

    for s in (0, 1):
        ws = [w for w in windows if w[1] == s]
        n = len(ws)
        nf = sum(1 for w in ws if w[2])
        base = nf / n if n else None
        drv_out = []
        for spec in drivers:
            label = spec[0]
            pairs = [(w[3][label], w[2]) for w in ws if w[3][label] is not None]
            if pairs and isinstance(pairs[0][0], str):
                by: dict[str, list[int]] = {k: [0, 0] for k in CURVE_LABELS}
                for v, f in pairs:
                    by[v][0] += 1
                    by[v][1] += int(f)
                cur = _reading(spec, series[label], today)
                p_cur = (by[cur][1] / by[cur][0]) if cur in by and by[cur][0] >= MIN_TERCILE_N else None
                drv_out.append({
                    "name": label, "n": len(pairs), "categorical": True,
                    "buckets": {k: {"n": c[0], "p_flip": (round(c[1] / c[0], 3) if c[0] else None)} for k, c in by.items()},
                    "current_value": cur, "current_bucket": cur,
                    "p_current": round(p_cur, 3) if p_cur is not None else None,
                    "base_rate": round(sum(f for _, f in pairs) / len(pairs), 3),
                    "window_start": next(w[0] for w in ws if w[3][label] is not None),
                })
                continue
            if len(pairs) < 3 * MIN_TERCILE_N:
                drv_out.append({"name": label, "n": len(pairs), "insufficient": True,
                                "current_value": (lambda v: round(v, 3) if v is not None else None)(_reading(spec, series[label], today))})
                continue
            drv_base = sum(1 for _, f in pairs if f) / len(pairs)
            vals = [p[0] for p in pairs]
            b = _tercile_bounds(vals)
            by_t = {0: [0, 0], 1: [0, 0], 2: [0, 0]}
            for v, f in pairs:
                k = _tercile(v, b)
                by_t[k][0] += 1
                by_t[k][1] += int(f)
            p_by_t = [(by_t[k][1] / by_t[k][0]) if by_t[k][0] else None for k in (0, 1, 2)]
            mean_f = [v for v, f in pairs if f]
            mean_nf = [v for v, f in pairs if not f]
            cur = _reading(spec, series[label], today)
            cur_t = _tercile(cur, b) if cur is not None else None
            p_cur = p_by_t[cur_t] if cur_t is not None and by_t[cur_t][0] >= MIN_TERCILE_N else None
            drv_out.append({
                "name": label,
                "n": len(pairs),
                "mean_flip": round(sum(mean_f) / len(mean_f), 3) if mean_f else None,
                "mean_noflip": round(sum(mean_nf) / len(mean_nf), 3) if mean_nf else None,
                "terciles": [round(b[0], 3), round(b[1], 3)],
                "p_by_tercile": [round(p, 3) if p is not None else None for p in p_by_t],
                "n_by_tercile": [by_t[k][0] for k in (0, 1, 2)],
                "current_value": round(cur, 3) if cur is not None else None,
                "current_tercile": cur_t,
                "p_current": round(p_cur, 3) if p_cur is not None else None,
                "base_rate": round(drv_base, 3),
                "window_start": next(w[0] for w in ws if w[3][label] is not None),
            })
        used = [d["p_current"] for d in drv_out if d.get("p_current") is not None]
        out["from_state"][str(s)] = {
            "n_windows": n,
            "n_flips": nf,
            "base_rate": round(base, 3) if base is not None else None,
            "drivers": drv_out,
            "conditioned_p_flip": round(sum(used) / len(used), 3) if used else None,
            "n_drivers_used": len(used),
        }
    return out


# ── public ───────────────────────────────────────────────────────────────────

def compute_axis_drivers() -> dict:
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    hist = {m: md._load_model(f"{m}_US") for m in ("compass", "grid")}
    events: list[dict] = []
    current: dict[str, int] = {}
    for m, rows in hist.items():
        ev, _ = md._events_and_dwell(m, rows, today)
        events.extend(ev)
        current[m] = rows[-1][1] if rows else None

    symbols: set[str] = set()
    for specs in DRIVERS.values():
        for _, sym, _ in specs:
            symbols.update(sym if isinstance(sym, tuple) else (sym,))
    loaded = {}
    for sym in sorted(symbols):
        d, c = _load_close(sym)
        loaded[sym] = _Series(d, c)

    axes_out = {}
    for axis, specs in DRIVERS.items():
        model = cal.MODEL_OF[axis]
        series = {spec[0]: _build_driver_series(spec, loaded) for spec in specs}
        stats = _axis_stats(axis, model, hist[model], events, specs, series, today)
        cur_state = cal.Q_TO_AXES[current[model]][cal.SLOT_OF[axis]]
        stats["current_state"] = cur_state
        stats["current"] = stats["from_state"][str(cur_state)]
        stats["release_type"] = cal.AXIS_OF and {v: k for k, v in cal.AXIS_OF.items()}[axis]
        axes_out[axis] = stats

    return {"as_of": today, "lookback_rows": LOOKBACK_ROWS, "axes": axes_out}
