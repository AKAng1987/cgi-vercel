# presidential_cycle -- RESULTS

Built 2026-11-04. Pre-registered in `PREREG.md` (lock commit 839cfe4 holds PREREG.md only and was never edited; the harness, facts and TradingView data were committed next, `run.py` and `results.json` last). Offline; ships nothing. Calendar context only, never a size or entry rule.

## Verdict
**Neither part shows anything distinguishable.** n = 19 presidential elections (1952-2024), so a null means "can't tell", not "no effect". A: the 12 months after Election Day averaged +9.0% against a volatility-matched baseline of +9.3% (excess **-0.3 points**, p = 0.94, 95% interval -8.1 to +7.8). B: January-June of presidential years returned +3.0% against +3.1% in other years (p = 0.99). All 4 secondary tests are also null. Zero claims out of 6 pre-registered tests (A primary, B primary and 4 secondaries; the Jan-Jun drawdown is reported only, not a test).

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
| B primary: Jan-Jun return, presidential vs other years | 3.0% vs 3.1% (-0.0 pts) | 0.993 | none: B is judged on p alone (below) |
| B Jul-Oct return | 0.9% vs 1.6% (-0.6 pts) | 0.766 | |
| B Jan-Jun max drawdown (reported only, not a test) | -8.7% vs -8.3% | 0.822 | |

## Exploratory (hand-entered public facts; descriptive, not tested)
| Cut | n | 12-month excess | Day after |
|---|---|---|---|
| Winner Democrat | 8 | +8.3 pts | +0.78% |
| Winner Republican | 11 | -6.5 pts | +0.34% |
| Party changed (incumbent party lost) | 11 | -1.8 | +0.75% |
| Party held | 8 | +1.8 | +0.22% |
| Incumbent ran | 11 | +0.0 | +0.28% |
| Open seat | 8 | -0.7 | +0.87% |
| **B splits, Jan-Jun return (pre-registered as exploratory):** incumbent ran / open seat | 11 / 8 | +1.8% / +4.8% | |
| Jan-Jun return, party changed / held | 11 / 8 | +2.8% / +3.3% | |
| 6-month run-up Down / Flat / Up | 1 / 7 / 11 | -2.2 / -6.5 / +3.8 | |

The day after the vote averaged +0.53%, up in 13 of 19. The largest gap is winner's party (Democrat +8.3 vs Republican -6.5 pts, a 14.8-point gap). In `run.py` (`winner_gap` in `results.json`): standard error 7.4 points (t = 2.01), a plain two-sample figure that ignores the overlap between neighbouring 12-month windows, so the true uncertainty is larger. No single election drives it: dropping any one leaves a gap between 11.8 and 19.0 points (largest shifts: 1976 4.1, 2020 3.0, 2000 2.6). An earlier draft said "a handful of years (2000, 1956, 1996, 2020) doing the work"; the leave-one-out check shows that was wrong and it is withdrawn. It is the largest of the 8 groupings PREREG listed (4 groupings above plus the 2 Jan-Jun splits and the day-after and Jan-Jun outputs), in groups of 8 and 11; PREREG expected about 0.4 false positives at 5%, and this one is near that line, so it is folklore on known history, not a finding. "Down" has one case (2008).

## Honest reading
Where it would go: at most a descriptive CGI context note ("the 12 months after presidential elections have looked like any other 12 months, n = 19"). Never a rule. A: the smallest effect detectable at 80% power is +15 points (+12 is 78%), so anything smaller than that after the vote is not excluded. B: power at +5 points was 78% and at +7 points 92% in 40 runs; "+7" is the grid's resolution (no +6 was tried), so the true 80% point is about +5 to +6 points. B has no interval: it is a label-permutation test and is judged on p alone (the PREREG claim rule mentions an interval, which only applies to A). The 4-year presidential-cycle folklore is not visible in this narrow slice.

## Gaps and decisions the plan did not cover
- 2024 counted as an open seat (the incumbent withdrew); changing it moves one case between the "incumbent ran" and "open seat" cuts only.
- IB cross-check not used (PREREG says why); TradingView covers all 19 election closes.
- B's windows are fixed calendar proxies (Jan-Jun, Jul-Oct), not the actual nomination or convention dates, so B cannot say anything about specific primaries or conventions.
- No live case: the next presidential election is 2028.

## Audit
Fresh-context audit, 2026-11-04 (a separate agent, read-only). **0 blocking, 5 minor; no unresolved finding.** It reproduced `results.json` byte for byte and confirmed PREREG was locked (839cfe4) before any return and never edited. How each minor finding was handled:
1. **Test count:** text said 8 pre-registered tests; PREREG lists 6 (A primary, B primary, 4 secondaries). Corrected here, in the BACKLOG row and in the CGI section; the drawdown is labelled reported-only.
2. **Groupings and false positives:** wording now follows PREREG (about 8 groupings, about 0.4 false positives).
3. **Standard error and "years doing the work":** both now computed in `run.py` (`winner_gap`: SE 7.4 points, t = 2.01, ignores overlap; leave-one-out range 11.8 to 19.0). The "handful of years" claim was wrong and is withdrawn.
4. **B exploratory splits:** added to the table above (open seat +4.8% vs incumbent ran +1.8%; party changed +2.8% vs held +3.3%), marked exploratory.
5. **B judged on p alone, B power, SELFTEST gate:** stated above. `run.py` does not enforce the SELFTEST OK gate; that rests on process (the harness was run before `run.py` and re-run after these fixes, both OK).
After the fixes `check_harness.py` printed SELFTEST OK and `run.py` changed only `results.json`'s new `winner_gap` key (every other number identical).
