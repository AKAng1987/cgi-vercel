"""run.py -- the ERP study on real history. Run check_harness.py first (must print SELFTEST OK), then fetch_data.py."""
import json, pathlib
import numpy as np
import erp_study as S

inp = S.load()
rows = S.build(inp)
HERE = pathlib.Path(__file__).resolve().parent
res = {"n_decision_months": len(rows), "first": rows[0]["month"], "last": rows[-1]["month"]}
print(f"decision months {len(rows)}: {rows[0]['month']} -> {rows[-1]['month']} (ERP row dated the month BEFORE the decision month)")

print("\n== A. Does ERP improve a walk-forward forecast beyond regime + 20d vol? (paired out-of-sample squared error)")
print("   PRIMARY (stated before running): erp_level -> maxdd3m. SECONDARY: erp_level -> ret3m. The other 10 are exploratory.")
res["compare"] = {}
for fk in S.FEATURES:
    for tk, (t, h) in S.TARGETS.items():
        r = S.compare(rows, fk, t, h)
        res["compare"][f"{fk}|{tk}"] = r
        if r.get("too_few"):
            print(f"   {fk:10} -> {tk:8} too few scored months ({r['n']})"); continue
        tag = "HELPS" if r["helps"] else "no clear gain"
        print(f"   {fk:10} -> {tk:8} n={r['n']:3}  rel. MSE gain {r['rel_gain_pct']:+5.1f}%  mean diff {r['mean_diff']:+8.3f}  95% CI [{r['ci95'][0]:+8.3f}, {r['ci95'][1]:+8.3f}]  {tag}")

print("\n== B. What happened after each ERP-level tercile (walk-forward terciles; means of forward outcomes)")
tt = S.tercile_table(rows)
res["terciles"] = tt
name = {0: "low ERP (thin cushion)", 1: "middle", 2: "high ERP (thick cushion)"}
for k in (0, 1, 2):
    v = tt[k]
    f = lambda x: "n/a" if x is None else f"{x:6.2f}"
    print(f"   {name[k]:26} n={v['n']:3}  fwd1m {f(v['r1'])}%  fwd3m {f(v['r3'])}%  worst-3m-drawdown {f(v['dd'])}%  3m vol {f(v['v3'])}%")
res["low_minus_high"] = {}
for t in ("r1", "r3", "dd", "v3"):
    r = S.low_vs_high(rows, t)
    res["low_minus_high"][t] = r
    if not r.get("too_few"):
        print(f"   low minus high, {t:3}: {r['diff_low_minus_high']:+6.2f}  95% CI [{r['ci95'][0]:+6.2f}, {r['ci95'][1]:+6.2f}]  (n low {r['n_low']}, high {r['n_high']})")

print("\n== C. Inside each Compass quadrant: worst-3m-drawdown, low minus high ERP tercile (thin = fewer than 6 in a bucket)")
res["by_compass"] = {}
for q in (1, 2, 3, 4):
    sub = [r for r in rows if r["comp"] == q]
    lo = [r["dd"] for r in sub if r["b_level"] == 0 and r["dd"] is not None]
    hi = [r["dd"] for r in sub if r["b_level"] == 2 and r["dd"] is not None]
    row = {"n_low": len(lo), "n_high": len(hi)}
    if len(lo) >= 6 and len(hi) >= 6:
        row["diff"] = float(np.mean(lo) - np.mean(hi))
        print(f"   C{q}: n low {len(lo):3}, high {len(hi):3}: low minus high = {row['diff']:+5.2f} pts")
    else:
        print(f"   C{q}: n low {len(lo):3}, high {len(hi):3}: thin, not reported")
    res["by_compass"][q] = row

print("\n== D. Long-horizon supplement: year-end ERP vs the NEXT year (annual file, ~60 years; price return, no dividends)")
a = S.annual_supplement(inp)
res["annual"] = a
print(f"   n = {a['n_years']} years")
for k, v in a.items():
    if isinstance(v, dict):
        print(f"   {k:34} Spearman rho {v['rho']:+.2f}  95% CI [{v['ci95'][0]:+.2f}, {v['ci95'][1]:+.2f}]")

cur = rows[-1]
print(f"\n== E. Where today sits: latest ERP {cur['erp']:.2f}%, gap {cur['gap']:+.2f} pts; level bucket {cur['b_level']} (0 = thin), "
      f"change bucket {cur['b_chg']}, gap bucket {cur['b_gap']}")
res["now"] = {k: cur[k] for k in ("month", "erp", "gap", "b_level", "b_chg", "b_gap", "comp", "grid", "vol20")}
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
