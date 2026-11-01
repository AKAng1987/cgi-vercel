"""Offline checks for api/ph_data.py (snapshot validation and the page's views). Run: api/.venv/bin/python scripts/check_ph_data.py"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))
import ph_data as P  # noqa: E402

fails = 0


def check(name, got, want):
    global fails
    ok = got == want
    fails += 0 if ok else 1
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"  got={got!r} want={want!r}"))


T = dt.date(2026, 11, 1)


def row(s, c, adv, m, q=None, ind="Banks", psei=0, mc=1e11, fl=40.0):
    """adv = average daily value traded in pesos (v30)"""
    return {"s": s, "c": c, "v30": adv, "m": m, "q": q if q is not None else m, "w": m, "y": m, "vt": adv, "ind": ind, "sec": "Finance",
            "mc": mc, "fl": fl, "e50": c / 1.05, "e200": c / 1.10, "h3": c * 1.2, "l3": c * 0.8, "psei": psei}


# ── views
rs = [row("AAA", 1e7, 1e7, 10, ind="Mining"), row("BBB", 5e7, 1e7, -5, ind="Mining"), row("CCC", 2e7, 1e7, 30, ind="Banks", psei=1, mc=5e11),
      row("DDD", 1e7, 1e7, 2, ind="Banks"), row("ZZZ", 1, 1e5, 500)]   # ZZZ trades PHP 100k a day: illiquid
lb = P.leaderboard(rs, "m", n_top=2, n_bottom=1)
check("leaderboard top order, illiquid excluded", ([r["s"] for r in lb["top"]], [r["s"] for r in lb["bottom"]], lb["n"]), (["CCC", "AAA"], ["BBB"], 4))
check("vs 50d / 200d", (lb["top"][0]["vs50"], lb["top"][0]["vs200"]), (5.0, 10.0))
sg = P.segments(rs, "m")
check("segments: median, % up, top", [(g["name"], g["median"], g["pct_up"], g["top"]) for g in sg], [("Banks", 16.0, 100, "CCC"), ("Mining", 2.5, 50, "AAA")])
check("segments need two names", P.segments(rs[:1], "m"), [])
edge0 = {"filing_dates": {"AAA": ["2025-11-12", "2025-08-12"], "BBB": ["2025-11-30", "2026-10-20"], "CCC": ["2025-11-14"], "DDD": ["2025-12-30"]},
         "results": []}
en = P.earnings_next(rs, edge0, T)
check("earnings next: last year's date + 365d, weekend moved, already-filed and out-of-window dropped",
      [(e["s"], e["date"]) for e in en], [("AAA", "2026-11-12"), ("CCC", "2026-11-16")])
check("earnings basis stated", en[0]["basis"], "filed 2025-11-12 last year")

edge = {
    "results": [
        {"symbol": "AAA", "kind": "Q", "period": "2026-09-30", "announced": "2026-10-30T10:00", "edge_no": "r1", "scale": 1000.0, "revenue": 110, "revenue_prev": 100,
         "net_income_parent": 20, "net_income_parent_prev": 10, "net_income_parent_ytd": 50, "net_income_parent_prev_ytd": 40, "eps": 0.5, "eps_prev": 0.2},
        {"symbol": "BBB", "kind": "Q", "period": "2026-09-30", "announced": "2026-10-29T10:00", "edge_no": "r2", "scale": 1.0, "revenue": 90, "revenue_prev": 100,
         "net_income_parent": -5, "net_income_parent_prev": 3, "eps": -0.1, "eps_prev": 0.1},
        {"symbol": "CCC", "kind": "Q", "period": "2026-09-30", "announced": "2026-10-28T10:00", "edge_no": "r3", "scale": 1.0, "revenue": 90, "revenue_prev": 100,
         "net_income_parent": 5, "net_income_parent_prev": -3, "eps": 0.1, "eps_prev": -0.1},
        {"symbol": "OLD", "kind": "Q", "period": "2026-03-31", "announced": "2026-05-10T10:00", "edge_no": "r4", "scale": 1.0, "revenue": 1, "revenue_prev": 1,
         "net_income_parent": 1, "net_income_parent_prev": 1},
    ],
    "buybacks": [
        {"symbol": "AAA", "report_date": "2026-10-28", "edge_no": "b1", "shares": 100000, "avg_price": 10.0, "value": 1000000.0, "outstanding_after": 1e9, "cumulative": 5e6, "total_repurchased": 4e8},
        {"symbol": "AAA", "report_date": "2026-10-20", "edge_no": "b2", "shares": 50000, "value": 480000.0, "outstanding_after": 1e9, "cumulative": 4.9e6, "total_repurchased": 3.9e8},
        {"symbol": "AAA", "report_date": "2026-08-01", "edge_no": "b3", "shares": 7, "value": 7.0, "outstanding_after": 1e9},
        {"symbol": "BBB", "report_date": "2026-09-20", "edge_no": "b4", "shares": 10, "value": 100.0, "outstanding_after": 1e6},
    ],
    "disclosures": [
        {"symbol": "AAA", "company": "A Corp", "chip": "buyback", "form": "9-1", "title": "Share Buy-Back Transactions", "amend": 0, "announced": "2026-10-29T08:00", "edge_no": "b1"},
        {"symbol": "BBB", "company": "B Corp", "chip": "other", "form": "4-6", "title": "x", "amend": 0, "announced": "2026-10-29T08:00", "edge_no": "o1"},
        {"symbol": "CCC", "company": "C Corp", "chip": "material", "form": "4-30", "title": "Material Information", "amend": 0, "announced": "2026-10-01T08:00", "edge_no": "m1"},
        {"symbol": "DDD", "company": "D Corp", "chip": "insider", "form": "13-1", "title": "Change in Shareholdings", "amend": 0, "announced": "2026-10-31T08:00", "edge_no": "i1"},
    ],
}
rv = P.results_view(edge, rs, T)
check("results: order, old dropped", [r["s"] for r in rv], ["AAA", "BBB", "CCC"])
check("results: y/y, pesos from scale", (rv[0]["rev_yoy"], rv[0]["ni_yoy"], rv[0]["ni"], rv[0]["revenue"]), (10.0, 100.0, 20000.0, 110000.0))
check("results: loss and swing flags, no % from a loss base", (rv[1]["ni_loss"], rv[1]["ni_yoy"], rv[2]["ni_swing"], rv[2]["ni_yoy"]), (True, None, True, None))
bb = P.buyback_board(edge, T)
check("buyback board: 30d totals, % of outstanding, link to latest", (bb[0]["s"], bb[0]["shares_30d"], bb[0]["value_30d"], bb[0]["pct_outstanding_30d"], bb[0]["edge_no"]),
      ("AAA", 150000, 1480000.0, 0.015, "b1"))
check("buyback board: 60-day cut", [b["s"] for b in bb], ["AAA", "BBB"])
check("buyback avg price 30d", bb[0]["avg_price_30d"], round(1480000.0 / 150000, 4))
mf = P.material_feed(edge, T)
check("material feed: other dropped, 14-day cut, newest first", [m["symbol"] for m in mf], ["DDD", "AAA"])
check("material feed carries buyback figures", mf[1].get("buyback", {}).get("shares"), 100000)
edge["disclosures"][3].update({"subject": "Change in Shareholdings of the Chairman", "insider": {"side": "bought", "net_shares": 20000.0}})
check("material feed carries subject and insider detail", [(m["symbol"], m.get("subject"), m.get("insider", {}).get("side")) for m in P.material_feed(edge, T)][0], ("DDD", "Change in Shareholdings of the Chairman", "bought"))

rb = P.rebalance_watch([row("M1", 10, 1e7, 1, psei=1, mc=1e12, fl=40), row("M2", 10, 1e7, 1, psei=1, mc=2e11, fl=20),
                        row("N1", 10, 1e7, 1, psei=0, mc=5e11, fl=50), row("N2", 10, 1e7, 1, psei=0, mc=1e10, fl=50)])
check("rebalance: members by free-float cap, weakest first", ([m["s"] for m in rb["members"]], rb["weakest_members"][0]["s"]), (["M1", "M2"], "M2"))
check("rebalance: nearest non-member vs smallest member", (rb["nearest_non_members"][0]["s"], rb["nearest_non_members"][0]["vs_smallest_member"]), ("N1", 6.25))

# ── pmi
check("pmi month, same year", P.pmi_month("Oct", "2026-11-02"), "2026-10")
check("pmi month, across new year", P.pmi_month("Dec", "2027-01-04"), "2026-12")
check("pmi month, bad period", P.pmi_month("??", "2027-01-04"), None)
pt = P.pmi_point({"pmi": {"2026-09": 49.6, "2026-10": 51.2}})
check("pmi point", (pt["latest"], pt["prior"], pt["direction"], pt["as_of"]), (51.2, 49.6, "up", "2026-10-01"))
import release_calendar as rc  # noqa: E402
check("BSP next meeting from the schedule", P.bsp_meetings(dt.date(2026, 11, 1))["next"], "2026-12-17")
# ── chart dock: symbol view, pinned, expected report
import json, tempfile  # noqa: E402

check("ema_series first value is the first close, then smooths", P.ema_series([10, 20], 3), [10, 15.0])
cs = P.chart_series([["2026-10-%02d" % d, 1, 2, 0.5, 1 + d * 0.01, 1e6] for d in range(1, 31)] * 1, show=10)
check("chart series: last 10 bars, six EMAs of the same length", (len(cs["bars"]), sorted(cs["ema"]), {len(v) for v in cs["ema"].values()}), (10, ["10", "100", "20", "200", "5", "50"], {10}))
tmp = tempfile.mkdtemp()
rowsd = [row("AAA", 10, 1e7, 5, ind="Mining"), dict(row("COL", 1.19, 2.4e6, -20), extra=1), dict(row("CTS", 0.34, 3e5, 0), extra=1), row("ILQ", 5, 1e5, 1)]
edged = {"directory": {"COL": {"name": "COL Financial"}, "AAA": {"name": "A Corp", "sector": "Mining", "subsector": "Mining"}},
         "filing_dates": {"COL": ["2025-11-17"]}, "results": [], "buybacks": [], "disclosures": [
             {"symbol": "COL", "chip": "insider", "title": "Change in Shareholdings", "announced": "2026-10-09T10:00", "edge_no": "i1", "amend": 0}]}
json.dump({"rows": rowsd, "psei_history": {"2026-10-29": 5700.0, "2026-10-30": 5680.35}, "psei_index": {"c": 5680.35}}, open(os.path.join(tmp, "screener.json"), "w"))
json.dump(edged, open(os.path.join(tmp, "edge.json"), "w"))
json.dump({"bars": {"AAA": [["2026-10-%02d" % d, 1, 2, 0.5, 1.5, 1e6] for d in range(1, 31)]}}, open(os.path.join(tmp, "bars.json"), "w"))
os.environ["PH_LOCAL_DIR"] = tmp
v = P.symbol_view("aaa", T)
check("symbol view: stock with bars, numbers and name", (v["symbol"], v["name"], len(v["bars"]), v["numbers"]["liquid"]), ("AAA", "A Corp", 30, True))
v = P.symbol_view("COL", T)
check("symbol view: an extra name below the line has no bars here but has numbers and disclosures", (v["bars"], v["numbers"]["liquid"], v["numbers"]["extra"], len(v["disclosures"])), ([], False, 1, 1))
check("symbol view: expected report from last year's filing date", v["expected_report"]["date"], "2026-11-17")
v = P.symbol_view("PSEI", T)
check("symbol view: index line", (v["kind"], len(v["line"])), ("index", 2))
check("lists: COL and CTS are in despite trading below the line, other illiquid names are not", sorted(r["s"] for r in P.liquid(rowsd)), ["AAA", "COL", "CTS"])
lb1 = P.leaderboard(rowsd, "m", n_top=5)
check("leaderboard carries COL and CTS", sorted(r["s"] for r in lb1["top"]), ["AAA", "COL", "CTS"])
check("1D horizon exists and keys the d field", (P.HORIZONS["1D"], P._row_view(dict(rowsd[0], d=1.5), "d")["ret"]), ("d", 1.5))
ev = P.chart_events("AAA", {"buybacks": [{"symbol": "AAA", "report_date": "2026-10-20", "shares": 5000, "avg_price": 1.5, "edge_no": "b1"}, {"symbol": "ZZ", "report_date": "2026-10-20", "shares": 1, "avg_price": 1, "edge_no": "b2"}],
    "disclosures": [{"symbol": "AAA", "chip": "insider", "title": "t", "announced": "2026-10-22T09:00", "edge_no": "i1", "insider": {"side": "sold", "net_shares": -2000.0, "name": "J. Cruz"}},
                    {"symbol": "AAA", "chip": "press", "title": "x", "announced": "2026-10-22T09:00", "edge_no": "p1"},
                    {"symbol": "AAA", "chip": "dividend", "title": "d", "announced": "2026-09-01T09:00", "edge_no": "d1", "dividend": {"per_share": 0.5, "record": "2026-09-15"}}]},
    [{"announced": "2026-10-28T10:00", "kind": "Q", "period": "2026-09-30", "edge_no": "r1", "rev_yoy": 6.0, "ni_yoy": None, "ni_loss": True}], "2026-10-01", "2026-10-30")
check("chart events: result, buy-back and insider kept, press and out-of-range dividend dropped, newest first",
      [(e["date"], e["type"]) for e in ev], [("2026-10-28", "R"), ("2026-10-22", "I"), ("2026-10-20", "B")])
check("chart event labels", (ev[0]["label"], ev[1]["label"], ev[1]["side"]), ("Q to 09/26: revenue +6.0%, net income loss", "J. Cruz sold 2,000 sh", "sold"))
del os.environ["PH_LOCAL_DIR"]

# ── digest
def _lead(s, ret, c):
    return {"s": s, "ret": ret, "c": c}


resp = {
    "as_of": "2026-11-02", "freshness": {"prices": {"asof": "2026-10-30"}, "edge": {"built_at": "x"}},
    "header": {"psei": None, "usdphp": None, "policy": None, "bsp": {"next": None}, "regime": "C2G2", "equity": None},
    "macro": {"loans": {"label": "Bank lending", "kind": "level", "unit": "level", "latest": 12731385030000.0, "prior": 1.0, "yoy_pct": 10.6, "as_of": "2026-08-01"},
              "reserves": {"label": "FX reserves", "kind": "level", "unit": "USD", "latest": 100e9, "yoy_pct": None, "as_of": "2026-09-01"},
              "policy": {"label": "BSP", "kind": "rate", "unit": "%", "latest": 5.5, "prior": 5.0, "as_of": "2026-10-01"}},
    "calendar": {"events": [], "late": []},
    "horizons": {h: {"leaders": {"top": [_lead("PHR", 155.4, 0.47), _lead("SGP", 19.3, 26.0)], "bottom": [_lead("ABG", -46.7, 22.7)]},
                     "segments_industry": [{"name": "Banks", "median": 1.0, "n": 6}]} for h in ("1D", "1M")},
    "earnings": {"reported": [], "next": []}, "buybacks": [],
    "material": [{"symbol": "AC", "chip": "dividend", "title": "Declaration of Cash Dividends", "announced": "2026-10-30T12:04",
                  "subject": "Declaration of the Fourth Quarter 2026 Cash Dividends on Outstanding Preferred A Shares", "dividend": {"per_share": 39.74, "record": "2026-11-16"}},
                 {"symbol": "ALCO", "chip": "dividend", "title": "Declaration of Cash Dividends", "announced": "2026-10-29T12:04", "subject": "Cash dividend declaration", "dividend": {"per_share": 7.5, "record": "2026-11-12"}}],
    "scanner": [{"s": "COL", "c": 1.19, "d": 0.0, "m": -20.7, "v30": 2.4e6, "extra": 1}, {"s": "CTS", "c": 0.34, "d": 0.0, "m": 0.0, "v30": 2.8e5, "extra": 1}],
    "index": {"calendar": [], "events": []}, "rebalance": {"weakest_members": [], "nearest_non_members": []}, "breadth": None,
}
edge_dg = {"disclosures": [{"symbol": "COL", "chip": "insider", "title": "Change in Shareholdings", "announced": "2026-10-09T10:00", "edge_no": "i1"},
                           {"symbol": "COL", "chip": "other", "title": "x", "announced": "2026-10-20T10:00", "edge_no": "o1"}]}
dg = P.build_digest(resp, edge_dg)
check("digest: levels as year-on-year and trillions, rates unchanged", (dg["macro"]["loans"], dg["macro"]["reserves"][1], dg["macro"]["policy"][1]), (["Bank lending", "P12.73T", "+10.6% y/y", "2026-08"], "US$100.00B", 5.5))
check("digest: a price under P1 is marked, a normal one is not", (dg["movers"]["1D"]["up"][0], dg["movers"]["1D"]["up"][1]), (["PHR", 155.4, "under P1: tick-size noise"], ["SGP", 19.3]))
check("digest: preferred dividend is flagged, the other is not claimed as common", [d[3] for d in dg["dividends"]], ["preferred", "common or not stated"])
check("digest: COL gets its latest real filing (the 'other' form is skipped), CTS with none stays empty", [(e["s"], e["last_filing"] and e["last_filing"][0]) for e in dg["extra_names"]], [("COL", "2026-10-09"), ("CTS", None)])

# ── freshness
import freshness as fr  # noqa: E402

ok = fr.ph_problems(dt.date(2026, 11, 3), "2026-10-30", "2026-11-02T11:00:00+00:00", {"filings_tried": 10, "n_failed": 1}, 90)
check("ph freshness: Monday after a Friday close is clean", ok["n_problems"], 0)
check("ph freshness: five weekdays of nothing is a problem", [p["check"] for p in fr.ph_problems(dt.date(2026, 11, 9), "2026-10-30", "2026-11-08T11:00:00+00:00", None, 90)["problems"]], ["prices"])
check("ph freshness: EDGE not rebuilt for 4 days", [p["check"] for p in fr.ph_problems(dt.date(2026, 11, 3), "2026-11-02", "2026-10-29T11:00:00+00:00", None, 90)["problems"]], ["edge"])
check("ph freshness: parse failures", [p["check"] for p in fr.ph_problems(dt.date(2026, 11, 3), "2026-11-02", "2026-11-03T01:00:00+00:00", {"filings_tried": 10, "n_failed": 5}, 90)["problems"]], ["edge_parse"])
check("ph freshness: nothing stored", [p["check"] for p in fr.ph_problems(dt.date(2026, 11, 3), None, None, None, 0)["problems"]], ["prices", "edge"])
check("ph freshness: thin coverage", [p["check"] for p in fr.ph_problems(dt.date(2026, 11, 3), "2026-11-02", "2026-11-03T01:00:00+00:00", None, 12)["problems"]], ["prices_coverage"])
# ── index calendar, events, PSE circular
import ph_index as X  # noqa: E402

cal = X.calendar_view(dt.date(2026, 11, 2))
check("calendar: nearest upcoming first (MSCI 11 Nov), done events last", ([e["provider"] for e in cal[:2]], cal[0]["days_to_announce"], cal[-1]["status"]), (["FTSE", "MSCI"], 7, "done"))
check("calendar problems: none with the table as written", X.calendar_problems(dt.date(2026, 11, 2), [])["n_problems"], 0)
check("calendar problems: the table runs out for MSCI/FTSE/PSE in 2029", sorted(p["check"] for p in X.calendar_problems(dt.date(2029, 1, 1), [])["problems"]), ["calendar_fts" + "e", "calendar_msci", "calendar_pse"])
check("calendar problems: MSCI announced 11 Nov, nothing stored 13 Nov -> problem; stored -> clean",
      (X.calendar_problems(dt.date(2026, 11, 13), [])["n_problems"], X.calendar_problems(dt.date(2026, 11, 13), [{"provider": "MSCI", "date": "2026-11-11"}])["n_problems"]), (1, 0))
good = {"events": [{"provider": "msci", "date": "2026-11-11", "kind": "add", "index": "MSCI Philippines", "symbols": ["abc", "DE F", "AB1"], "effective": "2026-12-01", "source_url": "https://example.com/x", "note": "n"},
                   {"provider": "evil", "date": "2026-11-11", "kind": "add", "symbols": ["ABC"]},
                   {"provider": "FTSE", "date": "2020-01-01", "kind": "note"},
                   {"provider": "FTSE", "date": "2026-11-12", "kind": "add", "symbols": []},
                   {"provider": "PSE", "date": "2026-11-12", "kind": "note", "note": "x" * 400, "source_url": "javascript:alert(1)"}]}
rows, rep = X.clean_events(good, dt.date(2026, 11, 13))
check("events: valid kept (symbols filtered), bad provider/date/empty add dropped", (rep["kept"], rep["dropped"], rows[0]["symbols"], rows[1]["note"] == "x" * 140, rows[1]["source_url"]), (2, {"provider": 1, "outside window": 1, "no symbols": 1}, ["ABC", "AB1"], True, ""))
check("events: merge replaces same key", len(X.merge_events(rows, [dict(rows[0], note="new")])), 2)
txt = open(os.path.join(os.path.dirname(__file__), "..", "..", "market-dashboard", "tests", "ph_edge_fixtures", "pse_cn_2026_0035.txt")).read() if os.path.exists(os.path.join(os.path.dirname(__file__), "..", "..", "market-dashboard", "tests", "ph_edge_fixtures", "pse_cn_2026_0035.txt")) else None
if txt:
    rv = X.parse_pse_review(txt)
    check("PSE circular: number, dates, 30 PSEi members, summary lines", (rv["circular"], rv["date"], rv["effective"], len(rv["psei_members"]), rv["summary"][0]), ("2026-0035", "2026-07-27", "2026-08-03", 30, "PSEi MYNLD CNVRG"))
    check("PSEi change by set difference", X.psei_change([m for m in rv["psei_members"] if m != "MYNLD"] + ["CNVRG"], rv["psei_members"]), {"added": ["MYNLD"], "removed": ["CNVRG"]})
check("a non-review circular is ignored", X.parse_pse_review("CN No. 2026-0036 REMINDER on trading hours"), None)
print("FAILS:", fails)
sys.exit(1 if fails else 0)
