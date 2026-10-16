"""
check_fundamentals_fit.py -- offline checks for the per-theme "fit" chip (api/fundamentals_data._fit).

The chip says whether a theme's own constituents agree with the theme running. It is context, not a signal, so the
rule is deliberately conservative: it needs 3+ readable names, more positive than negative reads, and a median
acceleration that does not point the other way. "buying growth" and "holding" count for neither side.
Run: api/.venv/bin/python scripts/check_fundamentals_fit.py
"""
import pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "api"))
import fundamentals_data as fd  # noqa: E402

fail = []


def check(name, got, want):
    ok = got == want
    print(("ok   " if ok else "FAIL ") + f"{name}: {got}")
    if not ok:
        fail.append(name)


def roll(verdicts, med):
    return {"status": "ok", "n": sum(verdicts.values()), "verdicts": verdicts, "median_revenue_acceleration_pp": med}


check("no data", fd._fit({"status": "no data", "n": 0})["label"], "no data")
check("two names is thin", fd._fit(roll({"capturing": 2}, 5.0))["label"], "thin")
check("capturing majority and positive median confirms", fd._fit(roll({"capturing": 3, "holding": 1}, 2.0))["label"], "confirms")
check("slowing majority and negative median contradicts", fd._fit(roll({"slowing": 2, "rolling over": 1, "holding": 1}, -3.0))["label"], "contradicts")
check("positive majority but negative median is mixed", fd._fit(roll({"capturing": 3, "holding": 1}, -1.0))["label"], "mixed")
check("buying growth counts for neither side", fd._fit(roll({"buying growth": 4}, 4.0))["label"], "mixed")
check("annual-only theme (no median) falls back to the counts", fd._fit(roll({"accelerating": 3}, None))["label"], "confirms")
check("tie is mixed", fd._fit(roll({"capturing": 2, "slowing": 2}, 0.0))["label"], "mixed")
sys.exit(1 if fail else 0)
