"""run.py -- probability checks for every axis on the production (publication-lagged) readings."""
import json, pathlib
import calibrate as C
import score

HERE = pathlib.Path(__file__).resolve().parent
data = json.loads((HERE.parent / "latent_state" / "data" / "windows.json").read_text())
MIN_TRAIN = {"credit": 40}
results = {}
for axis, block in data["axes"].items():
    r = C.run_axis(block, "r_pub", MIN_TRAIN.get(axis, score.MIN_TRAIN))
    results[axis] = r
    print(f"\n=== {axis}: scored {r['n_scored']} windows, {r['n_flips']} flips")
    print("  Brier  " + "  ".join(f"{k}={v:.4f}" for k, v in r["brier"].items()))
    for k, b in r["vs_B0"].items():
        lo, hi = b["ci95"]
        verdict = "BETTER" if hi < 0 else ("worse" if lo > 0 else "no clear difference")
        print(f"  {k:6s} vs B0: {b['mean_diff']:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  -> {verdict}")
    for k, c in r["calibration"].items():
        bins = " | ".join(f"pred {x['mean_pred']:.2f} obs {x['observed']:.2f} (n={x['n']})" for x in c["bins"])
        print(f"  calibration {k}: slope {c['slope']:.2f} CI [{c['slope_ci95'][0]:.2f}, {c['slope_ci95'][1]:.2f}]  bins: {bins}")
(HERE / "results.json").write_text(json.dumps(results, indent=1, default=float))
