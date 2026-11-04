# presidential_cycle -- RESULTS

Built 2026-11-04. Pre-registered in `PREREG.md` (lock commit 839cfe4 holds PREREG.md only; the harness, facts and TradingView data were committed next, `run.py` and `results.json` last). Offline; ships nothing. Calendar context only, never a size or entry rule.

## Verdict
**Neither part shows anything distinguishable.** n = 19 presidential elections (1952-2024), so a null means "can't tell", not "no effect". A: the 12 months after Election Day averaged +9.0% against a volatility-matched baseline of +9.3% (excess **-0.3 points**, p = 0.94, 95% interval -8.1 to +7.8). B: January-June of presidential years returned +3.0% against +3.1% in other years (p = 0.99). All 4 secondary tests are also null. Zero claims out of 8 pre-registered tests.

## Self-test (SELFTEST OK before run.py counted)
- A: planted +15 points found **8/8**; noise falsely claimed **2/20** (the allowed maximum); smallest detectable effect at 80% power **+15 points** (+12 is 78%).
- B: planted +10 points found **8/8**; noise falsely claimed **1/20**; smallest detectable effect at 80% power **+7 points**.
- Cross-check: the close before each of the 19 elections plus the 300 most recent bars (the last 300 reused from `election_cycle`, same price file) compared with TradingView SP:SPX: 319 closes, **0 gaps over 0.1%** (2024: Yahoo 5712.69, TradingView 5712.68). IB was not used (see PREREG).

## Pre-registered tests
| Test | Result | p | 95% interval |
|---|---|---|---|
| A primary: 12-month excess after Election Day | -0.3 pts | 0.935 | -8.1 to +7.8 |
| A +21 bars | +1.0 pts | 0.319 | -1.2 to +3.2 |
| A +63 bars | +1.5 pts | 0.410 | -1.9 to +4.6 |
| A +126 bars | +0.7 pts | 0.733 | -3.6 to +5.1 |
| B primary: Jan-Jun return, presidential vs other years | 3.0% vs 3.1% (-0.0 pts) | 0.993 | permutation test |
| B Jul-Oct return | 0.9% vs 1.6% (-0.6 pts) | 0.766 | |
| B Jan-Jun max drawdown (reported) | -8.7% vs -8.3% | 0.822 | |

## Exploratory (hand-entered public facts; descriptive, not tested)
| Cut | n | 12-month excess | Day after |
|---|---|---|---|
| Winner Democrat | 8 | +8.3 pts | +0.78% |
| Winner Republican | 11 | -6.5 pts | +0.34% |
| Party changed (incumbent party lost) | 11 | -1.8 | +0.75% |
| Party held | 8 | +1.8 | +0.22% |
| Incumbent ran | 11 | +0.0 | +0.28% |
| Open seat | 8 | -0.7 | +0.87% |
| 6-month run-up Down / Flat / Up | 1 / 7 / 11 | -2.2 / -6.5 / +3.8 | |

The day after the vote averaged +0.53%, up in 13 of 19. The largest gap is winner's party (Democrat +8.3 vs Republican -6.5, 14.8 points, about 2 standard errors). It is one of about 9 groupings looked at, small groups of 8 and 11, with the 12-month returns of overlapping periods and a handful of years (2000, 1956, 1996, 2020) doing the work; expect roughly one such gap by chance. Treat it as folklore on known history, not a finding. "Down" has one case (2008).

## Honest reading
Where it would go: at most a descriptive CGI context note ("the 12 months after presidential elections have looked like any other 12 months, n = 19"). Never a rule. The 4-year presidential-cycle folklore is not visible in this narrow slice with this test, but a +12 to +15 point effect is the floor of what could be seen after the vote, so smaller effects are not excluded.

## Gaps and decisions the plan did not cover
- 2024 counted as an open seat (the incumbent withdrew); changing it moves one case between the "incumbent ran" and "open seat" cuts only.
- IB cross-check not used (PREREG says why); TradingView covers all 19 election closes.
- B's windows are fixed calendar proxies (Jan-Jun, Jul-Oct), not the actual nomination or convention dates, so B cannot say anything about specific primaries or conventions.
- No live case: the next presidential election is 2028.

## Audit
Pending (separate fresh-context session). Not in the settled index.
