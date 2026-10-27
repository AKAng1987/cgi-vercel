"""check_cot_cadence.py -- COT must survive the CFTC moving to two reports a week (planned end of 2026).

    api/.venv/bin/python scripts/check_cot_cadence.py          # synthetic series, no network
    api/.venv/bin/python scripts/check_cot_cadence.py --live   # also: today's live CFTC output must equal the saved baseline
"""
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))
import cot_data as C  # noqa: E402


def mk(dates, spec=lambda i: 1000 + (i * 37) % 900 - 450, oi=10000):
    return [{"date": d, "oi": oi, "spec": float(spec(i)), "comm": 0.0, "small": 0.0, "spec_pct_oi": spec(i) / oi * 100}
            for i, d in enumerate(dates)]


def days(start, step, n):
    d = dt.date.fromisoformat(start)
    return [(d + dt.timedelta(days=step * k)).isoformat() for k in range(n)]


tuesdays = days("2023-01-03", 7, 200)                    # Tue 2023-01-03 -> weekly
assert dt.date.fromisoformat(tuesdays[0]).weekday() == 1

# (a) weekly Tuesday rows: calendar-day windows == the old row-count windows, for every lookback and every position
v = [r["spec"] for r in mk(tuesdays)]
for w in (156, 260, None):
    for i in (10, 80, 155, 199):
        assert C._index(v, i, w, tuesdays) == C._index(v, i, w), (w, i)

# (b) Mon + Wed as-of rows twice a week from "December": weekly series keeps one row a week, windows keep their span
mon = days("2026-11-30", 7, 1)                            # Monday
twice = tuesdays + sorted(days("2026-12-02", 7, 6) + days("2026-12-07", 7, 6))   # Wed 12-02.., Mon 12-07..
# put Mondays and Wednesdays in the same ISO weeks: Wed 12-02 (week 49), Mon 12-07 (week 50), Wed 12-09 (week 50)...
raw = mk(sorted(set(tuesdays + days("2026-11-30", 7, 6) + days("2026-12-02", 7, 6))))
wk = C._weekly(raw)
weeks = {dt.date.fromisoformat(r["date"]).isocalendar()[:2] for r in wk}
assert len(wk) == len(weeks), "one observation per ISO week"
assert [r["date"] for r in wk if r["date"] >= "2026-11-30"][:2] == ["2026-12-02", "2026-12-09"], "last as-of in the week wins"
# the 3y window over the weekly series still spans 156 weeks of calendar time, not 156 rows of mixed cadence
dts = [r["date"] for r in wk]
vals = [r["spec"] for r in wk]
assert C._index(vals, len(vals) - 1, 156, dts) == C._index(vals, len(vals) - 1, 156), "weekly series: days == rows"
# the BAD way (all raw rows, row counts) would cover far less calendar time
long_twice = mk(sorted(days("2025-01-06", 7, 100) + days("2025-01-08", 7, 100)))      # 100 weeks of Mon + Wed
span_rows = (dt.date.fromisoformat(long_twice[-1]["date"]) - dt.date.fromisoformat(long_twice[-156]["date"])).days
assert span_rows < 156 * 7 * 0.6, "demonstration: 156 raw twice-weekly rows cover only about 78 weeks"
lw = C._weekly(long_twice)
assert len(lw) == 100 and (dt.date.fromisoformat(lw[-1]["date"]) - dt.date.fromisoformat(lw[-100]["date"])).days >= 99 * 7 - 7, "weekly series keeps one row a week"

# (b2) a Monday-latest series: interim is flagged, finals stay on Wednesdays/Tuesdays
fin, inter = C._split(wk[:-1] + [{"date": "2026-12-14", "oi": 1.0, "spec": 5.0, "comm": 0.0, "small": 0.0, "spec_pct_oi": 0.1}])
assert inter is not None and inter["date"] == "2026-12-14" and fin[-1]["date"] == wk[-2]["date"], "Monday read after Tuesday/Wed finals is interim"
fin2, inter2 = C._split(wk)
assert inter2 is None, "a Wednesday-latest series has no interim"

# (c) Tuesday rows stop; Wednesday-as-of finals only (and Monday interim): nothing breaks, canon flips to Wednesday
wed = days("2026-04-01", 7, 40)                           # Wednesdays only, 40 weeks
assert dt.date.fromisoformat(wed[0]).weekday() == 2
wk3 = C._weekly(mk(tuesdays[:150] + wed))
assert C._canon_weekday(wk3) == 2, "after enough Wednesday weeks the final weekday is Wednesday"
f3, i3 = C._split(wk3 + [{"date": "2027-01-04", "oi": 1.0, "spec": 1.0, "comm": 0.0, "small": 0.0, "spec_pct_oi": 0.0}])
assert i3 and i3["date"] == "2027-01-04", "Monday after Wednesday finals is interim"

# (d) canary
cad = C._cadence(tuesdays[-20:])
assert cad["problem"] is None and not cad["twice_weekly"] and cad["pattern"].startswith("weekly")
cad = C._cadence(sorted(set(days("2026-10-05", 7, 12) + days("2026-10-07", 7, 12))))        # Mon + Wed
assert cad["problem"] is None and cad["twice_weekly"], cad
cad = C._cadence(days("2026-10-01", 7, 12))                                                  # Thursdays
assert cad["problem"] and "outside Mon-Wed" in cad["problem"], cad
cad = C._cadence(days("2026-09-01", 1, 60))                                                   # daily
assert cad["problem"], cad

# (e) publish dates
assert C.publish_date("2026-10-20") == dt.date(2026, 10, 23)      # Tue -> Fri
assert C.publish_date("2026-12-07") == dt.date(2026, 12, 9)       # Mon -> Wed
assert C.publish_date("2026-12-09") == dt.date(2026, 12, 11)      # Wed -> Fri

# (f) caveat is built from the data
assert "Tuesday 2026-10-20, published Friday 2026-10-23: 3 days" in C._caveat("2026-10-20", {"twice_weekly": False})
assert "twice a week" in C._caveat("2026-12-09", {"twice_weekly": True})

# (f) freshness: ok / stalled / cadence problem / source missing
import freshness as F  # noqa: E402
T = dt.date(2026, 10, 27)
ok = F.cot_problems("2026-10-20", {"as_of": "2026-10-20", "cadence": {"twice_weekly": False, "problem": None, "pattern": "weekly Tue"}}, T)
assert ok["n_problems"] == 0 and ok["published_est"] == "2026-10-23", ok
stalled = F.cot_problems("2026-10-06", {"as_of": "2026-10-06", "cadence": {"twice_weekly": False}}, T)       # published Fri 10-09, 18 days ago
assert stalled["n_problems"] == 1 and stalled["problems"][0]["check"] == "stalled"
twice_quiet = F.cot_problems("2026-12-09", {"as_of": "2026-12-09", "cadence": {"twice_weekly": True}}, dt.date(2026, 12, 19))   # pub Fri 12-11, 8 days
assert twice_quiet["n_problems"] == 1, "twice-weekly: 8 quiet days is a stall (limit 6)"
weekly_quiet = F.cot_problems("2026-12-09", {"as_of": "2026-12-09", "cadence": {"twice_weekly": False}}, dt.date(2026, 12, 19))
assert weekly_quiet["n_problems"] == 0, "weekly: 8 quiet days is still inside the 9-day limit"
cadence_bad = F.cot_problems("2026-10-20", {"as_of": "2026-10-20", "cadence": {"problem": "as-of weekday outside Mon-Wed seen (Thu)"}}, T)
assert cadence_bad["problems"][0]["check"] == "cadence"
assert F.cot_problems(None, None, T)["n_problems"] == 1
assert F.cot_problems("2026-10-20", {"as_of": "2026-10-13", "cadence": {}}, T)["n_problems"] == 0, "a cache that is behind the source rebuilds itself; reported, not a problem"

# (g) brief: positioning shown the 0-2 days after a release, every weekday
import brief_data as B  # noqa: E402
cot_fri = {"latest_published_est": "2026-10-23"}                   # Friday release
shown = [d for d in (dt.date(2026, 10, 19) + dt.timedelta(days=k) for k in range(14)) if B._cot_released_recently(cot_fri, d)]
assert shown == [dt.date(2026, 10, 23), dt.date(2026, 10, 24), dt.date(2026, 10, 25)], shown
cot_wed = {"latest_published_est": "2026-12-09"}                   # Wednesday release
assert [d.isoformat() for d in (dt.date(2026, 12, 7) + dt.timedelta(days=k) for k in range(7)) if B._cot_released_recently(cot_wed, d)] == ["2026-12-09", "2026-12-10", "2026-12-11"]
assert B._cot_released_recently({}, dt.date(2026, 10, 23)) is True and B._cot_released_recently({}, dt.date(2026, 10, 22)) is False, "old payload: old Friday rule"

print("OK: weekly series, calendar-day windows, interim, cadence canary and publish dates")

if "--live" in sys.argv:
    old = json.load(open("/tmp/cot_old.json"))
    new = C.build_cot_response()
    assert new["as_of"] == old["as_of"], (new["as_of"], old["as_of"])
    n = 0
    for go, gn in zip(old["groups"], new["groups"]):
        for co, cn in zip(go["contracts"], gn["contracts"]):
            for k in ("as_of", "spec", "comm", "small", "signal", "history_from", "spark",
                      "positions", "spec_pct_oi", "spec_change_4w", "open_interest"):
                assert co.get(k) == cn.get(k), (co["contract"], k, co.get(k), cn.get(k))
            # the index windows are calendar days now: a contract with a gap week (Aluminum) can differ by a rounding step
            for k in ("cot_index", "cot_index_pct_oi"):
                for w, a in co[k].items():
                    b = cn[k][w]
                    assert (a is None) == (b is None) and (a is None or abs(a - b) <= 0.5), (co["contract"], k, w, a, b)
            # n_weeks: a few early weeks (e.g. Natural Gas Dec 2001, Feb 2003) have two as-of rows; one per week is kept now
            assert 0 <= co["n_weeks"] - cn["n_weeks"] <= 6, (co["contract"], co["n_weeks"], cn["n_weeks"])
            n += 1
    assert old["extremes"] == new["extremes"], "extremes changed"
    print(f"OK live: {n} contracts match the saved baseline (signals, extremes, positions, spark identical; index within 0.5); cadence {new['cadence']['pattern']}, interim {bool(new['interim'])}")
