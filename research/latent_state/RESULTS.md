# Latent-state layer (Kalman factor -> P(flip)): walk-forward results

Run 2026-10-04. Offline only; nothing here is deployed. Reproduce:
`build_dataset.py` -> `selftest.py` -> `run.py`.

## Verdict

**Do not ship it as a P(flip).** On three of four axes it does not beat the plain
Markov base rate out of sample. On the fourth (liquidity) it beats the base rate
but not, with confidence, the equal-weight driver table CGI already has, and it
does so with 12 fitted numbers against 21 flips. "It did not beat the baseline"
was the stated acceptable outcome; this is that outcome.

## Setup

Windows are the production definition (`axis_drivers`: fixed-length release-cadence
windows, "flip" = the axis changed inside the window). Each estimator is fitted only
on windows whose outcome was already known, then asked for the next one (expanding
window, refit every step). Lower is better.

- **B0** base rate by state (what `markov_data` uses)
- **B1** the production idea (equal-weight driver terciles), refitted walk-forward.
  The live table is computed over ALL windows, i.e. in-sample.
- **M1** one-factor Kalman filter over the axis's drivers -> 4-parameter logistic.
  Parameters = K loadings + 1 persistence + 4 logistic (no free noise variances).

Harness validity (`selftest.py`): recovers a hidden factor (|corr| 0.93, 25% of
readings missing); detects a planted signal in 8/8 runs; claims a significant win
on pure noise in 0/20 runs.

## Scores (Brier, publication-lagged readings)

| axis | windows | scored | flips | params | B0 | B1 | M1 | M1 - B0 (95% CI) |
|---|---|---|---|---|---|---|---|---|
| liquidity | 180 | 120 | 21 | 12 | 0.149 | 0.132 | **0.118** | -0.030 [-0.062, -0.005] |
| credit | 89 | 49 | 17 | 13 | 0.233 | 0.215 | 0.239 | +0.006 [-0.018, +0.028] |
| growth | 225 | 165 | 66 | 16 | 0.244 | 0.246 | 0.244 | -0.0004 [-0.006, +0.005] |
| inflation | 225 | 165 | 54 | 19 | 0.224 | 0.221 | 0.224 | -0.0003 [-0.007, +0.007] |

M1 vs B1 (the existing table): liquidity -0.014 [-0.041, +0.009]; credit +0.023
[+0.005, +0.042] (M1 worse); growth and inflation indistinguishable.

Liquidity is stable across the training cutoff (40/60/80/100 windows): always better
than B0 (CI excludes zero), never clearly better than B1.

## The finding that matters more than the model: leakage

The same models scored on the production convention (value STAMPED on or before the
window start, which for monthly data is weeks before it was published):

| axis | M1 Brier, lagged | M1 Brier, leaky |
|---|---|---|
| inflation | 0.2238 | **0.2046** |
| growth | 0.2440 | 0.2404 |
| liquidity | 0.1183 | 0.1217 |

Inflation shows a ~9% apparent improvement that **disappears entirely** once readings
are restricted to what was published. The production table (B1) shows the same effect
on inflation (0.2211 lagged -> 0.2076 leaky). `axis_drivers` uses stamped dates, so
its `conditioned_p_flip` for inflation (and growth) is very likely overstated, and
that number is displayed as the "market" estimate beside the Markov P(flip) in
`markov_data._market_from_drivers`. This is worth auditing independently of the filter.

## What this cannot rule out (and why the verdict is, if anything, generous)

1. **Driver selection is in-sample.** The lists in `axis_drivers.DRIVERS` were chosen
   because they separated flips on this same history ("added ... at the same 26pp
   spread", "did not separate -- dropped"). Walk-forward fitting cannot undo that, so
   every score here is optimistic. B1 is flattered too, which is why credit's B1
   "win" over B0 should not be trusted.
2. **Revisions.** price-history holds series as last revised, not as first published.
   Growth and inflation inputs (orders, claims, CPI components) are revised; the
   publication lag removes look-ahead on timing, not on revisions. Liquidity drivers
   are mostly market series (yields, spreads), which are not revised.
3. **Liquidity's drivers contain the answer.** "3m bill - Fed target" and "2y - Fed
   target" are the market's own pricing of the next move. Beating a base rate with
   them is expected and is close to restating the FedWatch-style market probability.
4. **Small n, many comparisons.** 17-66 flips per axis; four axes and several
   comparisons each, uncorrected. Only liquidity vs B0 clears the bar, and not by a
   margin that survives a multiple-comparison correction with confidence.
5. **Windows are an approximation.** Fixed-length windows, not actual release dates.

## What a filter could still give that Brier does not score

A continuous distance-to-flip, and honest ragged-edge handling. Neither was tested;
neither justifies shipping a probability that did not beat the baseline. If wanted,
the way to get them without a P(flip) is to display the filtered factor itself, with
its variance, labelled as a descriptive measure and not a forecast.
