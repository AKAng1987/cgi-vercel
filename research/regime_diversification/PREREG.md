# Pre-registration: regime-conditional correlation and a walk-forward portfolio

Locked 2026-11-05, before `run.py` was written or run. Approved by Arvin the same day. Offline only; nothing deploys.

**Question.** Does a correlation matrix conditioned on the CGI Compass regime (shrunk toward the all-regime matrix) improve a
long-only, monthly-rebalanced portfolio of 14 ETF sleeves over honest baselines, judged first on max drawdown, then volatility and
return per unit of risk? Return is descriptive only.

**Data.** Dividend-adjusted daily closes from Yahoo (CGI's own closes are price-only, checked: TLT 0.86x vs 1.52x adjusted since 2008).
Sleeves: SPY QQQ IWM EWJ EWG FXI EWZ VNQ TLT IEF SHY GLD DBC UUP. Common start 2007-03-01 (UUP). Risk-free for Sharpe = SHY daily return.
Regimes: CGI model-history compass_US (events from 2004-07) and grid_US (from 2008-03), as stored. Stored labels are NOT first-print
vintage (CGI_OPERATIONS: "GDP vintage replay is not done"), so every result is flagged "label vintage unproven".

**Construction (all fixed now).** Decision day = first trading day of a month; every input is dated before it; weights are held to the
next decision day. Covariance = D x R x D: D = 60-day volatility, R = correlation. Blind R = all history up to the day, shrunk 20% to the
average off-diagonal correlation. Regime R = days with the same Compass bucket (C1, C2, C3+C4 pooled; at least 120 days, else blind R),
shrunk the same way, then blended 50/50 with the blind R. The label used on day t is the label in force on trading day t-1 (lag 1).
Long-only, 25% cap per sleeve. Costs: 5 bps one way, 10 bps for DBC, EWZ, FXI, UUP, charged on turnover against drifted weights.
First decision when 756 days of history exist (about March 2010).

**Portfolios.** B1 equal weight. B2 60/40 (SPY/IEF). B3 inverse 60-day volatility (the bar). B4 min-variance with blind R. B5 risk parity with
blind R. C1 min-variance with regime R. (Candidate.)

**Tests.** 95% paired moving-block bootstrap (21-day blocks, 2000 draws) on net daily returns.
- **Primary (1):** max drawdown, B3 minus C1. A CLAIM needs the interval above zero here AND B4 minus C1 above zero (the gain has to come
  from the regime information, not the optimizer).
- **Secondary (3), each vs B3, claim if interval is in the good direction:** annual volatility, Sharpe over SHY, Calmar (annual return / max drawdown).
- **Return:** annual return difference reported, no claim.
- **Exploratory (13), counted, about 0.65 false positives expected at 95%:** C1 vs B1, B2, B5 (max drawdown) [3]; regime risk parity vs B5 [1];
  16-quadrant regime R [1]; pure regime R (blend 100%) [1]; 21-day label lag [1]; C1 vs B4 by sub-period 2010-15, 2016-20, 2021-26 [3];
  C1 vs a rolling 756-day blind min-variance [1]; C1 vs B3 max drawdown after scaling both to 10% volatility [1]; do rolling effective number of
  bets (ENB) predict the next 63-day drawdown of equal weight beyond 20-day volatility [1].
- **Descriptive (not tests):** correlation by Compass bucket for key pairs, stability of the matrices across 3 non-overlapping eras and across
  buckets, diversification ratio, ENB, turnover, costs.

**Honest prior.** Likely null on return; plausible on drawdown but mostly captured by volatility sizing (`vol_state`) and by the regime-blind
min-variance (B4). Primary pass chance about 20-25%. A pass goes only to a descriptive CGI Context note, never a rule or size.

**Harness.** Synthetic 14-asset returns with three regimes of known, different correlation matrices, using the real regime calendar.
Plant found in at least 6 of 8 runs; false claim from no-effect data at most 2 of 20; report the smallest planted gap found in 6 of 8.

## Amendment 1 (2026-11-05, after the harness, before run.py was run on real data (see disclosure in item 3))

The harness showed the max-drawdown primary cannot detect even the strongest planted effect: the regime-aware portfolio cut planted
volatility by about 11% and the drawdown test still found it 0 of 8 times (a drawdown is one extreme number from one 16-year path; the
bootstrap interval is wide). Volatility is the same claim measured with power: found 8/8 at a planted gap of +/-0.1 and 4/8 at +/-0.06. Changes:
1. **Primary (1) is now annual volatility**, C1 lower than both B3 and B4 (both intervals above zero). Max drawdown moves to the secondary set.
2. **Secondary (3):** max drawdown, Sharpe over SHY, Calmar, each C1 vs B3 (B4 shown).
3. Exploratory count unchanged at 13. DISCLOSURE: before the amendment a smoke test of the pipeline on real data printed one line per portfolio (annual return, vol, max drawdown, turnover, no intervals); it showed C1 and B4 essentially identical (vol 3.0% both, drawdown 7.2% vs 7.3%). No test, interval or claim had been seen. The amendment was decided on the synthetic harness power, but the reader should know that glance happened. The original drawdown primary is still reported (it is also null).
4. Harness plant moved from a symmetric cross-group flip (which min-variance cannot exploit because equal-sized groups get equal weight) to a
   regime-dependent choice of hedge group (H1 vs H2), the thing a regime-aware min-variance can actually use.
