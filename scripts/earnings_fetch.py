"""
earnings_fetch.py -- pull companies' own earnings filings from SEC EDGAR. Free, no key, zero tokens.

For every name in the universe it finds 8-Ks that carry Item 2.02 (results of operations) and saves the press release
(Exhibit 99.1) and any investor slides (Exhibit 99.2) as plain text under ~/.cgi/earnings/. The text stays on this Mac
(never committed). A reader (the cgi-earnings-web task) then extracts guidance, demand statements and named companies.

  python3 scripts/earnings_fetch.py --since 2026-07-01          # backfill from a date (used for the pilot)
  python3 scripts/earnings_fetch.py                              # new filings since the last run (daily)
  python3 scripts/earnings_fetch.py --tickers NVDA,MSFT --since 2026-07-01
  python3 scripts/earnings_fetch.py --universe                   # print the universe and who is not an SEC 8-K filer

Universe: ~/.cgi/earnings_universe.json (a JSON list of tickers; edit it to add names). If it does not exist it is seeded
from the fundamentals list (theme constituents plus the AI layers) plus a short list of mega caps.

Foreign filers (TSM, ASML ...) file 6-K/20-F, not 8-K. Their 6-K results releases are picked up when the 6-K names
an exhibit 99; names with neither are reported as "not covered".
"""
from __future__ import annotations

import argparse, ast, datetime as dt, gzip, html, json, pathlib, re, sys, time, urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path("~/.cgi/earnings").expanduser()
UNIVERSE = pathlib.Path("~/.cgi/earnings_universe.json").expanduser()
STATE = OUT / "state.json"
UA = "CGI macro-regime research (ang.arvin@ymail.com)"          # same contact line as api/sec_xbrl.py
BANKS = ["JPM", "BAC", "WFC", "C", "GS", "MS", "USB", "PNC", "TFC", "SCHW", "COF", "AXP", "BK", "STT", "ALLY"]
NEO_CLOUD = ["CRWV", "NBIS", "IREN", "ORCL", "SNOW", "MDB", "NET", "DOCN", "TEAM", "WDAY", "ADBE", "INTU", "SHOP", "NOW", "CRM"]
MEGA = BANKS + NEO_CLOUD + ["AAPL", "TSLA", "ORCL", "ADBE", "NFLX", "QCOM", "TXN", "AMAT", "LRCX", "KLAC", "TSM", "ASML", "V", "MA", "GS", "MS"]
MAX_TEXT = 120_000          # characters kept per document


def get(url: str, timeout: int = 45) -> bytes:
    time.sleep(0.15)        # SEC asks for no more than 10 requests a second
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return gzip.decompress(raw) if r.headers.get("Content-Encoding") == "gzip" else raw


def seed_universe() -> list[str]:
    tickers: list[str] = []
    src = (ROOT / "api" / "fundamentals_data.py").read_text()
    for name in ("FALLBACK_CONSTITUENTS", "AI_LAYERS"):
        m = re.search(rf"^{name}[^=]*=\s*(\{{.*?^\}})", src, re.S | re.M)
        if m:
            for v in ast.literal_eval(re.sub(r"#[^\n]*", "", m.group(1))).values():
                tickers += v
    return sorted(set(tickers + MEGA))


# Names that companies use for each other in their releases, for the "who mentions whom" read (zero tokens).
ALIASES = {"CoreWeave": "CRWV", "Nebius": "NBIS", "Oracle": "ORCL", "OpenAI": "private", "Anthropic": "private",
           "Microsoft": "MSFT", "Azure": "MSFT", "AWS": "AMZN", "Amazon": "AMZN", "Google": "GOOGL", "Meta": "META",
           "NVIDIA": "NVDA", "TSMC": "TSM", "Micron": "MU", "Snowflake": "SNOW", "Salesforce": "CRM", "Databricks": "private",
           "ServiceNow": "NOW", "Broadcom": "AVGO", "AMD": "AMD", "Intel": "INTC"}


def mentions() -> int:
    """Which saved release mentions which other company, with the sentence. Run after a fetch."""
    rows = []
    for f in sorted(OUT.glob("*.txt")):
        me = f.name.split("-")[0]
        body = f.read_text().split("\n\n", 1)[-1]
        for sent in re.split(r"(?<=[.!?])\s+|\n+", body):
            if not 40 < len(sent) < 450:
                continue
            for name, tk in ALIASES.items():
                if tk != me and re.search(rf"\b{name}\b", sent):
                    rows.append({"filer": me, "mentions": name, "ticker": tk, "file": f.name, "sentence": sent.strip()})
    print(json.dumps(rows, indent=1))
    return 0


def universe() -> list[str]:
    if not UNIVERSE.exists():
        UNIVERSE.parent.mkdir(parents=True, exist_ok=True)
        UNIVERSE.write_text(json.dumps(seed_universe(), indent=0))
    return json.loads(UNIVERSE.read_text())


def cik_map() -> dict[str, int]:
    d = json.loads(get("https://www.sec.gov/files/company_tickers.json", 60))
    return {v["ticker"].upper(): int(v["cik_str"]) for v in d.values()}


def to_text(raw: bytes) -> str:
    t = raw.decode("utf-8", "ignore")
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", t)
    t = re.sub(r"(?i)</(p|div|tr|li|h\d|br)>|<br\s*/?>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n\n", t).strip()[:MAX_TEXT]


def exhibits(cik: int, acc_nodash: str, primary: str) -> list[str]:
    """The press release and slides inside a filing: the exhibit documents, not the cover page or XBRL viewer files.
    Companies name them freely (ex99, q2fy27pr ...), so take every other HTML document, biggest first."""
    idx = json.loads(get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/index.json"))
    items = idx.get("directory", {}).get("item", [])
    docs = [(int(i.get("size") or 0), i["name"]) for i in items
            if re.search(r"\.(htm|html)$", i["name"], re.I) and i["name"] != primary
            and not re.match(r"R\d+\.htm", i["name"], re.I) and "index" not in i["name"].lower()]
    return [n for _sz, n in sorted(docs, reverse=True)]


def filings_for(ticker: str, cik: int, since: str) -> list[dict]:
    d = json.loads(get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    rec = d.get("filings", {}).get("recent", {})
    out = []
    for i, form in enumerate(rec.get("form", [])):
        date = rec["filingDate"][i]
        if date < since:
            break          # newest first, so everything after this is older
        items = rec.get("items", [""] * len(rec["form"]))[i] or ""
        if (form == "8-K" and "2.02" in items) or form == "6-K":
            out.append({"ticker": ticker, "cik": cik, "form": form, "date": date, "items": items,
                        "acc": rec["accessionNumber"][i].replace("-", ""),
                        "doc": rec["primaryDocument"][i]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--tickers")
    ap.add_argument("--universe", action="store_true")
    ap.add_argument("--mentions", action="store_true", help="read the saved releases and list who mentions whom")
    a = ap.parse_args()
    if a.mentions:
        return mentions()
    tickers = [t.strip().upper() for t in a.tickers.split(",")] if a.tickers else universe()
    ciks = cik_map()
    if a.universe:
        print(f"{len(tickers)} names; not in SEC's ticker file: {[t for t in tickers if t not in ciks]}")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {"seen": [], "last_run": None}
    since = a.since or state["last_run"] or (dt.date.today() - dt.timedelta(days=7)).isoformat()
    seen, new, missing, failed = set(state["seen"]), [], [], []
    for t in tickers:
        cik = ciks.get(t)
        if cik is None:
            missing.append(t)
            continue
        try:
            fl = filings_for(t, cik, since)
        except Exception as exc:  # noqa: BLE001 -- one name failing must not stop the run
            failed.append(f"{t}: {type(exc).__name__}")
            continue
        for f in fl:
            if f["acc"] in seen:
                continue
            try:
                docs = exhibits(f["cik"], f["acc"], f["doc"]) or [f["doc"]]
                parts = []
                for n in docs[:3]:
                    parts.append(f"=== {n} ===\n" + to_text(get(f"https://www.sec.gov/Archives/edgar/data/{f['cik']}/{f['acc']}/{n}")))
                body = "\n".join(parts)
                if f["form"] == "6-K" and not re.search(r"(?i)(quarter|results|earnings)", body[:4000]):
                    seen.add(f["acc"])
                    continue                      # a 6-K that is not a results release
                path = OUT / f"{t}-{f['date']}-{f['acc']}.txt"
                url = f"https://www.sec.gov/Archives/edgar/data/{f['cik']}/{f['acc']}/"
                path.write_text(f"SOURCE {url}\nTICKER {t}\nFORM {f['form']}  FILED {f['date']}  ITEMS {f['items']}\n\n" + "\n\n".join(parts))
                new.append({"ticker": t, "date": f["date"], "form": f["form"], "file": str(path), "source": url,
                            "chars": sum(len(p) for p in parts)})
                seen.add(f["acc"])
            except Exception as exc:  # noqa: BLE001
                failed.append(f"{t} {f['acc']}: {type(exc).__name__}")
    state.update({"seen": sorted(seen), "last_run": dt.date.today().isoformat()})
    STATE.write_text(json.dumps(state))
    print(json.dumps({"since": since, "universe": len(tickers), "new_filings": new,
                      "not_in_sec_file": missing, "failed": failed}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
