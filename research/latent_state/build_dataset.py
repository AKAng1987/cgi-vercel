"""
build_dataset.py -- one row per release-cadence window per axis, with the driver
readings that were knowable at the window start. OFFLINE RESEARCH; ships nothing.

Reuses axis_drivers' own series builders and window definition so this study
and the production driver table cannot drift apart.

TWO READINGS PER DRIVER, ON PURPOSE
  r_pub   what was knowable at the window start: the query date is shifted back
          by a publication lag inferred from the series' own cadence
          (daily 1d, weekly 7d, monthly 45d, quarterly 120d). Conservative: it
          throws away information a trader would have had on release day.
  r_leak  the production convention: the value STAMPED on or before the date.
          A monthly series is stamped at its period start but published weeks
          later, so this uses data that did not yet exist -- the classic way to
          manufacture an edge. Kept only so the size of that leak can be MEASURED
          rather than argued about.

WHAT THIS CANNOT FIX (and the report must say so)
  * Revisions: price-history holds each series as last revised, not as first
    published. GDP, CPI components, claims and orders are revised; markets
    (yields, spreads, FX) are not.
  * Driver SELECTION: the lists in axis_drivers.DRIVERS were chosen because they
    separated flips on this same history. Walk-forward fitting cannot undo that.

  python3 research/latent_state/build_dataset.py
"""
from __future__ import annotations

import bisect
import datetime as dt
import json
import pathlib
import sys
import types

HERE = pathlib.Path(__file__).resolve().parent
API = HERE.parent.parent / "api"
sys.path.insert(0, str(API))
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))

import axis_drivers as ad          # noqa: E402
import markov_data as md           # noqa: E402
import release_calendar as cal     # noqa: E402

CACHE = HERE / "data" / "series"
CACHE.mkdir(parents=True, exist_ok=True)


def _run_query(sym, subprocess):
    return subprocess.run(
        ["aws", "dynamodb", "query", "--table-name", ad.PRICE_TABLE, "--region", "ap-southeast-1",
         "--key-condition-expression", "#s = :s",
         "--expression-attribute-names", '{"#s":"symbol","#d":"date","#c":"close"}',
         "--expression-attribute-values", json.dumps({":s": {"S": sym}}),
         "--projection-expression", "#d, #c", "--output", "json",
         "--cli-read-timeout", "90", "--cli-connect-timeout", "20"],
        capture_output=True, text=True, timeout=400)


def fetch_series(sym: str) -> tuple[list[str], list[float]]:
    """Close history for one symbol, cached on disk, fetched with the AWS CLI.

    boto3 under this repo's Python 3.9 stalled 30-120s per query (and once hung
    for 15 minutes at 0% CPU); the same query through the CLI returns in under a
    second and paginates itself. Research code, so the subprocess is fine.
    """
    f = CACHE / f"{sym}.json"
    if f.exists():
        d = json.loads(f.read_text())
        return d["dates"], d["values"]
    import subprocess, time as _t
    for attempt in range(1, 5):
        r = _run_query(sym, subprocess)
        if r.returncode == 0:
            break
        print(f"  retry {attempt} for {sym}: {r.stderr.strip()[:90]}", flush=True)
        _t.sleep(3 * attempt)
    else:
        raise RuntimeError(f"{sym}: {r.stderr.strip()[:300]}")
    items = json.loads(r.stdout)["Items"]
    rows = sorted((i["date"]["S"], float(i["close"]["N"])) for i in items if "N" in i.get("close", {}))
    f.write_text(json.dumps({"dates": [x[0] for x in rows], "values": [x[1] for x in rows]}))
    return [x[0] for x in rows], [x[1] for x in rows]


LAG_DAYS = {"daily": 1, "weekly": 7, "monthly": 45, "quarterly": 120}


def cadence_of(dates: list[str]) -> str:
    if len(dates) < 3:
        return "monthly"
    ds = [dt.date.fromisoformat(d) for d in dates[-60:]]
    gaps = sorted((b - a).days for a, b in zip(ds, ds[1:]))
    sp = gaps[len(gaps) // 2]
    return "daily" if sp <= 4 else "weekly" if sp <= 10 else "monthly" if sp <= 45 else "quarterly"


def spec_symbols(spec: tuple) -> list[str]:
    s = spec[1]
    return list(s) if isinstance(s, tuple) else [s]


def main() -> None:
    import time
    t0 = time.time()
    log = lambda m: print(f"[{time.time() - t0:6.1f}s] {m}", flush=True)
    today = dt.date.today().isoformat()
    from concurrent.futures import ThreadPoolExecutor
    all_syms = sorted({x for ax in ad.DRIVERS.values() for sp in ax if sp[2] != "curve_regime" for x in spec_symbols(sp)})
    log(f"prefetching {len(all_syms)} series (cached ones are instant)")
    def _pf(sym):
        d, v = fetch_series(sym)
        log(f"  {sym:22s} {len(d):6d} rows")
    with ThreadPoolExecutor(3) as ex:
        list(ex.map(_pf, all_syms))
    log("loading model-history")
    models = {m: md._load_model(f"{m}_US") for m in ("compass", "grid")}
    log(f"model-history loaded: " + ", ".join(f"{m}={len(r)} rows" for m, r in models.items()))
    events = []
    for m, rows in models.items():
        ev, _dw = md._events_and_dwell(m, rows, today)
        events.extend(ev)

    out = {"built": today, "axes": {}}
    for model, axes in md.AXES_OF_MODEL.items():
        rows = models[model]
        for axis in axes:
            specs = [s for s in ad.DRIVERS[axis] if s[2] != "curve_regime"]   # categorical: not numeric
            syms = sorted({x for s in specs for x in spec_symbols(s)})
            loaded = {}
            for sym in syms:
                d, v = fetch_series(sym)
                loaded[sym] = ad._Series(d, v)
            series = {s[0]: ad._build_driver_series(s, loaded) for s in specs}
            lag = {s[0]: max(LAG_DAYS[cadence_of(loaded[x].dates)] for x in spec_symbols(s)) for s in specs}

            slot = cal.SLOT_OF[axis]
            sdates = [d for d, _ in rows]
            svals = [cal.Q_TO_AXES[q][slot] for _, q in rows]
            flips = sorted(e["date"] for e in events if e["axis"] == axis)
            cad = ad.CADENCE_DAYS[axis]

            wins, t, end = [], dt.date.fromisoformat(sdates[0]), dt.date.fromisoformat(today)
            while t + dt.timedelta(days=cad) <= end:
                ts, te = t.isoformat(), (t + dt.timedelta(days=cad)).isoformat()
                i = bisect.bisect_right(sdates, ts) - 1
                if i >= 0:
                    lo, hi = bisect.bisect_right(flips, ts), bisect.bisect_right(flips, te)
                    r_pub, r_leak = {}, {}
                    for s in specs:
                        qd = (t - dt.timedelta(days=lag[s[0]])).isoformat()
                        r_pub[s[0]] = ad._reading(s, series[s[0]], qd)
                        r_leak[s[0]] = ad._reading(s, series[s[0]], ts)
                    wins.append({"start": ts, "state": svals[i], "flip": int(hi > lo),
                                 "r_pub": r_pub, "r_leak": r_leak})
                t += dt.timedelta(days=cad)
            out["axes"][axis] = {
                "model": model, "cadence_days": cad, "n_windows": len(wins),
                "n_flips": sum(w["flip"] for w in wins),
                "drivers": [s[0] for s in specs], "lag_days": lag,
                "kinds": {s[0]: s[2] for s in specs}, "windows": wins,
            }
            print(f"{axis:10s} windows={len(wins):4d} flips={sum(w['flip'] for w in wins):3d} "
                  f"drivers={len(specs):2d} {wins[0]['start']} -> {wins[-1]['start']}", flush=True)

    (HERE / "data" / "windows.json").write_text(json.dumps(out))
    print("wrote data/windows.json")


if __name__ == "__main__":
    main()
