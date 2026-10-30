# Does S&P 500 capex growth, or the funding gap, add anything to regime + 20-day volatility for the next 1-3 months?

Run 2026-10-30. Offline only; nothing here is deployed. Reproduce: `python3 fetch_data.py` (AWS CLI, read-only), build the SEC
snapshot with `api/.venv/bin/python ~/market-dashboard/scripts/capex_build.py --out research/capex_state/data/snapshot.json`
(about 8 minutes, SEC only), then `check_harness.py` (must print SELFTEST OK) and `run.py` with `api/.venv/bin/python`.

## Verdict

**No. Out of sample, neither capex growth, nor its acceleration, nor the funding gap improved a forecast of the S&P 500's next
1-month or 3-month return, 3-month worst drawdown, or 3-month volatility beyond regime + 20-day volatility. 0 of 12 comparisons
helped; the candidate was worse than the baseline in all 12, and clearly worse (CI wholly below zero) in 4.** Primary (capex growth
tercile -> 3-month worst drawdown): the candidate's squared error was 5.6% higher, CI of the paired difference [-5.3, +0.6] (negative
= worse). Secondary (funding gap tercile -> 3-month return): 6.2% higher, CI [-10.2, +2.3]. With 12 comparisons in this run
about 0.6 false claims were expected (0.3 given the one-sided rule); none was made.

**There were four runs, and the first three had date bugs.** Run 1 dated each quarter by the date of the LATEST filing that repeats it
(next year's 10-Q carries it as a comparative), so the features were about 15 months stale, and the "funding gap" came from a
median of 13 companies. A cold audit found this. Run 2 used each quarter's FIRST filing date and the value as first
reported, requires 80% coverage for both quarters used in the acceleration and 150 companies for the funding gap. The reported
quarter is now a median 92 days old at the decision date (p10 61, p90 123), the first-filing lag is a median 34 days for Q1-Q3 and
52 for Q4, and a growth figure exists for all 168 months. A second cold audit found run 2 still dated operating cash flow by the capex filing date (3.4% of quarters, mostly a year
late); run 3 gated it on its own first-filed date. A third audit (of the capex_flow study) found that a company that switched XBRL tags (AWK)
was dated by tag order, not by first filing; run 4 (this one, 2026-10-30) takes the earliest filing across tags. Runs 1 to 3 also reached
0 of 12 (11, 12 and 12 worse); 48 comparisons were run in all. Run 1's descriptive hint (low capex growth followed by lower returns, CI [-7.8, -1.1]) reversed sign in run 2 (bottom tercile
+2.6 points, CI [-0.7, +5.9] in runs 2 and 3): it was an artefact of stale dates, which is why the tercile tables below are not read as a signal.

## What was tested

Pre-registered before `run.py` was run (also in its docstring):
- PRIMARY: `b_g1` (aggregate YoY capex growth as known on the day, expanding terciles) -> 3-month max drawdown.
- SECONDARY: `b_gap` (trailing capex / trailing operating cash flow, as known) -> 3-month return.
- EXPLORATORY (counted): the acceleration feature on all four targets and each other feature-target pair.
- Method as `research/erp_state`: monthly decisions at month end; baseline OLS on log 20-day vol, compass and grid quadrant
  dummies; candidate adds bottom/top tercile dummies; refit each month on resolved months only; paired squared error; moving-block
  bootstrap (block 3). Deviations fixed in advance because the history is shorter: terciles after 24 months of feature history
  (36 in erp_state), first out-of-sample month after 24 resolved months (30).

## Data

- Capex and operating cash flow per company per calendar quarter from SEC filings as FIRST REPORTED
  (`sec_xbrl.cash_quarters_first`: for each year-to-date window the value from its earliest filing, differenced; quarter dated by
  the later of its two windows' first filings), 2011Q1 onward, 500 current S&P 500 members (469 report capex). Decision months
  2012-09 to 2026-08 (168); a growth figure exists for every month; median matched coverage of prior-year capex 0.97. The 150-company floor on the funding gap
  never binds (at least 236 companies qualify in every month); some off-calendar fiscal years (e.g. a November quarter labelled
  calendar Q4) are first-filed before their calendar quarter ends, which is not lookahead because the gate is the filing date.
- A figure counts as known only if first filed 5 or more days before the decision date; a quarter counts as reported when filings
  on file match at least 80% of last year's capex for that quarter (and for the prior quarter in the acceleration).
- SPX daily closes 1927-12-30 to 2026-10-28; compass 72 rows and grid 145 rows of model history.

## Harness

Feature code checked on hand-built companies (coverage rule, 5-day filing lag, the 80% threshold, YoY arithmetic, first-filing dates
against a later re-filing), and the first-filing reader against a restated comparative (`scripts/check_capex.py`, 50 checks). Planted strong
effect found 8 of 8; noise falsely claimed 0 of 20; a MODERATE planted effect (0.6 of the noise sd) found only 4 of 8 at 150
months, so this study could not see a modest effect either way. SELFTEST OK.

## Caveats

- ~30 independent quarters; the answer is "no evidence in 14 years", not "no effect".
- Survivorship: today's members applied to 2012 onward; the sample is of companies that survived and stayed in the index.
- Values are as first reported, so later restatements are not used (the right direction for a point-in-time test); the compass and
  grid history are taken as they were stamped at the time. Operating cash flow uses its own first-filed dates (`ofiled1`, from run 3).
- Earlier runs are kept for the record: `results_run1_stale_filing_dates.json`, `results_run2_ocf_capex_dates.json` (and the matching snapshots in `data/`).
- Only the S&P 500 index outcomes were tested. The largest spenders' relative performance and sector breadth were not tested
  (they were listed as possible exploratory items in the plan and not built).

## What this means

CGI keeps the capex view on Fundamentals as context only ("what was spent", labelled not a forecast). Nothing here goes into a
rule, a size or the regime. The brain should believe: capex growth as reported does not improve a next-quarter read on the index
over regime + 20-day volatility; it is a description of the AI build-out and its funding, not a timing tool.

## Audit

Two cold audits (2026-10-30), by readers with no memory of the build. Audit 1 (run 1): stale filing dates (blocking), a degenerate
funding gap (median 13 companies), no coverage floor on the prior quarter, a wrong "6 of 12" count and a wrong restatement caveat;
confirmed the 5-day lag, expanding terciles, resolved-months-only training, entry and target timing, arithmetic recomputed by hand,
and that "candidate worse" is overfitting (in-sample gains +0.4% to +10.6%); its own rerun with timely dates and with one
continuous feature also gave 0 of 12. Audit 2 (run 2): confirmed `filed1` is the first filing (median lag 34 days Q1-Q3, 52 Q4; 40
companies re-derived from live SEC data with 0 differences; AAPL, MSFT, AMZN, NVDA dates match), g1/acc/gap recomputed exactly on four
dates, the 150 floor and the 80% floors do not change the verdict (floors 0, 100, 150, 250 and no g0 floor: 0 helps in all); found
one new bug, operating cash flow gated by the capex filing date (3.4% of quarters), fixed in run 3 and the auditor's predicted
numbers (secondary -6.6% [-8.6, +0.5], 5 clearly worse) were reproduced. **No unresolved finding.** Not done: the continuous-feature
variant is not in `run.py` (the audit's version also gave 0 of 12); `cash_quarters_first` takes the first tag in its chain rather
than the earliest-filed one, which can only make a date later, never earlier.
