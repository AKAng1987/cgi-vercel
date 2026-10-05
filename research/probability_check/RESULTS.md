# Probability check: are CGI's published flip probabilities calibrated, and do they beat the base rate?

Run 2026-10-05. Offline only; nothing here is deployed. Reproduce: `check_harness.py` (must print SELFTEST OK) then `run.py`.
Reuses the walk-forward windows and publication-lagged readings from `research/latent_state/` (same windows, same lags).
Each estimator is fitted only on windows already resolved, then asked for the next one. Lower Brier is better; the
interval is a paired bootstrap of the per-window difference vs the base rate B0.

## Verdict

| Axis | "Today" figure (driver table) vs base rate | Verdict |
|---|---|---|
| Liquidity | Brier 0.132 vs 0.149, diff -0.017 [-0.026, -0.008] | **Better, and about calibrated** (slope 1.25, CI 0.73-2.09). If anything it under-states the top third (said 18%, happened 40%). |
| Credit | 0.215 vs 0.233, diff -0.018 [-0.034, -0.002] | Better on 49 windows / 17 flips, but the slope CI is huge (-0.3 to 4.7). Treat as unproven. |
| Growth | 0.2456 vs 0.2444, diff +0.001 [-0.003, +0.005] | **No better than the base rate.** |
| Inflation | 0.2211 vs 0.2241, diff -0.003 [-0.008, +0.002] | **No clear difference.** |

1. **Growth and inflation: the "today" number is the base rate with decoration.** Shrinking it toward the base rate
   (lambda 0.25/0.5/0.75) changes nothing measurable, so there is nothing to rescue.
2. **Liquidity is the one real result**, with two caveats already in `latent_state/RESULTS.md`: its drivers include the
   Fed-target spread (nearly the futures-implied probability), and the driver lists were chosen on this same history.
3. **Splitting the base rate by state is mostly noise, except liquidity.** Flip rates by state: liquidity 24% vs 8%
   (a real gap); credit 38/32, growth 39/43, inflation 33/30. A single pooled rate scores the same as the per-state rate
   (Bp vs B0, no clear difference on any axis). Growth and inflation per-state rates have negative calibration slopes.
4. **Time in regime: no clear effect.** H1 (flip rate by how long the axis has sat in its state) never beats the base rate.
   Power note: the harness finds a *strong* planted effect 8/8 but a *moderate* one (Brier gain ~0.012) only 1/8 at this
   sample size, so "no clear effect" means "none large enough to see", not "none".
5. **Per-release scaling is right.** Published base P(flip) vs the study's window flip rate for the same state:
   inflation 30.5% vs 29.9%, growth 45.1% vs 42.7%, credit 32.0% vs 31.9%, liquidity 26.3% vs 23.9%.
6. **GDP-by-estimate cannot be tested**: the live table has 1 release since tracking began (the 2026-09-30 flip), so it
   falls back to the pooled figure everywhere. It will become testable as live events accumulate.
7. **The live scorecard already exists** (Event log on /cgi: pre-registered probabilities, outcomes, running Brier,
   "history vs market"). One thing to know when reading it: for credit, growth and inflation its "market" column is the
   same in-sample driver table (labelled "Drivers"); only liquidity's is a real market price (fed funds futures).

## Caveats

Small n (17-66 flips per axis), several comparisons per axis uncorrected, driver selection in-sample (so B1 is flattered),
windows approximate real release dates, and revisions are not removed. The verdict, if anything, is generous.

## What this suggests (needs a decision before anything changes)

- Growth and inflation "today" figures: label them "no better than the base rate out of sample" or dim them.
- Keep the liquidity figure; keep its in-sample caveat.
- Nothing else to add: no hazard/duration term, no shrinkage, no new model.
