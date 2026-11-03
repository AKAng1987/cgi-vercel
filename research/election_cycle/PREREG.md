# PREREG: election_cycle   Locked 2026-11-04 (US midterm held 2026-11-03; no 2026 result enters any test)
Lock note: the original request said 2026-11-03 "before US results". The real day of this commit is 2026-11-04, after the vote.
Nothing in the tests uses 2026 (history ends with the 2022 midterm), and no return has been computed when this is committed, so
the lock is still before any test. The 2026 live case is tracking only, with its state measured at the 2 Nov close.

Question. Does the S&P 500 (price index) do better than its normal baseline (a) in the 12 months after a midterm election and
(b) worse during the midterm-year primary season (Mar 1 - Sep 30), and does the state going in (correction / flat / up)
change either? Calendar context only; it never moves size by itself.
Data. SPX daily closes 1928-2026 (Yahoo ^GSPC, cross-checked to TradingView SP:SPX; IB 2021+); Saturday bars before 1952-06-01
dropped; tests use midterms 1950-2022 (19). CGI compass (from 2004-07) / grid (from 2008-03) and 20-day vol where covered.
State going in (close before election day; for the season test, last close of February): Correction = drawdown from the
52-week closing high >= 10%. Up = 3-month return >= +3% and not Correction. Flat = everything else. Fixed now, never fitted.
Primary (one). 252-trading-day return from the close before election day, midterm years vs baseline = forward 252-day returns of
all start days in the same 20-day-volatility tercile (expanding, known at the time; warm-up from 1928; start days within 21
trading days of any election excluded). Inference: permutation of start dates plus moving-block bootstrap (block 252) for the
overlapping baseline windows; two-sided, 95%.
Secondary (pre-registered, 6 tests): (1) midterm-year Mar 1-Sep 30 return and max drawdown vs the same window in the 54
non-midterm years 1950-2022; (2) post-election +21, +63, +126 trading days vs the same baseline; (3) the primary test on 1994-2022.
Exploratory (descriptive tables, labelled): correction/flat/up split for both windows (6 cells), presidential-party seat loss,
divided government after (8 comparisons). Expected false positives at p<0.05: about 0.05 primary + 0.3 secondary + 0.4 exploratory.
Regime: CGI regime shown beside the 4-6 covered midterms; never part of a verdict.
Self-test (check_harness.py must print SELFTEST OK before run.py counts): plant +10 points of 12-month excess in 19 random years:
found in >= 6 of 8 runs; pure noise: claimed in <= 2 of 20; report the smallest effect detectable at 80% power.
Live case 2026 (not counted): state at the 2 Nov 2026 close, CGI regime now (C1G2), tracked at +1, +3, +6, +12 months in RESULTS.md.
Honest prior: not distinguishable from drift plus volatility state at n = 19; the state split is likely null.
Where a pass would go: a descriptive CGI context note, "not a forecast". Never a size or an entry rule.

Approved defaults (from the plan): bulk history from Yahoo by script; TradingView spot-checks of the close before each election
and the last 300 bars; IB for 2021+; any gap over 0.1% listed in RESULTS.md. Election results (seat change, control, divided
government) are hand-entered from the House Clerk and Senate history pages with sources; exploratory only.
Operational definitions added at build time (no return seen yet): "trading day" = a bar in the cleaned series; "close before
election day" = last bar strictly before the election date; the 252-day return = close[i+252]/close[i]-1 with i the index of that
bar; season window = last close of Feb to last close of Sep; max drawdown = worst peak-to-trough on closes inside that window;
20-day vol = stdev of 20 daily log returns ending at the start bar; terciles cut from all start bars up to and including that
day (expanding); non-midterm years = 1950-2022 years not divisible by the midterm pattern (1950, 1954, ... 2022 excluded).
