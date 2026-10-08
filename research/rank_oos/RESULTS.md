# Do the regime best/worst-20 lists predict the next episode?

Run 2026-10-08. Offline only; nothing here is deployed. Reproduce: `check_harness.py` (must print SELFTEST OK) then
`run.py`. For every past episode of every C x G regime, instruments are ranked using ONLY earlier episodes of that
regime; the score is that episode's top-20 minus bottom-20 return. Episodes are the unit of evidence
(bootstrapped over episodes).

## Verdict

**No. Out of sample, the best/worst-20 ranking is a coin flip.** 166 episodes scored:

| Ranking | Top-20 minus bottom-20, next episode | 95% CI | Episodes where top beat bottom | Rank correlation |
|---|---|---|---|---|
| Average return (RAW) | +0.36 pts | [−0.50, +1.22] | 48% | +0.015 [−0.025, +0.052] |
| Shrunk average (SHRUNK) | +0.34 pts | [−0.51, +1.17] | 49% | +0.014 [−0.026, +0.052] |
| High/low "edge" ratio (page today) | +0.28 pts | [−0.48, +1.02] | 53% | +0.012 [−0.025, +0.048] |

Shrinking small samples changes nothing (SHRUNK − RAW −0.02 [−0.30, +0.24]); the page's edge ratio is no better or
worse than plain averages (RAW − EDGE +0.08 [−0.39, +0.54]).

This agrees with what CGI already says in its caveats (64% of return variance is the regime itself, 2.5% the
instrument): the regime matters; which instrument tops the in-sample list within it does not carry forward.

## Harness

Finds a planted persistent per-instrument edge 8/8; claims an edge in pure noise 0/20 -- so the null above is not a
blind test.

## What this means for the product (needs the user's decision before any change)

- The BACKTEST page, the TradingView "CGI · now" list and the CTS post present the best/worst 20 as what did best
  and worst in this regime historically. That is true, but it should not read as a forecast. An honest line --
  "historical, in-sample; has not predicted the next episode" -- is the proportionate change.
- No model to add: shrinkage did not help.
