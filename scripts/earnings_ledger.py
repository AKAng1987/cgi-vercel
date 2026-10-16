"""
earnings_ledger.py -- the memory behind the weekly earnings threads. Zero tokens to run.

The Sunday brief reads each new results release (scripts/earnings_fetch.py puts the text in ~/.cgi/earnings/, local only).
This ledger keeps what it found as numbers, per company and quarter, so next quarter's thread can say "up from X" and a
claim made in a thread can be checked later. Only company-published facts go in, each with its SEC source URL; the
published copy feeds the Fundamentals tab (the repo and the page are public), so never put positions or P&L here.

  python3 scripts/earnings_ledger.py add FACTS.json     # facts from a release (see FORMAT below); '-' reads stdin
  python3 scripts/earnings_ledger.py show JPM           # every stored quarter for a name
  python3 scripts/earnings_ledger.py delta              # latest quarter vs the one before, every name with two
  python3 scripts/earnings_ledger.py claim CLAIM.json   # record a thread's claim so it can be checked
  python3 scripts/earnings_ledger.py score              # check due claims against newer facts
  python3 scripts/earnings_ledger.py publish            # write web/app/components/fundamentals/earnings_facts.json

FORMAT for add (one object or a list):
  {"ticker": "JPM", "quarter": "2026Q3", "filed": "2026-10-13", "source": "https://www.sec.gov/Archives/...",
   "metrics": {"provision_bn": {"value": 4.1, "unit": "$bn", "note": "credit loss provision"}},
   "names": ["Nvidia"]}                       # companies the release names (optional)
FORMAT for claim:
  {"id": "2026w42-banks-1", "date": "2026-10-18", "thread": "banks", "claim": "provisions keep rising",
   "ticker": "JPM", "metric": "provision_bn", "baseline": 4.1, "direction": "up", "check_quarter": "2026Q4"}
  A claim with no ticker/metric/baseline is recorded as "not testable" (a view, not a measurement).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
STORE = pathlib.Path("~/.cgi/earnings_facts.json").expanduser()
PUBLISHED = ROOT / "web" / "app" / "components" / "fundamentals" / "earnings_facts.json"
QUARTER = re.compile(r"^\d{4}Q[1-4]$")
SEC_URL = re.compile(r"^https://(www\.sec\.gov|data\.sec\.gov)/")
FLAT = 0.01      # a move under 1% of the baseline is "flat", neither up nor down


def load() -> dict:
    if STORE.exists():
        return json.loads(STORE.read_text())
    return {"facts": {}, "claims": []}


def save(db: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(db, indent=1, sort_keys=True))


def validate_fact(f: dict) -> list[str]:
    bad = []
    if not re.fullmatch(r"[A-Z.\-]{1,6}", str(f.get("ticker", ""))):
        bad.append("ticker")
    if not QUARTER.match(str(f.get("quarter", ""))):
        bad.append("quarter (want 2026Q3)")
    if not SEC_URL.match(str(f.get("source", ""))):
        bad.append("source (must be an sec.gov URL)")
    m = f.get("metrics")
    if not isinstance(m, dict) or not m:
        bad.append("metrics")
    else:
        for k, v in m.items():
            if not isinstance(v, dict) or not isinstance(v.get("value"), (int, float)) or isinstance(v.get("value"), bool):
                bad.append(f"metric {k}: value must be a number")
    return bad


def add(items: list[dict]) -> int:
    db, n = load(), 0
    for f in items:
        bad = validate_fact(f)
        if bad:
            print(f"REFUSED {f.get('ticker')} {f.get('quarter')}: {', '.join(bad)}", file=sys.stderr)
            return 1
        q = db["facts"].setdefault(f["ticker"], {}).setdefault(f["quarter"], {"metrics": {}, "names": []})
        q.update({"filed": f.get("filed"), "source": f["source"]})
        q["metrics"].update(f["metrics"])
        q["names"] = sorted(set(q["names"]) | set(f.get("names", [])))
        n += 1
    save(db)
    print(f"stored {n} release(s)")
    return 0


def delta_rows(db: dict) -> list[dict]:
    rows = []
    for t, qs in sorted(db["facts"].items()):
        keys = sorted(qs)
        if len(keys) < 2:
            continue
        new, old = qs[keys[-1]], qs[keys[-2]]
        for m, v in new["metrics"].items():
            if m in old["metrics"]:
                a, b = v["value"], old["metrics"][m]["value"]
                rows.append({"ticker": t, "metric": m, "unit": v.get("unit", ""), "from_q": keys[-2], "to_q": keys[-1],
                             "from": b, "to": a, "change_pct": round((a - b) / abs(b) * 100, 1) if b else None})
    return rows


def judge(baseline: float, new: float, direction: str) -> str:
    if baseline == 0:
        return "not testable"
    move = (new - baseline) / abs(baseline)
    if abs(move) < FLAT:
        return "flat"
    return "held" if (move > 0) == (direction == "up") else "did not hold"


def claim(c: dict) -> int:
    db = load()
    if any(x["id"] == c["id"] for x in db["claims"]):
        print(f"claim {c['id']} already recorded", file=sys.stderr)
        return 1
    c = dict(c)
    testable = all(c.get(k) is not None for k in ("ticker", "metric", "baseline", "direction", "check_quarter"))
    c["result"] = None if testable else "not testable"
    db["claims"].append(c)
    save(db)
    print(f"recorded {c['id']} ({'testable' if testable else 'not testable'})")
    return 0


def score(db: dict) -> int:
    n = 0
    for c in db["claims"]:
        if c.get("result"):
            continue
        q = db["facts"].get(c["ticker"], {}).get(c["check_quarter"])
        if q and c["metric"] in q["metrics"]:
            c["result"] = judge(c["baseline"], q["metrics"][c["metric"]]["value"], c["direction"])
            c["checked"] = dt.date.today().isoformat()
            n += 1
    save(db)
    print(f"scored {n} claim(s)")
    return 0


def summary(db: dict) -> dict:
    done = [c for c in db["claims"] if c.get("result") in ("held", "did not hold", "flat")]
    return {"claims": len(db["claims"]), "tested": len(done),
            "held": sum(1 for c in done if c["result"] == "held"),
            "not_testable": sum(1 for c in db["claims"] if c.get("result") == "not testable"),
            "waiting": sum(1 for c in db["claims"] if c.get("result") is None)}


def publish(db: dict) -> int:
    out = {"as_of": dt.date.today().isoformat(),
           "note": "Company-published figures with their SEC source. Descriptive context, not a signal.",
           "facts": db["facts"], "delta": delta_rows(db), "claims": db["claims"], "scorecard": summary(db)}
    PUBLISHED.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(f"wrote {PUBLISHED.relative_to(ROOT)}: {len(db['facts'])} names, {len(out['delta'])} changes, {len(db['claims'])} claims")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd in ("add", "claim"):
        raw = sys.stdin.read() if len(argv) < 3 or argv[2] == "-" else pathlib.Path(argv[2]).read_text()
        data = json.loads(raw)
        if cmd == "add":
            return add(data if isinstance(data, list) else [data])
        return claim(data)
    db = load()
    if cmd == "show":
        print(json.dumps(db["facts"].get(argv[2].upper(), {}), indent=1))
        return 0
    if cmd == "delta":
        print(json.dumps(delta_rows(db), indent=1))
        return 0
    if cmd == "score":
        return score(db)
    if cmd == "publish":
        return publish(db)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
