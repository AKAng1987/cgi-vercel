# Peer overshoot reversion ("buy what everyone else is selling"), daily, CGI universe

Run 2026-10-08. Offline only; nothing deployed. Reproduce: `check_harness.py` (SELFTEST OK) then `run.py`.
154 instruments in 9 peer groups (crypto excluded; 8 thin/stale series dropped), 5,463 trading days from 2005.
Overshoot = an instrument's k-day return minus its peer group's (itself excluded), scaled by its own residual vol;
event = beyond 2 sigma; "fade" = bet it comes back over the next h days. Net = after 10bp per round trip.
Days are block-bootstrapped (events on the same day are not independent).

## Verdict

**There is reversion, but almost none of it survives costs, and what survives is shrinking.**

| Overshoot over | Hold | Gross per event | Net per event (95% CI) | 2005-15 net | 2016-26 net |
|---|---|---|---|---|---|
| 1 day | 5 days | +0.18% | **+0.08% [+0.03, +0.15]** | +0.14% | +0.03% |
| 1 day | 10 days | +0.19% | **+0.09% [+0.01, +0.17]** | +0.12% | +0.07% |
| 3 days | 5 days | +0.13% | +0.03% [-0.04, +0.11] | +0.13% | **-0.06%** |
| 5 days | 5 days | +0.17% | +0.07% [-0.01, +0.16] | +0.16% | -0.01% |
| 5 days | 10 days | +0.12% | +0.02% [-0.10, +0.15] | +0.15% | **-0.10%** |

1. **Only the one-day overshoot, held a week or two, clears costs over the full sample**, at ~0.1% per event, and
   it has decayed since 2016. That is the "signals erode in 5-10 years" line from the video, measured.
2. **Since 2016, multi-day moves against peers have tended to CONTINUE, not reverse** (3-5 day overshoots, net
   negative to fade). Mild support for buying strength rather than fading it -- consistent with breakout entries.
3. **Regime splits are noise.** Signs disagree across neighbouring regimes, several cells are periods before the
   grid model existed, and the few that pass a false-discovery check do so barely. Not a finding.

## For the trader

At ~0.1% per event, this is not a strategy at $600 risk per trade. The usable reading is about entry timing:
a single sharp day against peers tends to give a little back within a week (a pullback entry slightly beats
chasing that day), while a multi-day move against peers is more likely to keep going.

## Caveats

Daily closes, not intraday; broad peer groups (69 sector ETFs share one group); no borrow costs for the short side;
model-history regime labels used as of each date. Medallion's version ran on 5-minute data at enormous breadth --
this measures what is left at a daily, manual scale.
