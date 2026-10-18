"""
fill_customer_links.py -- build the 10-K / 10-Q customer-disclosure cache OFF the API, then store it where the API reads it.

Why: the first build downloads ~30 annual reports (2-10 MB each). Run inside the free Render API on top of the normal
Fundamentals rebuild it overloaded the instance (2026-10-17 outage). Here it runs on this Mac and only the finished
result is written to the cache, so a page visit never triggers the heavy work. Filings change once a year, so run it
every Sunday before the brief (task refresh-customer-links-cache). The API only READS the cache and never rebuilds it,
so a late or missed run leaves the previous copy in place instead of triggering a heavy build.

  api/.venv/bin/python scripts/fill_customer_links.py
"""
import pathlib, sys, time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "api"))
import cache  # noqa: E402
import customer_links  # noqa: E402
import fundamentals_data as fdm  # noqa: E402

t0 = time.time()
syms = fdm.customer_link_symbols()
print(f"building {len(syms)} names ...", flush=True)
data = customer_links.build_customer_links(syms)
ok = [c for c in data["companies"] if c.get("status") == "ok"]
print(f"{len(ok)} parsed, {data['n_with_disclosure']} with a disclosure, {data['n_named']} named, {time.time() - t0:.0f}s")
if len(ok) < len(syms) // 2:
    sys.exit("fewer than half parsed; not writing the cache")
cache.set("customer_links", data)
print("stored under cache key customer_links")
