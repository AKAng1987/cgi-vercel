"""
backtest_fundamentals_fit.py -- does the Fundamentals "fit" chip say anything about what a theme does NEXT?

Local, read-only, zero tokens (network: SEC companyfacts once per name, prices from the price table).

  api/.venv/bin/python scripts/backtest_fundamentals_fit.py

Method
  * For each date T (about 50 days after each quarter end, from 2018, so most 10-Qs are in), rebuild every company's
    read from SEC facts FILED on or before T only -- point in time, no later restatements. The same code the page uses
    (fundamentals_data._company, _rollup, _fit) is run with the SEC fetch and "today" patched to T.
  * Fit label per theme at T: confirms / contradicts / mixed / thin.
  * Outcome: the theme's ETF legs, equal weighted, return minus SPY over the next 63 trading days.
  * Reported by label: n, mean and median excess return, share beating SPY. Then the per-quarter spread
    (confirms minus contradicts, themes averaged within the quarter first, because themes in one quarter share the same
    market) with a t-statistic across quarters.

Honest limits, printed with the result
  * Constituents are TODAY's top 5 per theme (survivorship: names that became leaders are more likely to be listed).
  * The theme running on RS is NOT conditioned on here; this tests the chip across all themes.
  * ~34 quarters at most; themes overlap; small samples. A hit is a prompt to test properly, not a finding.
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
import pathlib
import statistics
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
import axis_drivers as ad  # noqa: E402
import fundamentals_data as fd  # noqa: E402
import sec_xbrl as sx  # noqa: E402
import themes_data as td  # noqa: E402

FWD = 63
OUT = ROOT / "research" / "fundamentals_fit" / "results.json"
ASOF = {"d": None}


class _Date(_dt.date):
    @classmethod
    def today(cls):
        return ASOF["d"]


_shim = types.SimpleNamespace(**{k: getattr(_dt, k) for k in dir(_dt) if not k.startswith("__")})
_shim.date = _Date

RAW: dict[str, dict | None] = {}
_real_facts = sx.company_facts


def _raw(sym):
    if sym not in RAW:
        RAW[sym] = _real_facts(sym)
    return RAW[sym]


def _as_filed(f, asof_iso):
    g = copy.copy(f)
    g["facts"] = {}
    for ns, tags in f["facts"].items():
        g["facts"][ns] = {}
        for tag, node in tags.items():
            n = dict(node)
            n["units"] = {u: [r for r in rows if (r.get("filed") or "9999") <= asof_iso]
                          for u, rows in node.get("units", {}).items()}
            g["facts"][ns][tag] = n
    return g


def _patched(sym):
    raw = _raw(sym)
    return _as_filed(raw, ASOF["d"].isoformat()) if raw else None


def quarter_dates():
    out, y, q = [], 2018, 1
    today = _dt.date.today()
    while True:
        qend = _dt.date(y, q * 3, 30 if q in (2, 3) else 31)
        t = qend + _dt.timedelta(days=50)
        if t > today - _dt.timedelta(days=100):
            return out
        out.append(t)
        q += 1
        if q == 5:
            y, q = y + 1, 1


def closes(sym):
    d, c = ad._load_close(sym)
    return d, c


def fwd_excess(legs, spy, T):
    sd, sc = spy
    i = next((k for k, d in enumerate(sd) if d >= T.isoformat()), None)
    if i is None or i + FWD >= len(sd):
        return None
    rs = []
    for leg in legs:
        ld, lc = leg
        m = dict(zip(ld, lc))
        a, b = m.get(sd[i]), m.get(sd[i + FWD])
        if a and b:
            rs.append(b / a - 1 - (sc[i + FWD] / sc[i] - 1))
    return statistics.mean(rs) if rs else None


def main():
    constituents, _prov, _fb = fd.theme_constituents()
    names = sorted({s for v in constituents.values() for s in v})
    print(f"{len(names)} names, {len(constituents)} themes; fetching SEC facts once each ...", flush=True)
    for s in names:
        _raw(s)
    spy = closes("SPY")
    etf = {t: [closes(s) for s in td.THEMES[t] if s in td.THEMES[t]] for t in constituents if t in td.THEMES}
    sx.company_facts = _patched
    fd.dt = _shim
    if hasattr(sx, "dt"):
        sx.dt = _shim
    rows = []
    for T in quarter_dates():
        ASOF["d"] = T
        comp = {s: fd._company(s) for s in names}
        ok = {k: v for k, v in comp.items() if v.get("status") == "ok"}
        for theme, members in constituents.items():
            if theme not in etf:
                continue
            fit = fd._fit(fd._rollup(members, ok))
            ex = fwd_excess(etf[theme], spy, T)
            if ex is not None:
                rows.append({"asof": T.isoformat(), "theme": theme, "fit": fit["label"], "excess": ex})
        print(T, len(ok), "names read", flush=True)

    def stats(sel):
        v = [r["excess"] for r in sel]
        return {"n": len(v), "mean_pct": round(100 * statistics.mean(v), 2) if v else None,
                "median_pct": round(100 * statistics.median(v), 2) if v else None,
                "beat_spy_pct": round(100 * sum(1 for x in v if x > 0) / len(v), 1) if v else None}

    by = {lab: stats([r for r in rows if r["fit"] == lab]) for lab in ("confirms", "contradicts", "mixed", "thin")}
    spreads = []
    for T in sorted({r["asof"] for r in rows}):
        a = [r["excess"] for r in rows if r["asof"] == T and r["fit"] == "confirms"]
        b = [r["excess"] for r in rows if r["asof"] == T and r["fit"] == "contradicts"]
        if a and b:
            spreads.append(statistics.mean(a) - statistics.mean(b))
    sp = {"quarters": len(spreads)}
    if len(spreads) >= 4:
        m, sd = statistics.mean(spreads), statistics.stdev(spreads)
        sp.update({"mean_spread_pct": round(100 * m, 2), "t_stat": round(m / (sd / len(spreads) ** 0.5), 2),
                   "quarters_confirms_won": sum(1 for x in spreads if x > 0)})
    res = {"measured_on": _dt.date.today().isoformat(), "forward_trading_days": FWD, "by_label": by,
           "confirms_minus_contradicts_per_quarter": sp, "rows": rows,
           "limits": ["constituents are today's top 5 (survivorship)", "not conditioned on the theme running on RS",
                      "about 34 quarters at most, themes overlap"]}
    OUT.write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ("by_label", "confirms_minus_contradicts_per_quarter")}, indent=1))


if __name__ == "__main__":
    main()
