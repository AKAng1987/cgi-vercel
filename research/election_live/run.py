"""run.py -- zero-token, calendar-driven refresh of the S&P 500 live case for every US election (midterm and presidential).
For each election that has passed and is under 13 months old: take final daily closes only (an intraday bar is dropped), the
baseline is the last close BEFORE Election Day, and each milestone (day after, +1/+3/+6/+12 calendar months from the baseline
date) is written into that study's RESULTS.md tracking table only when its date's final bar exists and the row is still empty
(idempotent, never overwrites). The live JSON snapshot for the web page is rewritten when a row fills or about weekly.
A change is committed LOCALLY (never pushed) and announced with a macOS notification. A House/Senate (or presidential) result
still pending 14 days after the vote sends one notification. Nothing here is counted in any study test.
Usage: python run.py [--dry-run] [--no-fetch]   (--no-fetch reads the study's saved spx_yahoo.json)       Log: ~/.cgi/election_live.log"""
import datetime as dt, json, pathlib, re, subprocess, sys
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import election_calendar as cal

ET = ZoneInfo("America/New_York")
ROWS = [("Day after", None), ("+1 month", 1), ("+3 months", 3), ("+6 months", 6), ("+12 months", 12)]
WINDOWS = [("day after", None, "react"), ("1 month", 21, "r21"), ("3 months", 63, "r63"), ("6 months", 126, "r126"), ("12 months", 252, "r252")]
FINAL_AFTER = dt.time(16, 30)        # a bar dated today (US time) is final only after the close plus a margin
MAX_AGE_MONTHS = 13
RESULT_GRACE_DAYS = 14
JSON_REFRESH_DAYS = 7


def make_cfg(root=None, **over):
    root = pathlib.Path(root) if root else HERE.parent
    web = root.parent / "web/app/components/context"
    cfg = {"root": root, "web": web, "state": pathlib.Path.home() / ".cgi/election_live_state.json",
           "log": pathlib.Path.home() / ".cgi/election_live.log", "dry": False, "now": None,
           "notify": notify, "commit": commit, "last_commit_ts": last_commit_ts, "fetch": fetch, "log_to_file": True}
    cfg.update(over)
    cfg["cycles"] = {
        "midterm": {"dir": root / "election_cycle", "json": web / "election_live.json", "label": "midterm"},
        "presidential": {"dir": root / "presidential_cycle", "json": web / "presidential_live.json", "label": "presidential"}}
    return cfg


# ---------------------------------------------------------------------------------------------------------------- side effects
def notify(title, text):
    esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(["osascript", "-e", f'display notification "{esc(text)}" with title "{esc(title)}"'], check=False)


def fetch(cfg):
    """Last ~3 years of S&P 500 daily closes from Yahoo ^GSPC, kept in memory: the tracked election_cycle/data/spx_yahoo.json (the
    study's frozen price file) is deliberately not rewritten, so the working tree stays clean."""
    import urllib.request
    p1 = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1100)).timestamp())
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC?period1={p1}&period2=1900000000&interval=1d&events=history"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())["chart"]["result"][0]
    rows = [(dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"), float(c)) for t, c in zip(r["timestamp"], r["indicators"]["quote"][0]["close"]) if c is not None]
    if len(rows) < 100:
        raise RuntimeError(f"Yahoo returned only {len(rows)} bars")
    return rows


def repo_of(path):
    return subprocess.run(["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()


def commit(paths, msg):
    """Commit only these paths, locally. Never pushes."""
    repo = repo_of(paths[0])
    subprocess.run(["git", "-C", repo, "add", "--"] + [str(p) for p in paths], check=True)
    subprocess.run(["git", "-C", repo, "commit", "-m", msg, "--"] + [str(p) for p in paths], check=True, capture_output=True)


def last_commit_ts(path):
    out = subprocess.run(["git", "-C", repo_of(path), "log", "-1", "--format=%ct", "--", str(path)], capture_output=True, text=True).stdout.strip()
    return int(out) if out else None


def log(cfg, msg):
    line = f"{cfg['now_utc'].strftime('%Y-%m-%d %H:%M:%S')}Z {msg}"
    print(line)
    if cfg["log_to_file"] and not cfg["dry"]:
        cfg["log"].parent.mkdir(parents=True, exist_ok=True)
        with cfg["log"].open("a") as f:
            f.write(line + "\n")


# ----------------------------------------------------------------------------------------------------------------------- logic
def final_bars(rows, now_utc):
    """Drop any bar that may still be forming: dated after today (US time), or today before 16:30 ET."""
    now_et = now_utc.astimezone(ET)
    today = now_et.date().isoformat()
    out = []
    for d, c in rows:
        if d > today or (d == today and now_et.time() < FINAL_AFTER):
            continue
        out.append((d, float(c)))
    return out


def milestones(bars, election):
    """Baseline = last final close strictly before Election Day. Returns (baseline_idx, [row dicts]); a row has date/close/ret
    only if its date's final bar exists (the first bar on or after the target date)."""
    ed = election.isoformat()
    dates = [d for d, _ in bars]
    b = max((k for k, d in enumerate(dates) if d < ed), default=None)
    if b is None:
        return None, []
    base = dt.date.fromisoformat(dates[b])
    out = []
    for label, months in ROWS:
        if months is None:
            j = next((k for k, d in enumerate(dates) if d > ed), None)
            target = None
        else:
            target = cal.add_months(base, months).isoformat()
            j = next((k for k, d in enumerate(dates) if d >= target), None)
        row = {"label": label, "target": target, "date": None, "close": None, "ret": None}
        if j is not None:
            row.update(date=dates[j], close=bars[j][1], ret=bars[j][1] / bars[b][1] - 1)
        out.append(row)
    return b, out


HEAD = "| Horizon | Date | SPX | Return |"
ROW_RE = re.compile(r"^\| (Day after|\+1 month|\+3 months|\+6 months|\+12 months) \| ([^|]*)\| ([^|]*)\| ([^|]*)\|[ \t]*$")


def new_section(year, election):
    rows = "\n".join(f"| {lab} | | | |" for lab, _ in ROWS)
    return (f"## Live case {year} (not counted)\n- Election {election.isoformat()}. Return from the last close before Election Day; rows are filled by "
            f"`research/election_live/run.py` when each date's final bar exists. Descriptive only.\n\n{HEAD}\n|---|---|---|---|\n{rows}\n\n")


def ensure_section(md, year, election):
    if re.search(rf"^## Live case {year}\b", md, re.M):
        return md
    sec = new_section(year, election)
    m = re.search(r"^## Gaps", md, re.M)
    return md[:m.start()] + sec + md[m.start():] if m else md.rstrip("\n") + "\n\n" + sec


def fill_table(md, election, rows):
    """Fill empty rows whose data exists. Returns (new_md, [labels filled]). A filled row is never touched again."""
    md = ensure_section(md, election.year, election)
    m = re.search(rf"^## Live case {election.year}\b.*?(?=^## |\Z)", md, re.M | re.S)
    sec, filled = m.group(0), []
    by = {r["label"]: r for r in rows}
    lines = sec.split("\n")
    for i, ln in enumerate(lines):
        mm = ROW_RE.match(ln)
        if not mm:
            continue
        label, r = mm.group(1), by[mm.group(1)]
        if mm.group(3).strip() or mm.group(4).strip() or r["close"] is None:
            continue
        lines[i] = f"| {label} | {r['date']} | {r['close']:,.2f} | {r['ret'] * 100:+.1f}% |"
        filled.append(label)
    return md[:m.start()] + "\n".join(lines) + md[m.end():], filled


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def build_json(k, election, bars, b, hist, res):
    """Same schema as election_cycle/refresh_live.py's election_live.json (midterm) so ElectionCycle.tsx keeps working."""
    dates = [d for d, _ in bars]
    c = [v for _, v in bars]
    scenario, president = None, res.get("president", "R")
    if k == "midterm" and res.get("status") == "called" and res.get("house_after") in ("D", "R") and res.get("senate_after") in ("D", "R"):
        lh, ls = res["house_after"] != president, res["senate_after"] != president
        scenario = ("Pres party loses both (blue-wave analog)" if lh and ls else "Loses House only (Dem House / GOP Senate analog)" if lh
                    else "Loses Senate only (the other split)" if ls else "Keeps both (red-wave analog)")

    def hist_mean(key, scen=None):
        return mean([e.get(key) for e in hist["events"] if scen is None or e.get("scenario") == scen])

    ed = election.isoformat()
    wins = []
    for label, bars_n, key in WINDOWS:
        j = next((x for x, d in enumerate(dates) if d > ed), None) if bars_n is None else (b + bars_n if b + bars_n < len(c) else None)
        ret, when = (c[j] / c[b] - 1, dates[j]) if j is not None else (None, None)
        wins.append({"label": label, "bars": bars_n, "ret": ret, "date": when, "hist_mean": hist_mean(key),
                     "hist_scenario_mean": hist_mean(key, scenario) if scenario else None})
    rkeys = ("status", "house_after", "senate_after", "house_seats_d", "house_seats_r", "source", "as_of") if k == "midterm" else ("status", "winner", "source", "as_of")
    out = {"kind": k, "election": ed, "as_of": dates[-1], "baseline_date": dates[b], "baseline_close": c[b], "last_close": c[-1],
           "since": c[-1] / c[b] - 1 if len(c) - 1 > b else None, "bars_since": len(c) - 1 - b, "windows": wins,
           "result": {x: res.get(x) for x in rkeys}, "scenario": scenario,
           "scenario_n": hist.get("scenarios", {}).get(scenario, {}).get("n") if scenario else None}
    return out


def result_for(path, election):
    """The hand-entered result, treated as pending when the file is missing or belongs to another election."""
    try:
        res = json.loads(path.read_text())
    except (OSError, ValueError):
        res = {}
    if res.get("election") != election.isoformat():
        return {"status": "pending", "president": res.get("president", "R")}
    return res


def load_state(cfg):
    try:
        return json.loads(cfg["state"].read_text())
    except (OSError, ValueError):
        return {"result_notified": []}


def save_state(cfg, st):
    cfg["state"].parent.mkdir(parents=True, exist_ok=True)
    cfg["state"].write_text(json.dumps(st, indent=1))


def dormant_stub(k, today):
    nxt = cal.next_upcoming(today, k)
    return {"kind": k, "status": "dormant", "next_election": nxt.isoformat(),
            "note": "No live case until Election Day; run.py fills this file after the vote. Descriptive addendum, not part of any pre-registered test."}


# ------------------------------------------------------------------------------------------------------------------------- main
def run(cfg):
    now_utc = cfg["now"] or dt.datetime.now(dt.timezone.utc)
    cfg["now_utc"] = now_utc
    today = now_utc.astimezone(ET).date()
    dry = cfg["dry"]
    active = {}
    for k in ("midterm", "presidential"):
        e = cal.latest_passed(today, k)
        if e is not None and today < cal.add_months(e, MAX_AGE_MONTHS):
            active[k] = e
    summary = {"filled": {}, "notified": [], "committed": False, "wrote": []}
    # dormant stubs: a cycle never run yet gets a placeholder JSON so the file exists; never overwrites a real live case
    stubs = []
    for k, c in cfg["cycles"].items():
        if k not in active and not c["json"].exists():
            stubs.append((k, c))
            if not dry:
                c["json"].write_text(json.dumps(dormant_stub(k, today), indent=1))
            log(cfg, f"{k}: dormant, next election {cal.next_upcoming(today, k)}; placeholder {'would be ' if dry else ''}written")
            summary["wrote"].append(str(c["json"]))
    stub_paths = [c["json"] for _, c in stubs] if not dry else []
    if not active:
        log(cfg, "no election under 13 months old; nothing to refresh")
        if stubs and not dry:
            commit_paths(cfg, [c["json"] for _, c in stubs], "election live case: dormant placeholder (presidential 2028)", summary)
        return summary
    try:
        rows = cfg["fetch"](cfg) if cfg["fetch"] else cfg["bars"]
    except Exception as ex:                                  # DNS failure, Yahoo 4xx/5xx, timeout
        log(cfg, f"FETCH FAILED: {ex!r}; will retry on the next run")
        if not dry:
            cfg["notify"]("Election live case", "price fetch failed; will retry tomorrow")
        summary["fetch_failed"] = True
        return summary
    bars = final_bars(rows, now_utc)
    st = load_state(cfg)
    for k, e in active.items():
        c = cfg["cycles"][k]
        b, ms = milestones(bars, e)
        if b is None:
            log(cfg, f"{k} {e}: no final bar before Election Day in the data; skipped")
            continue
        md_path = c["dir"] / "RESULTS.md"
        md = md_path.read_text()
        new_md, filled = fill_table(md, e, ms)
        res = result_for(c["dir"] / "data/live_result.json", e)
        hist = json.loads((c["dir"] / "results.json").read_text())
        js = build_json(k, e, bars, b, hist, res)
        # result pending 14 days after the vote: one notification, ever
        key = f"{k}:{e.isoformat()}"
        if res.get("status") != "called" and today >= e + dt.timedelta(days=RESULT_GRACE_DAYS) and key not in st["result_notified"]:
            what = "House/Senate result not entered" if k == "midterm" else "presidential result not entered"
            log(cfg, f"{k} {e}: {what}; notifying once")
            summary["notified"].append(what)
            if not dry:
                cfg["notify"]("Election live case", f"{what} (election {e}). Tell a session the winners and the source.")
                st["result_notified"].append(key)
                save_state(cfg, st)
        old = json.loads(c["json"].read_text()) if c["json"].exists() else {}
        ts = cfg["last_commit_ts"](c["json"]) if c["json"].exists() else None
        due = (not old or old.get("baseline_date") != js["baseline_date"] or old.get("election") != js["election"] or ts is None
               or now_utc.timestamp() - ts >= JSON_REFRESH_DAYS * 86400)
        log(cfg, f"{k} {e}: baseline {js['baseline_date']} {js['baseline_close']:.2f}, last final bar {js['as_of']}, since {js['since']}; "
                 f"rows filled now: {filled or 'none'}; json {'refresh due' if (due or filled) else 'fresh'}")
        summary["filled"][k] = filled
        if dry:
            continue
        paths = []
        if filled:
            md_path.write_text(new_md)
            paths.append(md_path)
        if (filled or due) and json.dumps(js, indent=1) != json.dumps(old, indent=1):
            c["json"].write_text(json.dumps(js, indent=1))
            paths.append(c["json"])
            summary["wrote"].append(str(c["json"]))
        if paths:
            msg = (f"election live case ({k} {e.year}): " + (", ".join(filled) + " filled" if filled else "snapshot refreshed")
                   + f" (last final bar {js['as_of']}); automatic, not pushed")
            commit_paths(cfg, paths + [s for s in stub_paths if s not in paths], msg, summary)
            stub_paths = []
            if filled:
                detail = "; ".join(f"{r['label']} {r['ret'] * 100:+.1f}%" for r in ms if r["label"] in filled)
                cfg["notify"]("Election live case", f"{k} {e.year}: {detail}. Committed locally, not pushed.")
                summary["notified"].append("filled:" + ",".join(filled))
    if stub_paths:
        commit_paths(cfg, stub_paths, "election live case: dormant placeholder (presidential 2028)", summary)
    return summary


def commit_paths(cfg, paths, msg, summary):
    try:
        cfg["commit"](paths, msg)
        summary["committed"] = True
        log(cfg, f"committed locally: {msg}")
    except Exception as ex:
        log(cfg, f"COMMIT FAILED: {ex!r}")
        cfg["notify"]("Election live case", "files updated but the local commit failed; check ~/.cgi/election_live.log")


if __name__ == "__main__":
    over = {"dry": "--dry-run" in sys.argv}
    cfg = make_cfg(**over)
    if "--no-fetch" in sys.argv:
        cfg["fetch"] = lambda c: [tuple(r) for r in json.loads((c["root"] / "election_cycle/data/spx_yahoo.json").read_text())]
    r = run(cfg)
    sys.exit(1 if r.get("fetch_failed") else 0)
