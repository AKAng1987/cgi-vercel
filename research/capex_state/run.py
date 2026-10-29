"""run.py -- the capex_state study on real history. Run check_harness.py first (must print SELFTEST OK), then fetch_data.py and
build data/snapshot.json (capex_build.py --out).

PRE-REGISTERED (written 2026-10-30, before this file was run):
  PRIMARY    b_g1 (aggregate capex YoY growth, as known, expanding terciles) -> 3-month max drawdown of the S&P 500
  SECONDARY  b_gap (funding gap: trailing capex / trailing operating cash flow, as known) -> 3-month return
  EXPLORATORY (counted, not claimed): b_acc on all four targets; b_g1 and b_gap on the other targets; tercile tables.
  Deviations from erp_state, fixed in advance because the history is shorter: terciles after 24 months (36), first
  out-of-sample month after 24 resolved months (30). Decision months 2012-09 to 2026-08. Survivorship: today's S&P 500 members.
"""
import json, pathlib
import numpy as np
import capex_study as C
import erp_study as S

HERE = pathlib.Path(__file__).resolve().parent
snap = json.loads((HERE / "data" / "snapshot.json").read_text())
inp = json.loads((HERE / "data" / "inputs.json").read_text())
companies = [c for c in snap["companies"] if c.get("cq")]
rows = C.build(companies, inp)
res = {"snapshot_built": snap.get("built_at"), "n_companies_with_capex": len(companies), "n_decision_months": len(rows),
       "first": rows[0]["month"], "last": rows[-1]["month"]}
have = [r for r in rows if r["g1"] is not None]
print(f"companies with capex {len(companies)}; decision months {len(rows)} ({rows[0]['month']} -> {rows[-1]['month']}); "
      f"g1 available {len(have)} (first {have[0]['month'] if have else None}); median coverage "
      f"{np.median([r['cov'] for r in have]):.2f}")
import datetime as dt


def qend(q):
    return dt.date(int(q[:4]), int(q[5]) * 3, 30 if int(q[5]) in (2, 3) else 31)


ages = [(dt.date.fromisoformat(r["date"]) - qend(r["q"])).days for r in have]
lags = [(dt.date.fromisoformat(f) - qend(q)).days for c in companies for q, f in c.get("filed1", {}).items()]
olags = [(dt.date.fromisoformat(f) - qend(q)).days for c in companies for q, f in c.get("ofiled1", {}).items()]
print(f"first-filing lag (days after quarter end): capex median {np.median(lags):.0f}, operating cash flow median {np.median(olags):.0f}")
print(f"age of the reported quarter at the decision date: median {np.median(ages):.0f} days (p10 {np.percentile(ages, 10):.0f}, p90 {np.percentile(ages, 90):.0f})")
for k in ("g1", "acc", "gap"):
    v = [r[k] for r in rows if r[k] is not None]
    print(f"   {k:4} n={len(v):3}  min {min(v):7.2f}  median {np.median(v):7.2f}  max {max(v):7.2f}")

FEATS = {"b_g1": "capex growth (g1)", "b_acc": "capex acceleration (acc)", "b_gap": "funding gap (gap)"}
res["compare"] = {}
print("\n== A. Does the feature improve a walk-forward forecast beyond regime + 20d vol? (paired out-of-sample squared error)")
print("   PRIMARY (stated before running): b_g1 -> maxdd3m.  SECONDARY: b_gap -> ret3m.  The other 10 are exploratory.")
for fk in FEATS:
    for tk, (t, h) in S.TARGETS.items():
        r = S.compare(rows, fk, t, h)
        res["compare"][f"{fk}|{tk}"] = r
        if r.get("too_few"):
            print(f"   {fk:6} -> {tk:8} too few scored months ({r['n']})")
            continue
        tag = "HELPS" if r["helps"] else "no clear gain"
        print(f"   {fk:6} -> {tk:8} n={r['n']:3}  rel. MSE gain {r['rel_gain_pct']:+5.1f}%  mean diff {r['mean_diff']:+8.3f}  "
              f"95% CI [{r['ci95'][0]:+8.3f}, {r['ci95'][1]:+8.3f}]  {tag}")
n_cmp = sum(1 for v in res["compare"].values() if not v.get("too_few"))
helps = [k for k, v in res["compare"].items() if v.get("helps")]
res["counts"] = {"comparisons_run": n_cmp, "claimed": helps,
                 "note": f"{n_cmp} comparisons at 95%: expect about {round(n_cmp * 0.05, 1)} false claims by chance"}
print(f"\n   {res['counts']['note']}; crossed zero in the helpful direction: {helps or 'none'}")

print("\n== B. What happened after each tercile (walk-forward terciles; means of forward outcomes)")
res["terciles"] = {}
name = {0: "bottom", 1: "middle", 2: "top"}
for fk in FEATS:
    tt = S.tercile_table(rows, fk)
    res["terciles"][fk] = tt
    print(f"   {FEATS[fk]}")
    for k in (0, 1, 2):
        v = tt[k]
        f = lambda x: "n/a" if x is None else f"{x:6.2f}"
        print(f"     {name[k]:7} n={v['n']:3}  fwd1m {f(v['r1'])}%  fwd3m {f(v['r3'])}%  worst-3m-drawdown {f(v['dd'])}%  3m vol {f(v['v3'])}%")
res["bottom_minus_top"] = {}
for fk in FEATS:
    for t in ("r3", "dd"):
        r = S.low_vs_high(rows, t, fk)
        res["bottom_minus_top"][f"{fk}|{t}"] = r
        if not r.get("too_few"):
            print(f"   {fk} bottom minus top, {t}: {r['diff_low_minus_high']:+6.2f}  95% CI [{r['ci95'][0]:+6.2f}, {r['ci95'][1]:+6.2f}]  "
                  f"(n bottom {r['n_low']}, top {r['n_high']})")
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
