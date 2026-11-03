# election_cycle: do US midterm elections change how the S&P 500 behaves?

Built 2026-11-04. Pre-registered in `PREREG.md` (commit 69dccb5, before any return was computed; Amendment 1 committed 2e7a755, also before any real-data return). Offline; ships nothing. Calendar context only, never a size or entry rule.

## Verdict (n = 19, so a null means "not distinguishable", never "no effect")
- **Primary test: not distinguishable.** The 252-trading-day return from the close before election day averaged +15.6% against a volatility-matched baseline of +9.3%, an excess of **+6.3 points**. Permutation p = 0.14; bootstrap 95% interval +1.5 to +11.5. A claim needs both, so **no claim**. With 19 midterms the test only detects effects of about +12 points or more, so +6 points can be real or luck.
- **Secondary tests (6 pre-registered): 3 of 6 clear p < 0.05, but read them with care.** Post-election +63 bars: +5.5 pts (p = 0.014); +126 bars: +9.4 pts (p = 0.008); midterm-year Mar 1 to Sep 30 return -6.8 pts vs other years (p = 0.038) and max drawdown 6.1 pts deeper (p = 0.001). Six tests were run, so about 0.3 false positives are expected at 5%; after a Bonferroni cut (0.05/6 = 0.008) only the +126-bar window and the season drawdown survive. These are one story told twice (a weak midterm summer, then a recovery after the vote), not two independent findings, and the primary 12-month window did not confirm it. The 1994-2022 subset (n = 8) gave +3.9 pts, p = 0.49.
- **State going in (correction / flat / up): no pattern worth reading.** Cells are 3 to 8 midterms each (Flat has only 3 before the election). Descriptive only.
- **Politics (seat loss, divided government): no pattern.** 12-month excess is +5.8% vs +6.7% for big vs small House losses; identical 14 vs 5 split for "President's party lacks House majority" and "divided government" (the same 14 years).
- **Where it goes:** at most a descriptive CGI context note ("midterm summers have been weak and the following 6 months strong, n = 19, not a forecast"). Never a rule. Not added to the settled index; that waits for a clean audit.

## Method (as pre-registered, plus Amendment 1)
- Data: SPX daily closes from Yahoo `^GSPC` (24,827 bars, 1927-12-30 to 2026-11-02), price index without dividends. Yahoo carries no Saturday bars at all, so the Saturday rule (drop before 1952-06-01) changed nothing. The 3 Nov 2026 bar was intraday when built and is excluded; the live case uses the 2 Nov close.
- Event = last bar strictly before election day (19 midterms 1950-2022, computed as the Tuesday after the first Monday in November). Volatility = stdev of 20 daily log returns; terciles cut expanding from all bars since 1928 (known at the time). The baseline pool is start days from 1950 on, in the same tercile, excluding any start day within 21 bars of an election.
- State: Correction = drawdown from the 52-week closing high of 10% or more; Up = 3-month return of +3% or more and not Correction; Flat = the rest.
- Inference: permutation moves the whole 19-date calendar by a common circular offset inside 1950-2025 (keeps the 4-year spacing; every offset used); bootstrap interval from a moving-block bootstrap (block 252) of the baseline plus resampled events. Season tests: midterm years vs the 54 other years 1950-2022, label permutation (10,000).

## Self-test (`check_harness.py` prints SELFTEST OK)
- Planted +15 points: found **8/8** (bar: 6/8). Noise: falsely claimed **1/20** (bar: at most 2/20).
- Smallest effect detectable at 80% power: **+12 points** of 12-month excess (power 55% at +10, 82% at +12, 100% at +15).
- The original PREREG bar was +10 points found in 6/8; it fails (5/8) because power at +10 is only about 55-60%. That is why Amendment 1 moved the planted effect to +15; both numbers are shown in the harness output.

## Per-midterm table (12m = 252 bars from the close before election day; excess vs same-tercile baseline)
| Year | State going in | Vol tercile | 12m | Baseline | Excess | Mar-Sep return | Mar-Sep max DD | CGI (compass/grid) |
|---|---|---|---|---|---|---|---|---|
| 1950 | Up | 1 | +17.5% | +9.0% | +8.5 | +13.0% | -14.0% | n/a |
| 1954 | Flat | 0 | +33.2% | +8.9% | +24.3 | +23.6% | -4.4% | n/a |
| 1958 | Up | 0 | +11.1% | +8.9% | +2.2 | +22.6% | -2.9% | n/a |
| 1962 | Correction | 2 | +24.8% | +9.6% | +15.2 | -19.6% | -26.4% | n/a |
| 1966 | Correction | 1 | +12.9% | +9.0% | +3.9 | -16.1% | -19.4% | n/a |
| 1970 | Correction | 0 | +11.1% | +8.9% | +2.3 | -5.8% | -23.2% | n/a |
| 1974 | Correction | 2 | +20.5% | +9.6% | +11.0 | -34.0% | -36.3% | n/a |
| 1978 | Correction | 2 | +7.0% | +9.6% | -2.6 | +17.8% | -6.0% | n/a |
| 1982 | Up | 2 | +20.6% | +9.6% | +11.0 | +6.5% | -14.3% | n/a |
| 1986 | Up | 1 | +4.0% | +9.0% | -5.0 | +1.9% | -9.4% | n/a |
| 1990 | Correction | 2 | +24.1% | +9.6% | +14.5 | -7.8% | -18.4% | n/a |
| 1994 | Flat | 1 | +27.1% | +9.0% | +18.0 | -0.9% | -6.8% | n/a |
| 1998 | Up | 2 | +21.2% | +9.6% | +11.7 | -3.1% | -19.3% | n/a |
| 2002 | Correction | 2 | +16.0% | +9.6% | +6.4 | -26.3% | -31.8% | n/a |
| 2006 | Up | 0 | +6.9% | +8.9% | -1.9 | +4.3% | -7.7% | C4 / n/a |
| 2010 | Up | 1 | +5.8% | +9.0% | -3.2 | +3.3% | -16.0% | C2 / G2 |
| 2014 | Up | 2 | +4.6% | +9.6% | -5.0 | +6.1% | -4.0% | C1 / G4 |
| 2018 | Flat | 2 | +12.4% | +9.6% | +2.8 | +7.4% | -7.3% | C3 / G3 |
| 2022 | Correction | 2 | +15.1% | +9.6% | +5.6 | -18.0% | -22.6% | C4 / G1 |

CGI regime is shown for the 5 midterms it covers (compass from 2004-07, grid from 2008-03); descriptive, never part of a verdict. Hand-recomputed from raw closes for 1950, 1974 and 2022 (12m return, drawdown, 3-month return): all match.

By state (exploratory): mean 12-month excess after Correction (n = 8) +7.0 pts, Flat (n = 3) +15.1, Up (n = 8) +2.3. Mar-Sep return by end-February state: Correction (n = 6) -3.2%, Flat (n = 7) -7.8%, Up (n = 6) +8.1%.

## Live case 2026 (not counted)
- Election 2026-11-03. State at the 2 Nov close (7541.40): **Flat** (drawdown from the 52-week closing high -3.5%, 3-month return -2.5%), volatility tercile 1 (middle). Baseline 12-month return for that tercile: +9.0%.
- CGI regime now (`get_regime`, 3 Nov): **C1G2** (compass C1 since 2 Nov, grid G2 since 30 Sep).
- Tracking (fill in as they arrive; return from the 2 Nov close):

| Horizon | Date | SPX | Return |
|---|---|---|---|
| +1 month | 2026-12-02 | | |
| +3 months | 2027-02-02 | | |
| +6 months | 2027-05-03 | | |
| +12 months | 2027-11-02 | | |

## Gaps, deviations and what was not done
- **Price cross-check: 320 closes compared with TradingView SP:SPX (the close before each of the 19 elections plus 2 Nov 2026, and the last 300 bars): 0 gaps over 0.1%.**
- **IB cross-check not done:** `get_price_history` returned "Details currently unavailable" on two tries (month and 15-bar requests). The IB tool also reaches back five years at most. No IB gap list exists.
- Election results: House seats from the House Clerk's Party Divisions page (fetched 2026-11-04). **The Senate.gov history page returned 403, so Senate majorities come from Wikipedia's party-divisions table (source deviation).** President's party is the standard roll, not fetched. All exploratory.
- A system Python numpy was the wrong CPU build; the runs used a throwaway venv with numpy 2.0.2.

## Decisions the plan did not cover
1. Lock date stayed 2026-11-04 (real commit day). 2. Permutation changed from iid random start days to a calendar shift after the first harness run showed iid was too conservative (0 of 60 false claims where about 3 expected), and the baseline pool starts in 1950 (1928-49 only warms up the volatility terciles). 3. Self-test plant moved from +10 to +15 (Amendment 1, above). 4. The "8 comparisons" are 4 flags (lost 20+ House seats, no House majority, no Senate majority, divided government) x 2 windows. 5. The 3 Nov bar is excluded.

## Audit
Pending: a fresh-context audit has not been run. Not in the settled index until it is clean.
