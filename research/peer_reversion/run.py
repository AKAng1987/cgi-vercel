"""run.py -- peer-overshoot reversion on CGI's universe (daily closes from price-history, read-only)."""
import json, pathlib, sys
import numpy as np, pandas as pd

API = pathlib.Path(__file__).resolve().parents[2] / "api"
sys.path.insert(0, str(API))
import axis_drivers as ad, backtest_data as bd, markov_data as md  # noqa: E402
import study  # noqa: E402

START = "2005-01-01"
universe, groups = bd.build_backtest_universe()
groups = {t: g for t, g in groups.items() if g != "CRYPTO"}

closes = {}
for t in groups:
    d, c = ad._load_close(t)
    if d:
        closes[t] = pd.Series(c, index=pd.to_datetime(d))
spx_d, _ = ad._load_close("SPX")
days = pd.to_datetime([x for x in spx_d if x >= START])
px = pd.DataFrame(closes).reindex(days)              # NO forward fill: a stale price would fake a reversion
rets = px.pct_change(fill_method=None)
zero_share = (rets == 0).sum() / rets.notna().sum()
thin = sorted(zero_share[zero_share > 0.05].index)
rets = rets.drop(columns=thin)
rets = rets.where(rets.abs() < 0.25)                 # drop impossible one-day moves (bad prints)
res = study.residuals(rets, groups)
print(f"instruments: {res.shape[1]} (dropped {len(thin)} thin: {thin[:8]}{'...' if len(thin) > 8 else ''}), days: {len(res)}")

out = {"full": {}, "early": {}, "late": {}}
print("\nfade P&L per event, % (positive = overshoot came back), net of 10bp; 95% CI over days")
for k in study.KS:
    for h in study.HS:
        daily = study.fade_table(res, k, h)
        gross = study.fade_table(res, k, h, cost=0.0)
        for name, sl in (("full", slice(None)), ("early", slice(None, "2015-12-31")), ("late", slice("2016-01-01", None))):
            out[name][f"k{k}_h{h}"] = {"net": study.block_boot(daily[sl], reps=1000),
                                       "gross": study.block_boot(gross[sl], reps=1000)}
        f = out["full"][f"k{k}_h{h}"]; e = out["early"][f"k{k}_h{h}"]["net"]; l = out["late"][f"k{k}_h{h}"]["net"]
        print(f"  k={k}d h={h:2d}d  gross {f['gross']['mean']*100:+.3f}  net {f['net']['mean']*100:+.3f} "
              f"[{f['net']['ci95'][0]*100:+.3f}, {f['net']['ci95'][1]*100:+.3f}]  days {f['net']['days']}"
              f" | 2005-15 {e['mean']*100:+.3f}  2016-26 {l['mean']*100:+.3f}")

# By regime, for the k=3/h=5 cell, with a Benjamini-Hochberg false-discovery check across regimes.
comp, grid = md._load_model("compass_US"), md._load_model("grid_US")
def asof(rows):
    s = pd.Series([q for _, q in rows], index=pd.to_datetime([d for d, _ in rows])).sort_index()
    return s.reindex(res.index, method="ffill")
regime = "C" + asof(comp).astype("Int64").astype(str) + "G" + asof(grid).astype("Int64").astype(str)
daily = study.fade_table(res, 3, 5)
rows = []
for r in sorted(regime.dropna().unique()):
    b = study.block_boot(daily[regime == r], reps=1000)
    if b["days"] >= 60:
        v = daily[regime == r].dropna()
        p = 2 * min((np.array([v.sample(frac=1, replace=True, random_state=i).mean() for i in range(400)]) <= 0).mean(),
                    (np.array([v.sample(frac=1, replace=True, random_state=i).mean() for i in range(400)]) >= 0).mean())
        rows.append((r, b, p))
m = len(rows); ranked = sorted(rows, key=lambda x: x[2])
passed = set()
for i, (r, b, p) in enumerate(ranked, 1):
    if p <= 0.10 * i / m:
        passed = {x[0] for x in ranked[:i]}
print("\nby regime (k=3, h=5, net %):")
for r, b, p in rows:
    print(f"  {r}: {b['mean']*100:+.3f} [{b['ci95'][0]*100:+.3f}, {b['ci95'][1]*100:+.3f}] days {b['days']}"
          f"{'  survives FDR' if r in passed else ''}")
out["by_regime_k3_h5"] = {r: {**b, "p": p, "fdr_pass": r in passed} for r, b, p in rows}
(pathlib.Path(__file__).resolve().parent / "results.json").write_text(json.dumps(out, indent=1, default=float))
