"""run.py -- the capex_flow study on real history. Run check_harness.py first (SELFTEST OK); data/snapshot.json comes from
~/market-dashboard/scripts/capex_build.py --out (SEC filings, first-reported values, first-filed dates).

PRE-REGISTERED (written 2026-10-30, before this file was run):
  PRIMARY    AI receivers pooled (energy + chips + infrastructure layers, 12 names): does the five hyperscalers' capex growth at q,
             added to an AR(1) of the receivers' own revenue growth, improve the out-of-sample forecast of the receivers' revenue
             growth at q+1? (paired squared error, block bootstrap, first forecast after 16 resolved quarters)
  SECONDARY  the same for Industrials, Utilities and Materials (whole sectors).
  EXPLORATORY (counted, not claimed): the three AI layers separately; capex lagged one and two quarters for the primary group;
             the descriptive lead-lag correlation table.
  ROBUSTNESS RULE (added 2026-10-30 after the cold audit of the first run, BEFORE the rerun): a 'helps' is reported as a finding only if it
             also holds with the capex term first-differenced, with an AR(2) baseline, with minimum training of 12 and of 20 quarters, and
             with the single best forecast quarter left out; otherwise it is reported as "not robust". The training filter is now by the
             FILING DATE of each training row's target (the first run filtered on quarter labels).
  NOT TESTED: market returns of the receivers (single-name prices are not stored; the index version, capex_state, was null).
Survivorship: today's S&P 500 members and today's layer lists applied to all history.
"""
import json, pathlib
import numpy as np
import flow_study as F

HERE = pathlib.Path(__file__).resolve().parent
snap = json.loads((HERE / "data" / "snapshot.json").read_text())
companies = [c for c in snap["companies"] if c.get("cq1") or c.get("rq1")]
gm = F.group_members(companies)
last = max(q for c in companies for q in c.get("rq1", {}))
pan = F.panel(companies, gm, last=F.q_shift(last, -0))
res = {"snapshot_built": snap.get("built_at"), "last_quarter_with_revenue": last,
       "members": {k: [c["t"] for c in v] for k, v in gm.items() if not k.startswith("AI:") or True}}
print(f"snapshot {snap.get('built_at')}; newest revenue quarter {last}")
for k, v in gm.items():
    print(f"   {k:16} {len(v):3} members" + (f"  ({', '.join(c['t'] for c in v)})" if len(v) <= 12 else ""))

print("\\n== A. Does spender capex growth improve a walk-forward forecast of next-quarter receiver revenue growth beyond an AR(1)?")
print("   PRIMARY (stated before running): AI receivers pooled.  SECONDARY: Industrials, Utilities, Materials.  The rest is exploratory.")
res["compare"] = {}
plan = [("AI receivers", 0, "PRIMARY"), ("Industrials", 0, "SECONDARY"), ("Utilities", 0, "SECONDARY"), ("Materials", 0, "SECONDARY"),
        ("AI: energy", 0, "exploratory"), ("AI: chips", 0, "exploratory"), ("AI: infrastructure", 0, "exploratory"),
        ("AI receivers", 1, "exploratory"), ("AI receivers", 2, "exploratory")]
for name, lag, tier in plan:
    r = F.compare(pan[name], lag=lag)
    key = f"{name}|lag{lag}"
    res["compare"][key] = {**r, "tier": tier}
    if r.get("too_few"):
        print(f"   {tier:11} {name:18} lag {lag}  too few scored quarters ({r['n']})")
        continue
    tag = "HELPS" if r["helps"] else "no clear gain"
    print(f"   {tier:11} {name:18} lag {lag}  n={r['n']:3} ({r['first']}..{r['last']})  rel. MSE gain {r['rel_gain_pct']:+6.1f}%  mean diff {r['mean_diff']:+8.2f}"
          f"  95% CI [{r['ci95'][0]:+8.2f}, {r['ci95'][1]:+8.2f}]  {tag}")
n_cmp = sum(1 for v in res["compare"].values() if not v.get("too_few"))
helps = [k for k, v in res["compare"].items() if v.get("helps")]
res["counts"] = {"comparisons_run": n_cmp, "claimed": helps,
                 "note": f"{n_cmp} comparisons at 95% (one-sided rule): expect about {round(n_cmp * 0.025, 1)} false claims by chance"}
print(f"\\n   {res['counts']['note']}; claimed: {helps or 'none'}")

print("\\n== A2. Robustness of every claimed 'helps' (rule above)")
res["robustness"] = {}
for key in helps:
    name, lag = key.split("|lag")
    lag = int(lag)
    base_r = res["compare"][key]
    tests = {"first-differenced capex": F.compare(pan[name], lag, variant="diff"), "AR(2) baseline": F.compare(pan[name], lag, variant="ar2"),
             "min train 12": F.compare(pan[name], lag, min_train=12), "min train 20": F.compare(pan[name], lag, min_train=20)}
    ex = F.examples(pan[name], lag)
    se_b, se_c, when = F.walkforward(ex)
    best = when[int(np.argmax(se_b - se_c))]
    tests[f"best quarter ({best}) left out"] = F.compare(pan[name], lag, drop_quarter=best)
    res["robustness"][key] = {k: v for k, v in tests.items()}
    survive = all(v.get("helps") for v in tests.values())
    res["robustness"][key]["_survives_all"] = survive
    print(f"   {key}: " + ("SURVIVES all variants" if survive else "NOT ROBUST"))
    for k, v in tests.items():
        if v.get("too_few"):
            print(f"      {k:34} too few")
        else:
            print(f"      {k:34} n={v['n']:3}  rel. MSE gain {v['rel_gain_pct']:+6.1f}%  95% CI [{v['ci95'][0]:+7.2f}, {v['ci95'][1]:+7.2f}]  {'helps' if v['helps'] else 'no clear gain'}")

print("\\n== B. Descriptive: correlation of spender capex growth at q-k with receiver revenue growth at q (whole sample, overlapping, not a test)")
res["lead_lag"] = {}
for name in ("AI receivers", "AI: chips", "AI: energy", "AI: infrastructure", "Industrials", "Utilities", "Materials"):
    ll = F.lead_lag(pan[name])
    res["lead_lag"][name] = ll
    print(f"   {name:18} " + "  ".join(f"k={k}: {v['corr']:+.2f} (n={v['n']})" if v["corr"] is not None else f"k={k}: n/a" for k, v in ll.items()))

print("\\n== C. What the receivers' growth and spender capex growth looked like (latest 6 quarters)")
res["latest"] = {}
for name in ("AI receivers", "Industrials", "Utilities", "Materials"):
    rows = [r for r in pan[name] if r["r"] is not None][-6:]
    res["latest"][name] = [{"q": r["q"], "revenue_growth": round(r["r"], 1), "spender_capex_growth": None if r["g"] is None else round(r["g"], 1)} for r in rows]
    print(f"   {name:14} " + "  ".join(f"{r['q']}: rev {r['r']:+.0f}% / capex {('n/a' if r['g'] is None else format(r['g'], '+.0f') + '%')}" for r in rows))
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
