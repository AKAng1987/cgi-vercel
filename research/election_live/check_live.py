"""check_live.py -- tests for election_live/run.py. Prints ALL OK or the failures. Run with the market-dashboard venv:
~/market-dashboard/.venv/bin/python research/election_live/check_live.py   (no network, no real git, no real notifications)"""
import datetime as dt, json, pathlib, shutil, sys, tempfile
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import election_calendar as cal, run as R

FAILS = []
def check(name, ok, detail=""):
    print(("ok   " if ok else "FAIL ") + name + (f"  {detail}" if detail and not ok else ""))
    if not ok:
        FAILS.append(name)

UTC = dt.timezone.utc
def at(s):                                    # "2026-12-03 23:00" as UTC
    return dt.datetime.fromisoformat(s).replace(tzinfo=UTC)

def bdays(start, end):
    d, out = dt.date.fromisoformat(start), []
    while d <= dt.date.fromisoformat(end):
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += dt.timedelta(days=1)
    return out

def mkbars(start, end, base_date, base=100.0, step=0.1):
    """Synthetic closes: a rising line, so every return is a known number."""
    ds = bdays(start, end)
    return [(d, base + step * (k - ds.index(base_date))) if base_date in ds else (d, 100 + k * step) for k, d in enumerate(ds)]

MD_MID = ("# t\n\n## Live case 2026 (not counted)\n- x\n\n| Horizon | Date | SPX | Return |\n|---|---|---|---|\n| Day after | | | |\n| +1 month | 2026-12-02 | | |\n"
          "| +3 months | 2027-02-02 | | |\n| +6 months | 2027-05-03 | | |\n| +12 months | 2027-11-02 | | |\n\n## Gaps, deviations\n- g\n")
MD_PRES = "# p\n\n## Honest reading\nh\n\n## Audit\na\n"
HIST = {"events": [{"react": 0.01, "r21": 0.02, "r63": 0.05, "r126": 0.1, "r252": 0.15, "scenario": "Keeps both (red-wave analog)"}],
        "scenarios": {"Keeps both (red-wave analog)": {"n": 1}}}

def tree(res=None):
    tmp = pathlib.Path(tempfile.mkdtemp())
    for d, md in (("election_cycle", MD_MID), ("presidential_cycle", MD_PRES)):
        (tmp / "research" / d / "data").mkdir(parents=True)
        (tmp / "research" / d / "RESULTS.md").write_text(md)
        (tmp / "research" / d / "results.json").write_text(json.dumps(HIST))
    (tmp / "web/app/components/context").mkdir(parents=True)
    (tmp / "research/election_cycle/data/live_result.json").write_text(json.dumps(res or {"election": "2026-11-03", "status": "pending"}))
    (tmp / "research/presidential_cycle/data/live_result.json").write_text(json.dumps({"election": "2028-11-07", "status": "pending"}))
    return tmp

class Rec:
    def __init__(self):
        self.notes, self.commits = [], []
    def notify(self, t, x): self.notes.append(x)
    def commit(self, paths, msg): self.commits.append((paths, msg))

def go(tmp, rows, now, rec, dry=False, ts=None):
    cfg = R.make_cfg(tmp / "research", state=tmp / "state.json", log=tmp / "log", now=at(now), dry=dry, log_to_file=False,
                     notify=rec.notify, commit=rec.commit, last_commit_ts=lambda p: ts, fetch=lambda c: rows)
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        return R.run(cfg)

# 1. election dates 2026-2040 -----------------------------------------------------------------------------------------------
exp = {2026: "2026-11-03", 2028: "2028-11-07", 2030: "2030-11-05", 2032: "2032-11-02", 2034: "2034-11-07", 2036: "2036-11-04", 2038: "2038-11-02", 2040: "2040-11-06"}
check("election dates 2026-2040", all(cal.election_day(y).isoformat() == v for y, v in exp.items()))
check("kinds: 2026 midterm, 2028 presidential, 2030 midterm, 2032 presidential",
      [cal.kind(y) for y in (2026, 2028, 2030, 2032)] == ["midterm", "presidential", "midterm", "presidential"])
check("2028-11-07 is not the 3rd and is a Tuesday", cal.election_day(2028).day == 7 and cal.election_day(2028).weekday() == 1)
check("every election 2026-2040 is a Tuesday in Nov 2-8", all(d.weekday() == 1 and 2 <= d.day <= 8 for d, _ in cal.elections(2026, 2040)))
check("add_months clamps and rolls the year", cal.add_months(dt.date(2026, 11, 2), 3) == dt.date(2027, 2, 2) and cal.add_months(dt.date(2026, 8, 31), 6) == dt.date(2027, 2, 28))

# 2. milestone not yet final -> no fill ---------------------------------------------------------------------------------------
bars = mkbars("2026-10-01", "2026-11-04", "2026-11-02")
tmp, rec = tree(), Rec()
r = go(tmp, bars, "2026-11-05 00:00", rec)            # 2026-11-04 19:00 ET: the Nov 4 bar is final
md = (tmp / "research/election_cycle/RESULTS.md").read_text()
check("day after fills when the bar after Election Day is final", r["filled"]["midterm"] == ["Day after"] and "| Day after | 2026-11-04 |" in md)
check("+1 month etc. stay empty (no bar yet)", "| +1 month | 2026-12-02 | | |" in md and "| +12 months | 2027-11-02 | | |" in md)
check("one local commit and one notification, never a push", len(rec.commits) == 1 and len(rec.notes) == 1 and "not pushed" in rec.notes[0])

# 3/4. final -> fills once; second run changes nothing -------------------------------------------------------------------------
before = (tmp / "research/election_cycle/RESULTS.md").read_text()
rec2 = Rec()
r = go(tmp, bars, "2026-11-05 01:00", rec2, ts=at("2026-11-05 00:00").timestamp())
check("second run: nothing filled, file identical, no commit, no notification", r["filled"]["midterm"] == [] and (tmp / "research/election_cycle/RESULTS.md").read_text() == before and not rec2.commits and not rec2.notes)
bars2 = mkbars("2026-10-01", "2026-12-03", "2026-11-02")
rec3 = Rec(); r = go(tmp, bars2, "2026-12-04 00:00", rec3)
md = (tmp / "research/election_cycle/RESULTS.md").read_text()
check("+1 month fills from the 2 Dec bar, day after row untouched", r["filled"]["midterm"] == ["+1 month"] and "| +1 month | 2026-12-02 |" in md and "| Day after | 2026-11-04 |" in md)
tmp2 = tree()
(tmp2 / "research/election_cycle/RESULTS.md").write_text(MD_MID.replace("| Day after | | | |", "| Day after | 2026-11-04 | 1.00 | +9.9% |"))
go(tmp2, bars2, "2026-12-04 00:00", Rec())
check("a hand-filled row is never overwritten", "| Day after | 2026-11-04 | 1.00 | +9.9% |" in (tmp2 / "research/election_cycle/RESULTS.md").read_text())

# 5. intraday bar excluded ---------------------------------------------------------------------------------------------------------
tmp, rec = tree(), Rec()
r = go(tmp, bars, "2026-11-04 18:00", rec)             # 13:00 ET on Nov 4: the Nov 4 bar is still forming
check("intraday bar (today, before 16:30 ET) is dropped: nothing fills", r["filled"]["midterm"] == [] and not rec.notes and "Day after | |" in (tmp / "research/election_cycle/RESULTS.md").read_text())
j = json.loads((tmp / "web/app/components/context/election_live.json").read_text())
check("intraday bar is not in the snapshot either", j["as_of"] == "2026-11-03" and j["windows"][0]["ret"] is None, str(j["as_of"]))
check("final_bars keeps today's bar after 16:30 ET", [d for d, _ in R.final_bars(bars, at("2026-11-04 22:00"))][-1] == "2026-11-04")
check("final_bars drops future-dated bars", all(d <= "2026-11-03" for d, _ in R.final_bars(bars, at("2026-11-04 03:00"))))

# 6. pending result -> one notification only ------------------------------------------------------------------------------------------
tmp, rec = tree(), Rec()
for now in ("2026-11-16 00:00", "2026-11-17 00:00", "2026-11-18 00:00"):
    go(tmp, mkbars("2026-10-01", "2026-11-17", "2026-11-02"), now, rec)
pend = [n for n in rec.notes if "not entered" in n]
check("pending House/Senate result: exactly one notification across three days", len(pend) == 1, str(rec.notes))
tmp, rec = tree(), Rec(); go(tmp, mkbars("2026-10-01", "2026-11-12", "2026-11-02"), "2026-11-13 00:00", rec)
check("no pending-result notification before 14 days", not [n for n in rec.notes if "not entered" in n])
tmp, rec = tree({"election": "2026-11-03", "status": "called", "house_after": "D", "senate_after": "R", "source": "AP", "as_of": "2026-11-05"}), Rec()
go(tmp, mkbars("2026-10-01", "2026-11-17", "2026-11-02"), "2026-11-18 00:00", rec)
j = json.loads((tmp / "web/app/components/context/election_live.json").read_text())
check("a called result silences the notification and sets the scenario", not [n for n in rec.notes if "not entered" in n] and j["scenario"] == "Loses House only (Dem House / GOP Senate analog)")

# 7. midterm and presidential use the right baseline -----------------------------------------------------------------------------------
allbars = mkbars("2026-09-01", "2028-12-20", "2026-11-02")
tmp, rec = tree(), Rec()
go(tmp, allbars, "2028-11-09 00:00", rec)              # 2028-11-08 19:00 ET: midterm is 24 months old, presidential day after final
jp = json.loads((tmp / "web/app/components/context/presidential_live.json").read_text())
check("presidential baseline = last close before 2028-11-07 (2028-11-06)", jp["baseline_date"] == "2028-11-06" and jp["kind"] == "presidential", jp.get("baseline_date"))
check("presidential day-after row filled in its own RESULTS.md", "| Day after | 2028-11-08 |" in (tmp / "research/presidential_cycle/RESULTS.md").read_text())
check("midterm 2026 no longer active at 24 months: its table untouched", (tmp / "research/election_cycle/RESULTS.md").read_text() == MD_MID)
tmp, rec = tree(), Rec(); go(tmp, allbars, "2026-12-04 00:00", rec)
jm = json.loads((tmp / "web/app/components/context/election_live.json").read_text())
check("midterm baseline = 2026-11-02, 21-bar window uses it", jm["baseline_date"] == "2026-11-02" and jm["windows"][1]["ret"] is not None and abs(jm["windows"][1]["ret"] - (allbars[[d for d, _ in allbars].index("2026-11-02") + 21][1] / jm["baseline_close"] - 1)) < 1e-12)
check("presidential not active in 2026: dormant placeholder only", json.loads((tmp / "web/app/components/context/presidential_live.json").read_text())["status"] == "dormant")

# 8. a new cycle gets its own table; the old one is left alone -------------------------------------------------------------------------
tmp, rec = tree(), Rec()
(tmp / "research/election_cycle/RESULTS.md").write_text(MD_MID.replace("| Day after | | | |", "| Day after | 2026-11-04 | 7,600.00 | +0.8% |"))
(tmp / "research/election_cycle/data/live_result.json").write_text(json.dumps({"election": "2026-11-03", "status": "called", "house_after": "D", "senate_after": "R"}))
go(tmp, mkbars("2030-09-01", "2030-11-12", "2030-11-04"), "2030-11-13 00:00", rec)
md = (tmp / "research/election_cycle/RESULTS.md").read_text()
check("2030 midterm: new 'Live case 2030' section, 2026 row untouched, section placed before Gaps",
      "## Live case 2030" in md and "| Day after | 2026-11-04 | 7,600.00 | +0.8% |" in md and md.index("## Live case 2030") < md.index("## Gaps") and "| Day after | 2030-11-06 |" in md)
check("2026 result file does not leak into 2030: result pending", json.loads((tmp / "web/app/components/context/election_live.json").read_text())["result"]["status"] == "pending")

# 9. Sunday target rolls to the next bar ------------------------------------------------------------------------------------------------
b, ms = R.milestones(mkbars("2026-10-01", "2027-05-05", "2026-11-02"), cal.election_day(2026))
check("+6 months target 2027-05-02 (Sunday) fills from Monday 2027-05-03", [m for m in ms if m["label"] == "+6 months"][0]["date"] == "2027-05-03")
b, ms = R.milestones(mkbars("2026-10-01", "2027-04-30", "2026-11-02"), cal.election_day(2026))
check("+6 months stays empty until the Monday bar exists", [m for m in ms if m["label"] == "+6 months"][0]["date"] is None)

# 10. fetch failure -> notify, change nothing; dry run changes nothing -------------------------------------------------------------------
tmp, rec = tree(), Rec()
cfg = R.make_cfg(tmp / "research", state=tmp / "s.json", log=tmp / "l", now=at("2026-11-05 00:00"), log_to_file=False, notify=rec.notify, commit=rec.commit,
                 last_commit_ts=lambda p: None, fetch=lambda c: (_ for _ in ()).throw(OSError("DNS failed")))
import io, contextlib
with contextlib.redirect_stdout(io.StringIO()):
    r = R.run(cfg)
check("fetch error: one notification, no commit, RESULTS.md unchanged", r.get("fetch_failed") and len(rec.notes) == 1 and not rec.commits and (tmp / "research/election_cycle/RESULTS.md").read_text() == MD_MID)
tmp, rec = tree(), Rec(); go(tmp, bars, "2026-11-05 00:00", rec, dry=True)
check("dry run: reports the fill but writes, commits and notifies nothing", (tmp / "research/election_cycle/RESULTS.md").read_text() == MD_MID and not rec.commits and not rec.notes and not (tmp / "web/app/components/context/election_live.json").exists())

# 11. equivalence with the committed election_live.json on the real data (skipped if files are absent) ------------------------------------------------------
real = HERE.parent / "election_cycle/data/spx_yahoo.json"
live = HERE.parent.parent / "web/app/components/context/election_live.json"
if real.exists() and live.exists() and json.loads(live.read_text()).get("as_of") == "2026-11-03":
    rows = [tuple(x) for x in json.loads(real.read_text()) if x[0] <= "2026-11-03"]
    b, _ = R.milestones(rows, cal.election_day(2026))
    old = json.loads(live.read_text())
    new = R.build_json("midterm", cal.election_day(2026), rows, b, json.loads((HERE.parent / "election_cycle/results.json").read_text()),
                       R.result_for(HERE.parent / "election_cycle/data/live_result.json", cal.election_day(2026)))
    same = all(new[k] == old[k] for k in ("as_of", "baseline_date", "baseline_close", "last_close", "since", "bars_since", "windows", "scenario", "scenario_n")) and new["result"] == old["result"]
    check("build_json reproduces refresh_live.py's election_live.json (2026-11-03 snapshot)", same)

print("\nALL OK" if not FAILS else f"\nFAILED: {FAILS}")
sys.exit(1 if FAILS else 0)
