"""check_harness.py -- the study must find a planted effect and must NOT find one in noise.

synth() makes releases whose flip probability does (signal>0) or does not (signal=0) depend on the oriented gap g.
claim() is what run.py would call a finding: the 95% block-bootstrap CI of (Brier of the gap model - Brier of the base
rate) lies entirely below zero. Needs >= 6 of 8 planted found and <= 2 of 20 noise runs falsely claimed.
"""
import numpy as np
import consensus_study as C


def synth(n=45, signal=0.0, seed=0):
    rng = np.random.default_rng(seed)
    rows, state = [], 1
    for t in range(n):
        g = float(rng.normal(0, 1.2))
        p = 1 / (1 + np.exp(-(-0.4 + signal * g)))
        flip = int(rng.random() < p)
        rows.append({"date": f"2020-01-{t + 1:02d}" if t < 28 else f"2020-02-{t - 27:02d}", "state": state, "flip": flip,
                     "forecast": 0.0, "previous": 0.0, "actual": 0.0, "g": g})
        if flip:
            state = 1 - state
    return rows


def claims(rows, min_train=20):
    r = C.compare(rows, min_train)
    return r.get("verdict") == "BETTER"


if __name__ == "__main__":
    # hand check of the oriented gap and the flip definition
    assert C.oriented_gap(3.2, 2.2, 1) == -1.0 and C.oriented_gap(3.2, 2.2, 0) == 1.0, "gap orientation"
    ser = [("2020-01-01", 1), ("2020-04-30", 0), ("2020-07-30", 0)]
    assert C.flip_after(ser, "2020-04-29") == (1, 1), "flip inside settle window"
    assert C.flip_after(ser, "2020-04-20") == (1, 0), "no flip yet 10 days early"
    assert C.flip_after(ser, "2020-07-29") == (0, 0), "hold"

    # end to end through build_rows and state_before: grid rows (quadrant 2 = growth up, 3 = growth down)
    grid = [("2020-01-01", 2), ("2020-04-30", 3), ("2020-07-30", 3), ("2020-10-29", 2)]
    series = C.axis_series(grid, "growth")
    rels = [{"date": "2020-04-30T12:30:00.000Z", "forecast": 1.0, "previous": 2.0, "actual": 0.5},   # up -> consensus implies flip; flipped
            {"date": "2020-07-30T12:30:00.000Z", "forecast": 3.0, "previous": 0.5, "actual": 2.0},   # down -> consensus implies flip; no row until 10-29
            {"date": "2020-10-29T12:30:00.000Z", "forecast": 2.5, "previous": 2.0, "actual": 2.6}]   # down -> up on 10-29
    built = C.build_rows(rels, series)
    assert [b["state"] for b in built] == [1, 0, 0], built
    assert [b["flip"] for b in built] == [1, 0, 1], built
    assert [round(b["g"], 1) for b in built] == [1.0, 2.5, 0.5], built
    print("build_rows end-to-end ok")

    hit_strong = sum(claims(synth(n=60, signal=3.0, seed=s)) for s in range(8))
    hit_gdp_n = sum(claims(synth(n=45, signal=3.0, seed=50 + s)) for s in range(8))
    weak = sum(claims(synth(n=60, signal=1.0, seed=300 + s)) for s in range(8))
    fp = sum(claims(synth(n=60, signal=0.0, seed=100 + s)) for s in range(20))
    fp45 = sum(claims(synth(n=45, signal=0.0, seed=150 + s)) for s in range(20))
    print(f"(power note: a MODERATE effect, signal 1.0, n=60, is found only {weak}/8)")
    print(f"strong planted effect (signal 3.0), n=60: found {hit_strong}/8")
    print(f"strong planted effect (signal 3.0), n=45 (about the GDP advance count): found {hit_gdp_n}/8")
    print(f"noise: falsely claimed {fp}/20 at n=60, {fp45}/20 at n=45")
    ok = hit_strong >= 6 and fp <= 2 and fp45 <= 2
    print("SELFTEST", "OK" if ok else "FAILED")
    raise SystemExit(0 if ok else 1)
