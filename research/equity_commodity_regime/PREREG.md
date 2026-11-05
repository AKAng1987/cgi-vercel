# Pre-registration: regime information in an equity + commodity portfolio, judged on return per unit of risk

Locked 2026-11-05, before any code for this study was written or run. Approved by Arvin the same day ("judged on per unit of risk").
Offline only; nothing deploys. Follows `research/regime_diversification` (null: regime-conditional correlations added nothing to a bond-heavy
min-variance book). That portfolio held about half bonds/cash-like sleeves, which does not serve Arvin's goal (alpha from equities and
commodities), so this study removes bonds as a sleeve.

**Question.** In a long-only, monthly-rebalanced portfolio of 7 equity ETFs and 3 commodity ETFs (cash = SHY as the fallback, never a sleeve),
do (1) a regime tilt between equities and commodities, (2) volatility-based sizing, or (3) regime-conditional correlations improve
Sharpe ratio over cash (return per unit of risk) over the simple baseline each is compared with?

**Data.** Yahoo dividend-adjusted daily closes. Equities: SPY QQQ IWM EWJ EWG FXI EWZ. Commodities: DBC GLD USO. Cash: SHY (risk-free for
Sharpe; also where the unused part of a vol-sized portfolio sits). Common start 2006-04 (USO); first decision after 756 days (about April 2009),
scored to Nov 2026. 2008 is warm-up. Regimes: CGI model-history as stored (not first-print vintage; flagged "label vintage unproven").
Label in force on trading day t-1, further shifted 1 day (effectively 2 days at the decision, as in `regime_diversification`).

**Construction (fixed).** Decision = first trading day of a month, all inputs dated before it. Covariance = D x R x D, D = 60-day vol, blind R = all
history shrunk 20% to constant correlation; regime R = same Compass bucket (C1, C2, C3+C4; at least 120 days, else blind), shrunk the same way, blended
50/50 with blind R. Long-only. Costs 5 bps one way, 10 bps for DBC, USO, EWZ, FXI, on turnover against drifted weights. SIZING OVERLAY applied to every portfolio
except EW: scale s = min(1, 10% / ex-ante annual vol of the portfolio under the blind covariance); (1 - s) in SHY. No leverage.

**Portfolios.** EW: 10 sleeves equal weight, 100% invested, no overlay (the "hold" baseline). V: inverse 60-day vol across the 10, with overlay (the vol-sizing
baseline). G0: 50% equities / 50% commodities, inverse-vol within each group, with overlay. T1: G0 with the group split tilted to 65/35 toward the group that did better on
earlier days of the current Compass bucket (no tilt if fewer than 120 days). B4e: min-variance (25% cap) with blind R, with overlay. C: the same with regime R, with overlay.

**Primary family (3 tests, Sharpe over SHY, paired moving-block bootstrap, 21-day blocks, 2000 draws, 98.3% intervals = Bonferroni for 3):**
- P1 regime tilt: T1 minus G0. Claim if lower bound above zero.
- P2 volatility sizing: V minus EW. Claim if lower bound above zero.
- P3 regime correlations: C minus B4e AND C minus V, both lower bounds above zero.
**Secondary (4, 95% intervals):** max drawdown and Calmar for T1 vs G0 and for C vs B4e. Annual return difference reported, no claim.
**Exploratory (8, 95%, about 0.4 false positives expected), Sharpe difference:** 16-quadrant tilt vs G0; pure-regime R (blend 100%) vs B4e; 21-day label lag for
T1 vs G0 and for C vs B4e; C vs B4e in 2009-14, 2015-20, 2021-26; C vs a rolling-756 blind min-variance.
**Descriptive, not tests:** equity-minus-commodity return and correlation by Compass bucket, turnover, cost drag, the full portfolio table.

**Honest prior.** Likely null on all three. `rank_oos` (regime asset lists are a coin flip) argues against P1; P2 should be positive (`vol_state`) but may
be small because Sharpe already includes the vol; `regime_diversification` argues against P3. Chance at least one primary claims: about 25%.
A pass goes to a descriptive CGI Context note, never a rule or size. A null is recorded and not re-proposed.

**Harness (check_harness.py).** Per arm, synthetic data on the real calendar and real labels. Plant 1: group drift depends on the regime. Plant 2: persistent
two-state volatility with constant expected return. Plant 3: regime-dependent hedge group (as in `regime_diversification`). Must find each planted effect in
at least 6 of 8 runs and claim from no-effect data in at most 2 of 20 per arm; report the smallest planted effect found in 6 of 8.

**Rule on changes.** Any change after this point goes in an Amendment section with date, reason, and what had been seen.

## Amendment 1 (2026-11-05, after the first harness runs, before any real-data run of this study)

What was seen: only synthetic harness output. No real-data number of this study had been computed. (The earlier `regime_diversification` study, a bond-heavy 14-ETF
book, was null on regime correlations and on volatility sizing's value; that is background, not a result of this study.)
The harness showed a Sharpe test cannot see two of the planted effects on 17 years of data: a persistent volatility swing as large as 5x moved the Sharpe difference
between vol-sized and hold by only about +0.03 to +0.07 against an interval of +/-0.15 (0/8), and a regime-dependent hedge group at the largest correlation gap that keeps the
matrix valid (0.35) was found by a Sharpe test 1/8, by a volatility test 8/8 (still 8/8 at gap 0.2). The Sharpe ratio of two similar portfolios differs mostly by the luck of the
mean return, which no sizing or correlation rule can control. Changes:
1. **P2 (vol sizing, V vs EW) becomes descriptive**, not a claim: it replicates `vol_state` and cannot be tested on Sharpe here. Its Sharpe, volatility and drawdown are reported.
2. **P3 is tested on volatility** (C calmer than B4e AND V), with Sharpe reported beside it as the return-per-risk headline, flagged underpowered.
3. **P1 stays on Sharpe** (found 8/8 at a group-drift gap of 0.0006 a day, 0/20 false; smallest found 0.0004 a day, about 10 points a year).
4. Primary family is therefore 2 tests: intervals widen to 97.5% (Bonferroni). Secondary (4) and exploratory (8) are unchanged; exploratory Sharpe tests of C are
   underpowered by the same argument, and their volatility difference is printed beside them.
