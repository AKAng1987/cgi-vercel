# Calm/stormy risk state (2-state HMM, Baum-Welch) vs plain volatility sizing

Run 2026-10-08. Offline only; nothing here is deployed. Reproduce: `check_harness.py` (must print SELFTEST OK) then
`run.py`. Rules use only information up to the previous close; the HMM is refitted every 63 days on the previous
10 years only. Both sizing rules target 15% annual volatility, capped at 1.5x.

## Verdict

**Do not ship the HMM.** It never beats plain 20-day-volatility sizing with confidence:

| Index (scored from) | HOLD Sharpe / max DD | VOL20 Sharpe / max DD | HMM Sharpe / max DD | HMM − VOL20 Sharpe (95% CI) |
|---|---|---|---|---|
| S&P 500 (1970) | 0.55 / 56.8% | 0.63 / 51.4% | 0.57 / 49.9% | −0.06 [−0.13, +0.00] |
| Nasdaq (1981) | 0.61 / 77.9% | 0.81 / 49.0% | 0.84 / 46.2% | +0.02 [−0.06, +0.11] |
| Russell 2000 (1997) | 0.39 / 59.9% | 0.33 / 39.4% | 0.40 / 38.0% | +0.07 [−0.04, +0.17] |

**What did work, and is the takeaway: sizing to recent volatility.** Either rule cut the worst drawdown sharply
(Nasdaq 78% → ~47%, Russell 60% → ~39%, S&P 57% → ~50%) at similar or better return per unit of risk. That needs no
hidden-state model: hold less when the last month has been volatile.

## Harness

Recovers a known calm/stormy process 8/8 (state vols within 15%, state hit-rate > 85%); claims a winner from noise
0/20; detects perfect-knowledge sizing when the stormy state loses money 8/8. Power note: when both states have
the same average return, even perfect knowledge of the state adds only ~0.1 Sharpe, which decades of daily data can
barely separate from luck -- the benefit of state-aware sizing is mainly drawdown, not return.

## Caveats

Indexes only (no trading costs, which would penalise the daily re-sizing of both rules equally); one target and cap;
the long sample includes regimes unlike today. For the execution project: a volatility-scaled position size is the
defensible version of this idea.
