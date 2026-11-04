# PREREG -- presidential elections and the S&P 500 (two parts)

**Locked 2026-11-04** (the real commit day), before any return in this study is computed. Sibling of `research/election_cycle` (midterms); same method, same S&P file, same rules. Offline; ships nothing until a clean audit. Market data only (no Pulse, accounts or positions).

## Questions
- **A. After the vote:** does the S&P 500 do anything unusual in the 12 months after a US presidential election (Election Day, 1952-2024, n = 19) versus an ordinary volatility-matched 12 months?
- **B. Primary season:** does the S&P 500 behave differently from January to June of a presidential year (the primary season) than in other years (1950-2024)? Nomination dates are NOT used: Jan-Jun is a fixed calendar proxy, so nothing is hand-entered for B's tests.

## Data
S&P 500 price index, daily closes, Yahoo `^GSPC` (no dividends), the same file as `election_cycle` (`../election_cycle/data/spx_yahoo.json`, 24,827 bars to 2026-11-02). Saturday bars before 1952-06-01 dropped. 1928-49 is volatility warm-up only. Presidential Election Day = Tuesday after the first Monday in November (computed). Cross-checked: the close before each of the 19 elections against TradingView SP:SPX (narrow calls); any gap over 0.1% is listed. IB is not used (the election_cycle IB call errored and these dates are all before 2021 except 2024; 2024 is covered by TradingView).

## Method (unchanged from election_cycle, incl. its Amendment 1)
- Event return = 252-trading-day return from the close before Election Day. Baseline = mean forward-252 return of start days in the same expanding 20-day-volatility tercile, pool starting 1950, excluding start days within 21 bars of any of the 19 presidential Election Days.
- Test = circular shift of the whole 19-date calendar by a common offset inside 1950-2025 (every offset used); 95% interval from a moving-block bootstrap (block 252) plus event resampling. A **claim** needs p < 0.05 AND an interval that excludes 0.
- B: season return = last close of January to last close of June, for each year 1950-2024. Presidential years (19) versus all other years (56), label permutation (10,000), two-sided.
- A null at n = 19 means "not distinguishable", not "no effect".

## Pre-registered tests (the only ones that count)
Primary A: 12-month excess after Election Day. Primary B: Jan-Jun return, presidential years vs others.
Secondary (4): A at +21, +63, +126 bars (excess); B: Jul-Oct return (last close of June to last close of October), presidential vs other years.
Everything else below is **exploratory** and descriptive.

## Exploratory (hand-entered public facts, not fetched; descriptive, not tested)
By winner's party (D/R); party change vs held (incumbent party lost or kept the White House); incumbent president running vs open seat (2024 counted as open: the incumbent withdrew); 6-month run-up going in (126 bars to the close before Election Day: Up >= +3%, Down <= -3%, else Flat); reaction day (first bar after Election Day vs the bar before). B: Jan-Jun return split by incumbent running vs open seat, and by party change. About 8 groupings: at 5%, expect roughly 0.4 false positives. Also reported: Jan-Jun max drawdown.

## Self-test (repo standard)
`check_harness.py` must print SELFTEST OK before `run.py` counts. A: plant +15 points on the real 19-date calendar shifted to random ordinary dates, found in >= 6 of 8; no effect invented from noise in more than 2 of 20 (these are the election_cycle numbers' standard; if the +15 bar fails the harness is tuned BEFORE any real return is computed and the change recorded as an amendment). B: plant +10 points on 19 random years' Jan-Jun return, same bar. Both report the smallest effect detectable at 80% power.

## Honest prior
Likely null for both. The 4-year "presidential cycle" folklore (strong year 3, weak year 2) is well known; this is a single narrow slice of it with 19 events. A thin result will be described as folklore on known history, not out of sample.

## Live case
None to track: the next presidential election is 2028. The 2026 midterm study carries the live case.
