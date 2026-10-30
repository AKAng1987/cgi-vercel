# Does the hyperscalers' capex show up in their suppliers' revenue, and does knowing it help forecast that revenue?

Run 2026-10-30 (second run; the first was wrong, see below). Offline only; nothing here is deployed except a descriptive chart.
Reproduce: build the SEC snapshot with `api/.venv/bin/python ~/market-dashboard/scripts/capex_build.py --out research/capex_flow/data/snapshot.json`
(about 8 minutes), then `check_harness.py` (must print SELFTEST OK) and `run.py` with `api/.venv/bin/python`.

## Verdict

**Descriptively yes, as a forecast no.** The five hyperscalers' capex growth and their suppliers' revenue growth move together: the
12 AI suppliers' revenue growth correlates +0.62 with spender capex growth in the same quarter and +0.58 with it one quarter earlier,
fading to +0.13 at four quarters (chips +0.61 and +0.43; data-centre equipment +0.44 and +0.37; power only +0.27 at one quarter).
That is a whole-sample, overlapping-quarters description, not a test.

**Out of sample, knowing the spenders' capex did not improve a forecast of next quarter's supplier revenue growth.** Primary (AI
suppliers pooled): the candidate's squared error was 9.6% HIGHER than a plain AR(1), CI of the paired difference [-130.8, +41.5],
17 forecast quarters. Industrials +5.7% [-3.2, +6.5], Utilities +0.6% [-8.1, +8.3], Materials -2.3% [-9.1, +5.5]. None of 9
comparisons helped (about 0.2 false claims expected). **This is "not shown", not "no effect"**: at the real sample size (about 30
quarters, 14-24 scored) the harness finds an effect of 0.3 per point of capex growth only about 9 times in 20.

**A first run said otherwise and was wrong.** It reported Utilities as "helps" (+12.6%, CI [+1.5, +16.0]). A cold audit showed it was
not robust (it vanished with first-differenced capex, with detrending, and when the single best quarter was dropped) and that the
revenue dates for one utility that switched tags (AWK) were dated by tag order, not by first filing, so some training targets were
used before they were on file. After fixing the dating (earliest filing across tags, and a training filter on the filing DATE of each
row's target, not the quarter label) the Utilities result is +0.6%. The pre-registered robustness rule (a "helps" counts only if it
also holds with differenced capex, an AR(2) baseline, minimum training of 12 and 20 quarters and without the best quarter) was added
before the rerun; with no claim left it had nothing to test.

## What was tested

Pre-registered (docstring of `run.py`, written before the first run; the robustness rule added before the second):
- PRIMARY: the 12 AI suppliers (power: VST CEG NRG ETN; chips: NVDA AMD AVGO MU; data-centre equipment: VRT ANET DLR SMCI) pooled.
- SECONDARY: Industrials, Utilities, Materials (whole sectors, today's members, spenders excluded).
- EXPLORATORY (counted): the three AI layers separately and the primary at one and two quarters' lag.
- Method: forecast revenue growth (year on year, summed, first reported) at q+1 from an AR(1) baseline vs the baseline plus the five
  spenders' capex growth at q; expanding walk-forward, first forecast after 16 resolved quarters, a training row used only if its
  target was on file by the forecast's information date; paired squared error with a block-3 bootstrap.
- Not tested: the suppliers' share prices (single names are not stored; the index version, `capex_state`, was null).

## Data and caveats

- SEC filings via `sec_xbrl.cash_quarters_first` (first-reported values and first-filed dates), 500 current S&P 500 members; AMZN,
  MSFT, GOOGL, META, ORCL as spenders. Revenue verified against TradingView for Micron (41.5bn and 54.2bn in the last two quarters).
- **Survivorship**: today's members and today's layer lists applied to all history.
- **Twelve names, really two**: the AI pool's 2026Q2 growth (+97%) is NVDA (+$49.5bn) and MU (+$32.2bn, +346%) with AVGO; nothing
  else moves it. Acquisitions show up as growth (NRG +312% in 2021, VST +107% in 2018 and +233% in 2021Q1); no organic adjustment.
- Year-on-year growth overlaps three quarters between neighbours, so the effective sample is smaller than the quarter count, and
  both series trend up in the AI years, which is why a level comparison can flatter a shared trend.
- n = 17 forecasts for the primary (the AI pool needs 75% of its names to have both quarters, which is true only from 2017).

## Harness

Unit checks on hand-built groups (growth arithmetic, the 75% coverage floor, the date-based training filter). Planted strong effect
found 8 of 8; noise falsely claimed 0 of 20; moderate (0.15) found 2 of 8 at 60 quarters; at the real size an effect of 0.3 is found
9 of 20. SELFTEST OK.

## What this means

The Fundamentals page shows the two growth rates side by side as a description of whether the spending is arriving as suppliers'
revenue, with this caveat in the caption. It is not a forecast, not a timing tool and not an input to any regime. The brain should
believe: capex and supplier revenue rise together (strongest for chips, same or next quarter); capex growth as known did not predict
next quarter's supplier revenue growth beyond the suppliers' own trend, with too little data to rule out a moderate link.

## Audit

One cold audit (2026-10-30), of the first run. Findings: the training filter compared quarter labels, not filing dates (1 of 17 AI
forecasts and 5 of 22 Utilities forecasts used a target filed after the information date); AWK tag-switch dating; the Utilities
"helps" not robust; harness sample size; write-up requirements (all listed above). Everything it flagged was fixed or stated before
this run. **This run (second) was not re-audited by a separate reader**: its numbers were checked by me against the first run
(0 of 9 claims, the same sign on the primary), and the dating fix also moved `capex_state` by about a point (verdict unchanged).
