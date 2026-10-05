"""selftest.py -- the harness must find a planted effect and must NOT find one in noise."""
import numpy as np
import calibrate as C

def synth(n=240, signal=0.0, dwell_effect=0.0, seed=0, K=4):
    rng = np.random.default_rng(seed)
    st = np.zeros(n, dtype=int)
    cur, run, flip = 0, 0, np.zeros(n)
    for t in range(n):
        st[t] = cur
        x = rng.normal(size=K)
        z = signal * x[0] + dwell_effect * (min(run, 12) - 6) / 6
        p = 1 / (1 + np.exp(-(-1.0 + z)))
        f = rng.random() < p
        flip[t] = f
        yield_row = x
        if t == 0: rows = []
        rows.append(x)
        if f: cur, run = 1 - cur, 0
        else: run += 1
    names = [f"d{k}" for k in range(K)]
    W = [{"state": int(st[t]), "flip": int(flip[t]), "start": str(t),
          "r_pub": {names[k]: float(rows[t][k]) for k in range(K)}} for t in range(n)]
    return {"windows": W, "drivers": names}

def claims(res, key):
    return res["vs_B0"][key]["ci95"][1] < 0

if __name__ == "__main__":
    hit_sig = sum(claims(C.run_axis(synth(signal=1.5, seed=s), min_train=60), "B1") for s in range(8))
    hit_dw = sum(claims(C.run_axis(synth(dwell_effect=5.0, seed=100 + s), min_train=60), "H1") for s in range(8))
    fp_b1 = fp_h1 = 0
    for s in range(20):
        r = C.run_axis(synth(seed=200 + s), min_train=60)
        fp_b1 += claims(r, "B1"); fp_h1 += claims(r, "H1")
    weak = sum(claims(C.run_axis(synth(dwell_effect=2.5, seed=300 + s), min_train=60), "H1") for s in range(8))
    print(f"(power note: a MODERATE time-in-state effect, Brier gain ~0.012, is found only {weak}/8 at this sample size)")
    print(f"planted driver signal found (B1 beats B0): {hit_sig}/8")
    print(f"planted time-in-state effect found (H1 beats B0): {hit_dw}/8")
    print(f"noise: B1 falsely claimed {fp_b1}/20, H1 falsely claimed {fp_h1}/20")
    ok = hit_sig >= 6 and hit_dw >= 6 and fp_b1 <= 2 and fp_h1 <= 2
    print("SELFTEST", "OK" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)
