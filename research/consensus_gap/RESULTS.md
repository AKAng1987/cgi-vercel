# Does the consensus gap tell us whether the growth or inflation axis will flip?

Run 2026-10-30. Offline only; nothing here is deployed. Reproduce: `python3 fetch_data.py` (AWS CLI, read-only), then with
`api/.venv/bin/python`: `check_harness.py` (must print SELFTEST OK), `run.py`, `sensitivity.py`. Release data is
`data/releases.json` (TradingView economic calendar, fetched once on 2026-10-30; the connector only works inside a Claude
session, so it cannot be refetched by script).

## Verdict

**Growth axis: yes, the consensus carries real information about the GDP flip, and it is large.** On the 54 advance GDP
prints since 2013, when the consensus implied a flip (the forecast on the other side of the previous print from the current
state) the growth axis flipped **24 of 27** times (89%); when it implied no flip it flipped **4 of 27** (15%). The base rate
for growth is about 52% (28 flips in 54). Walk-forward on 34 scored releases the Brier score fell from 0.259 (base rate by
state) to 0.157; the paired block-bootstrap 95% CI of the difference is [-0.154, -0.051], entirely below zero. It held in all
10 distinct variants of the sensitivity grid (training minimum 10 to 30, with or without the excluded rows; the settle window of 1, 3 or 5 days makes no difference because every matched flip is stamped on the release day).

**Why this is not a surprise and not a forecast of markets.** The growth axis is defined as the sign of (new GDP print minus
previous print) (`update_grid_model.py`). The consensus is the market's estimate of the new print, so (forecast minus previous)
is an estimate of that same sign. The study confirms the market's estimate is right on the sign 87% of the time; it does not say
anything about what prices do afterwards. It is the "market-side" figure CGI's growth row has lacked (the existing growth
"market" number is a driver table that scored no better than the base rate).

**Inflation axis: the direction is the same but the sample is too thin to claim.** Headline CPI YoY: the consensus implied a
flip 14 times and 8 flipped (57%) against 4 of 147 (3%) when it did not; but there are only 12 flips in 161 releases and the
walk-forward Brier gain (-0.0074, CI [-0.0222, +0.0066]) includes zero. Core PCE YoY: 1 flip in 120 releases: untestable.

**One exploratory comparison also crossed zero** (core CPI YoY, Brier gain 0.0010 on a 0.081 base, CI [-0.0029, -0.0002]):
the effect is a tenth of one percent of the score, it is exploratory, and with 8 comparisons run about 0.4 false claims are
expected by chance. It is recorded, not claimed.

## What was tested

Pre-registered before `run.py` was run (also in its docstring):
- PRIMARY: growth axis, advance GDP, one predictor, the oriented gap g (positive = "the consensus already implies a flip":
  axis up: previous - forecast; axis down: forecast - previous). Logistic on g (ridge), expanding walk-forward, minimum 20
  releases to train, Brier against the base flip rate of the current state, 95% moving-block bootstrap (block 3).
- SECONDARY: inflation axis with headline CPI YoY (forecast - previous), and with core PCE YoY.
- EXPLORATORY (counted): CPI MoM, core CPI YoY, core CPI MoM, core PCE MoM, GDP second estimates, and the mechanical sign
  rule and the flip-rate bins (descriptive, whole-sample).

## Data

| Series | Releases used | First | Last | Flips |
|---|---|---|---|---|
| GDP advance (first print) | 54 | 2013-04-26 | 2026-07-30 | 28 |
| CPI YoY | 161 | 2013-03-15 | 2026-09-11 | 12 |
| Core PCE YoY | 120 | 2014-10-31 | 2026-09-30 | 1 |

- Forecast, previous and actual per release from the calendar; the calendar's "previous" is the value known on the day (so it
  carries the revision then in force). 2010-2012 returned nothing, so history starts in 2013, not 2003 as the connector says.
- Axis state and flip dates from `cmon-stage-backend-model-history` (`grid_US`: 145 rows, 2008-03-27 to 2026-09-30). The grid
  model stamps a flip on the release date itself: all 29 matched advance-GDP flips were stamped on day 0, so the 3-day settle
  window used by `markov_data.py` is not what drives the match.
- GDP selection fixed before the run: advance rows only; excluded the three 2013 rows titled "Adv" that are third estimates
  and the 2025-10-30 row (the print was delayed by the shutdown); included the delayed first prints of 2019-02-28 and
  2025-12-23. Releases after 2026-10-01 are excluded (the model history dedupes unchanged days, so a recent release with no
  flip row cannot be told from one not yet processed): the 29 Oct 2026 GDP print is therefore not in the sample.
- Missing forecasts: headline PCE (86 of 143) and 2013's first GDP row; not used.

## Harness

`check_harness.py`: planted strong effect found 8 of 8 at n=60 and 8 of 8 at n=45; noise falsely claimed 0 of 20 (n=60) and
1 of 20 (n=45); a moderate effect (signal 1.0) found 6 of 8 at n=60. SELFTEST OK.

## Caveats

- **Advance-day flips can reverse.** The growth axis also flips on revisions: 95 growth flips in the model history, 29 on advance
  prints; second estimates flipped 20 of 52 times. A consensus-implied advance flip is a statement about the first print only.
- **The logistic understates the effect.** The cold audit's simpler benchmark (flip when g > 0, with training-bin rates as
  probabilities, same walk-forward rows) scored Brier 0.113 against 0.157 for the logit and 0.259 for the base rate. The
  conclusion (consensus gap beats the base rate) is the same and is conservative as reported.
- **Ties.** 3 releases have g = 0 (forecast equal to previous) and fall in the "implies no flip" bin; one of them flipped.
- **Pre-registration cannot be verified from file dates** (no version control at the time; the docstring in `run.py` states the
  plan and the run came after it). The audit re-ran the primary under eight other defensible selections (drop the delayed prints,
  drop 2020, drop 2020-21, 2016 onward, pre-2020 only, keep all advance rows): every one stayed BETTER with CIs below zero.

- 34 scored GDP releases and 17 flips: the interval is wide even though it excludes zero. One more quarter of data moves it.
- Survivor of one data vendor: all forecasts come from the TradingView calendar; the 23 CPI rows of 2013 were transcribed by
  hand by the fetching agent (spot-checked rows match).
- The oriented gap uses the calendar's "previous"; the model's own previous (stored original) can differ after revisions, which
  would turn a few "implied flips" into real non-flips. That is part of the 13% sign misses.
- It says nothing about markets. A consensus-implied flip is not a trade signal and not a sizing input.
- Inflation: only 12 flips in 13 years, so no claim either way.

## What this means

Where a pass would go (per the pre-registration): CGI, as a descriptive column **"consensus-implied"** on the growth (and, with
its thin-sample label, inflation) release rows, labelled "what the consensus implies for the sign; not a forecast of markets".
Never a rule or a size. The brain should now believe: for GDP advance prints the consensus gap is a strong, mechanical read on
whether the growth axis flips (about 89% vs 15%), far better than CGI's own base rate; it adds nothing yet that we can show for
the inflation axis. Items not concluded: GDP second estimates (32 scored, CI includes zero) and the market-return effect of a
flip (not tested here).

## Audit

Cold read by a separate Claude with no memory of the study (2026-10-30), reproducing every number. Lookahead: none found
(`state_before` strictly before the release; the walk-forward fits only on earlier releases; the scaling uses training rows only).
Vintage: none found (the calendar's "previous" equals the model's comparator; flip = sign(actual - previous) disagreeing with the
state held on 53 of 54 rows, the exception being the 2013 benchmark revision). Selection: result does not depend on it (table
above). Tests tried vs reported: honest (8 comparisons, 3 pre-registered). Method: sound; the logit is conservative. Harness: it
shares the `compare` code path with `run.py`; the first version did not exercise `build_rows`/`state_before`, now added; the
noise check at n=45 cannot tell a 5% from a ~15% false-positive rate. **Unresolved findings: none.** Nice-to-haves applied: the
variant count, the sign-rule benchmark, tie handling, the revision-reversal caveat, the pre-registration note, the end-to-end test.
