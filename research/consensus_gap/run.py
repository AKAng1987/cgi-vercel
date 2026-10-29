"""run.py -- the consensus-gap study on the real release history. Run check_harness.py first (SELFTEST OK).

PRE-REGISTERED (written 2026-10-30, before this file was run):
  PRIMARY    growth axis, advance GDP, single predictor g = oriented (forecast - previous), Brier vs the base rate by
             state, expanding walk-forward, min train 20, block-bootstrap CI.
  SECONDARY  inflation axis with the headline CPI YoY (forecast - previous); inflation axis with core PCE YoY.
  EXPLORATORY (counted, not claimed): CPI MoM, core CPI YoY, the mechanical sign rule, GDP 2nd estimates, bins.
"""
import json, pathlib
import consensus_study as C

HERE = pathlib.Path(__file__).resolve().parent
rel = json.loads((HERE / "data" / "releases.json").read_text())
model = json.loads((HERE / "data" / "inputs.json").read_text())
grid = model["grid_US"]
res = {"data": {"gdp_rows": len(rel["gdp"]), "price_rows": len(rel["prices"]), "fetched": rel.get("fetched")}}


CUTOFF = "2026-10-01"     # later releases are still settling into the model history (it dedupes unchanged days)
# GDP advance selection, fixed before the run: est == adv, EXCLUDING the three 2013 rows titled "Adv" that are third
# estimates and the 2025-10-30 row (the print was delayed by the shutdown; the first real print is 2025-12-23, kept),
# INCLUDING the delayed 2019-02-28 first print of Q4 2018.
GDP_EXCLUDE = {"2013-03-28", "2013-06-26", "2013-09-26", "2025-10-30"}


def pick(rows, title, adv=False):
    out = [r for r in rows if r.get("title") == title]
    if adv:
        out = [r for r in out if r.get("est") == "adv" and r["date"][:10] not in GDP_EXCLUDE]
    return [r for r in out if r.get("forecast") is not None and r.get("previous") is not None
            and r["date"][:10] <= CUTOFF]


def report(name, rows, tier):
    c = C.compare(rows)
    flat = {"tier": tier, "n_releases": len(rows), "flips": sum(r["flip"] for r in rows),
            "first": rows[0]["date"] if rows else None, "last": rows[-1]["date"] if rows else None,
            "compare": c, "bins": C.bins(rows), "sign_rule": C.sign_rule(rows)}
    res[name] = flat
    print(f"\n=== {name} [{tier}]  releases {flat['n_releases']}  flips {flat['flips']}  {flat['first']} -> {flat['last']}")
    if "diff" in c:
        print(f"  scored {c['n_scored']} (flips {c['n_flips']}): Brier base {c['brier_base']:.4f}  gap-model {c['brier_gap']:.4f}"
              f"  diff {c['diff']:+.4f}  95% CI [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]  -> {c['verdict']}")
    else:
        print("  ", c)
    for k, b in flat["bins"].items():
        print(f"  {k}: n {b['n']}, flips {b['flips']}, rate {b['rate'] if b['rate'] is None else round(b['rate'], 2)}")
    s = flat["sign_rule"]
    if s:
        print(f"  sign rule: hit rate {s['hit_rate']:.2f} vs always-'no flip' {1 - s['flip_rate']:.2f}; "
              f"P(flip | rule says flip) {s['p_flip_given_pred']}; P(flip | rule says none) {s['p_flip_given_not_pred']}")


gdp = [r for r in rel["gdp"] if r.get("indicator") == "GDP Growth Rate"]
gdp = pick([dict(r, title="GDP") for r in gdp], "GDP", adv=True)
growth = C.axis_series(grid, "growth")
infl = C.axis_series(grid, "inflation")
report("PRIMARY growth ~ GDP advance gap", C.build_rows(gdp, growth), "primary")
report("SECONDARY inflation ~ CPI YoY gap", C.build_rows(pick(rel["prices"], "Inflation Rate YoY"), infl), "secondary")
report("SECONDARY inflation ~ core PCE YoY gap", C.build_rows(pick(rel["prices"], "Core PCE Price Index YoY"), infl), "secondary")
for ind in ("Inflation Rate MoM", "Core Inflation Rate YoY", "Core Inflation Rate MoM", "Core PCE Price Index MoM"):
    report(f"EXPLORATORY inflation ~ {ind}", C.build_rows(pick(rel["prices"], ind), infl), "exploratory")
second = [r for r in rel["gdp"] if r.get("est") == "2nd" and r.get("forecast") is not None and r.get("previous") is not None
          and r["date"][:10] <= CUTOFF]
report("EXPLORATORY growth ~ GDP 2nd-estimate gap", C.build_rows(second, growth), "exploratory")

n_exp = sum(1 for k in res if k.startswith("EXPLORATORY"))
res["counts"] = {"pre_registered": 3, "exploratory": n_exp,
                 "note": f"{3 + n_exp} comparisons in all; at 95% expect about {round((3 + n_exp) * 0.05, 1)} false claims by chance"}
print("\n" + res["counts"]["note"])
(HERE / "results.json").write_text(json.dumps(res, indent=1, default=float))
