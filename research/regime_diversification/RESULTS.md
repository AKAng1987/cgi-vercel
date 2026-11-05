# Does a regime-conditional correlation matrix improve a walk-forward portfolio?

Run 2026-11-05. Offline only; nothing here is deployed. Reproduce: `fetch_data.py` (Yahoo + AWS read), `check_harness.py` (must print SELFTEST OK),
then `run.py` (needs numpy and scipy; saved output in `harness_output.txt`, `run_output.txt`, `results.json`). Pre-registration and its one
amendment are in `PREREG.md`.

## Verdict

**No detectable benefit. Knowing the Compass regime does not improve the portfolio beyond what plain min-variance or risk parity already deliver (under a volatility-dominated optimizer; see caveat 1).**
The portfolio that uses the regime-conditional correlations (C1) is 1.2 points less volatile than inverse-volatility weighting (B3), but it is
indistinguishable from the same optimizer using ordinary all-history correlations (B4): volatility difference +0.01 pts, interval [-0.00, +0.02].
Primary test not claimed. The diversification came from the optimizer, not from the regime. It is "likely null on return, plausible on drawdown" as
expected; drawdown is also null once B4 is the comparison. Return was never the claim: C1 earned 3.5% a year, level with B4 (-0.07 pts [-0.16, +0.03]).

| Portfolio (net of costs, Apr 2010 - Nov 2026, 4,174 days, 200 monthly decisions) | Return | Vol | Sharpe over SHY | Max drawdown | Calmar |
|---|---|---|---|---|---|
| B1 equal weight | 6.9% | 10.7% | 0.55 | 21.7% | 0.32 |
| B2 60/40 (SPY/IEF) | 9.5% | 9.8% | 0.84 | 21.3% | 0.44 |
| B3 inverse volatility (the bar) | 3.6% | 4.2% | 0.56 | 11.1% | 0.32 |
| B4 min-variance, ordinary correlations | 3.6% | 3.0% | 0.83 | 7.3% | 0.48 |
| B5 risk parity, ordinary correlations | 3.0% | 2.6% | 0.71 | 6.7% | 0.44 |
| **C1 min-variance, regime-conditional correlations** | 3.5% | 3.0% | 0.80 | 7.2% | 0.49 |
| C1 risk-parity version | 2.9% | 2.6% | 0.68 | 6.9% | 0.43 |

Turnover about 0.10 of the book per month for the min-variance versions (0.08 for inverse-vol), cost drag a few basis points a year. The three
low-risk portfolios hold mostly IEF, SHY and UUP (25% cap each), so they are low-return, low-risk portfolios; Sharpe and drawdown are the fair comparison.

## Tests (95% paired moving-block bootstrap, 21-day blocks, 2,000 draws; "benchmark minus C1", positive = C1 better)

| Test | vs B3 | vs B4 (regime-blind, same optimizer) | Claim |
|---|---|---|---|
| **Primary: annual volatility** | +1.18 pts [+0.92, +1.45] | +0.01 pts [-0.00, +0.02] | **No** (needs both) |
| Secondary: max drawdown | +3.9 pts [+0.1, +8.5] | +0.2 pts [-0.3, +0.3] | Beats B3 only: the optimizer, not the regime |
| Secondary: Sharpe | +0.24 [-0.06, +0.56] | -0.02 [-0.06, +0.01] | No |
| Secondary: Calmar | +0.17 [-0.08, +0.57] | +0.00 [-0.07, +0.03] | No |

Original drawdown primary (before Amendment 1): vs B3 +3.9 pts [+0.1, +8.5], vs B4 +0.2 pts [-0.3, +0.3]: also not claimed.

Exploratory (13 run, about 0.7 false positives expected at 95%): 2 intervals clear zero, both are C1 against high-volatility benchmarks (equal weight +14.6
pts, 60/40 +14.1 pts of drawdown): a low-risk portfolio against a high-risk one, not regime information. Scaled to the same 10% volatility, C1 versus B3 is
+2.6 pts [-5.0, +12.6], not distinguishable. Nothing else clears zero: regime risk parity vs B5 -0.2 [-0.5, +0.1]; 16-quadrant version +0.0 [-0.5, +0.2]; pure-regime
matrix +0.3 [-0.6, +0.5]; 21-day label lag +0.1 [-0.3, +0.3]; three sub-periods -0.1 / -0.0 / +0.2 pts; vs a 756-day rolling blind min-variance +0.5 [-0.6, +0.8]; effective number of bets
as a lead on the next 63-day drawdown, controlling for 20-day vol, rho +0.07 [-0.10, +0.27].

## Why the regime has no purchase here (descriptive, not tested)

- **The regime barely changes the weights.** C1 and B4 differ by 2.7% of the portfolio per month on average (sum of absolute weight changes, two-sided; 1.4% one-sided; not in run_output.txt). Min-variance is driven by the three lowest-volatility
  sleeves (IEF, SHY, UUP, at the cap), so the correlation structure moves little.
- **Correlations barely differ by regime; they differ by era.** Matrix-to-matrix correlation of the 91 pairwise correlations: C1 vs C2 0.99, each bucket vs all-days
  0.99 / 1.00 / 0.93; mean absolute gap vs all-days 0.04 (C1), 0.03 (C2), 0.13 (C3+C4). Across 2007-12, 2013-18 and 2019-26 the matrices correlate 0.90-0.93 but the mean
  absolute gap is 0.12-0.22, about 3-7 times the C1/C2 regime gap but only 1-1.7 times the C3+C4 gap (0.13).
- **Where a regime does show up, it is thin.** SPY-TLT correlation is about -0.35 in C1 and C2 and -0.01 in C3+C4 (775 days; few episodes): in the stress
  regimes the bond hedge disappears. SPY-GLD about 0 everywhere; SPY-DBC +0.36 to +0.46; SPY-UUP -0.13 to -0.24. This is the one pattern a note could show, with n flagged.
- Diversification ratio (equal weight) 1.50 / 1.53 / 1.59 and effective number of bets 5.9 / 6.0 / 6.7 in C1 / C2 / C3+C4 (6.2 overall): the 14 sleeves behave like about six independent bets.

## Harness

`check_harness.py` plants a regime-dependent hedge (which of two hedge groups protects the risk assets flips with the regime), on the real trading calendar and real Compass
labels. Volatility primary found **8/8** at the strongest plant (gap +/-0.35); a false claim from no-effect data **0/20**; smallest gap found in 6/8: **+/-0.1**
(4/8 at +/-0.06, 0/8 at +/-0.04). The same plants found by the original drawdown primary: 0/8 at +/-0.20 and 0/8 at +/-0.35 -- drawdown, one extreme number
from one 16-year path, is unusable for a regime claim here. SELFTEST OK.

## Caveats (read before relying on the null)

1. **The planted test used equal volatilities; the real sleeves do not.** The harness is powered for correlation changes among similar-risk assets. Real min-variance is dominated by
   volatility differences, which is exactly why the real weights barely move. A regime effect on correlations that exists but is small relative to volatility differences cannot show up
   here. The risk-parity version (less dominated by volatility level) is also null, but only as an exploratory test.
2. **Label vintage is unproven.** Stored regime labels are not first-print vintage (CGI_OPERATIONS: GDP vintage replay not done). A 21-day lag changes nothing (null), which does not remove a
   revision problem; it only shows the null is not fragile to a lag.
3. **Amendment 1 and a disclosure.** The primary moved from max drawdown to volatility after the harness showed drawdown has no power. Before that, a smoke test printed one summary line per
   portfolio on real data (C1 and B4 essentially the same). No interval or claim had been seen. Both versions are null.
4. **Scored from April 2010** (756 days of warm-up from March 2007), so the 2008 crisis is warm-up, not out-of-sample. Only about 16.6 years and 200 months. C3+C4 regime estimates rest on 775 days.
5. **Data:** Yahoo dividend-adjusted closes (CGI's own closes are price-only: TLT 0.86x since 2008 vs 1.52x adjusted, checked); 14 US-listed ETFs; no credit, TIPS, EM bonds, broad EM equity, Philippine assets or crypto.
   SHY as the risk-free rate and also a sleeve. Costs 5/10 bps one way; no taxes, no slippage on real fills.
6. Sector-sleeve sensitivity and a Bitcoin sub-sample (both in the plan) were not run; the primary is already null and neither can change a regime-vs-blind comparison on this evidence.

## What this means for Arvin's trading

Context only. Nothing here is a size, rule or weight. The result says portfolio construction by volatility and correlation (min-variance, risk parity) beats equal weight on risk and that
regime information does not add to it, consistent with `vol_state` and `rank_oos`. The one live-relevant fact: the stock-bond hedge (SPY-TLT about -0.35) is gone in the C3+C4 regimes (about 0 in
775 days), so do not assume bonds diversify equities there. For his book (about 150 trades a year, 1-8 week holds, $600 risk per trade, 3% monthly loss limit) the useful follow-up, not built, is a Pulse study of the
correlation among his open positions (are three $600 trades one $1,800 bet).

## Audit

Fresh-context audit 2026-11-05 (Sonnet, no memory of the study): **0 blocking.** Lookahead clean (checked in code and by running it); costs and turnover correct; bootstrap paired and signed correctly; harness uses the real code path and its noise case is sound; exploratory count 13 matches. Non-blocking findings and what was done:
- Label lag is effectively 2 trading days at the decision (conservative), not "t-1" as worded. Harmless; wording noted here.
- Early compass events (before 2007-08) sit on round Jan/Jul dates and look backfilled. Vintage stays flagged unproven.
- B3 (inverse-vol) is uncapped (mean SHY weight 0.51, max 0.80) while B4/C1 are capped at 25%, so C1-vs-B3 compares unlike constraints. The decisive comparison is C1 vs B4 (same cap, same optimizer).
- The secondary max-drawdown interval vs B3 has lower bound +0.07 pts, marginal, and has no multiplicity adjustment; it is not a regime claim (fails vs B4).
- The primary has no minimum effect size; the vs-B4 volatility lower bound is -0.00004, so +0.008 pts was close to "significant" and is economically nothing.
- Max-drawdown block-bootstrap intervals are asymmetric and rough (E1 +14.6 [8.2, 33.3]); E1/E2 are trivially true.
- The harness plant was redesigned once and the primary moved after the drawdown power result: disclosed (Amendment 1), but a researcher degree of freedom. Harness power is for equal-vol assets, not proof of real-data power.
- The headline was softened to "no detectable benefit"; the era-vs-regime ratio corrected above.
