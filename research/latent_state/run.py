"""run.py -- walk-forward scores for every axis, lagged vs leaky readings."""
import json, pathlib, sys
import numpy as np
import score

HERE = pathlib.Path(__file__).resolve().parent
data = json.loads((HERE / "data" / "windows.json").read_text())
MIN_TRAIN = {"credit": 40}          # only 89 windows; 60 would leave 29 to score

def fmt(r):
    return (f"  n_scored={r.n_scored:3d} flips={r.n_flips:3d} params={r.params:2d} | "
            f"Brier B0={r.brier['B0']:.4f} B1={r.brier['B1']:.4f} M1={r.brier['M1']:.4f} | "
            f"logloss B0={r.logloss['B0']:.4f} B1={r.logloss['B1']:.4f} M1={r.logloss['M1']:.4f}")

def line(name, b):
    lo, hi = b["ci95"]
    return f"    {name:18s} diff={b['mean_diff']:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  P(first better)={b['p_a_better']:.2f}"

results = {}
for axis, block in data["axes"].items():
    results[axis] = {}
    print(f"\n=== {axis}  windows={block['n_windows']} flips={block['n_flips']} "
          f"base={block['n_flips']/block['n_windows']:.2f} drivers={len(block['drivers'])} cadence={block['cadence_days']}d")
    for reading in ("r_pub", "r_leak"):
        r = score.score_axis(axis, block, reading, min_train=MIN_TRAIN.get(axis, score.MIN_TRAIN))
        results[axis][reading] = r.__dict__
        print(f" [{reading}]" + fmt(r))
        if reading == "r_pub":
            print(line("M1 vs B0 (Brier)", r.boot["M1_vs_B0_brier"]))
            print(line("M1 vs B0 (logloss)", r.boot["M1_vs_B0_logloss"]))
            print(line("B1 vs B0 (Brier)", r.boot["B1_vs_B0_brier"]))
            print(line("M1 vs B1 (Brier)", r.boot["M1_vs_B1_brier"]))
(HERE / "data" / "results.json").write_text(json.dumps(results, indent=1, default=float))
