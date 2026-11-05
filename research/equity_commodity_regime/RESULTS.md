# Does regime information improve return per unit of risk in an equity + commodity portfolio?

Run 2026-11-05. Offline only; nothing here is deployed. Reproduce: `fetch_data.py` (Yahoo), `check_harness.py` (must print SELFTEST OK), then `run.py`
(numpy and scipy; saved output in `harness_output.txt`, `run_output.txt`, `results.json`). Pre-registration and its one amendment: `PREREG.md`.
Follows `research/regime_diversification` (same machinery, bonds removed because that book was about half bonds).

## Verdict

**No. Neither the regime tilt (P1) nor regime-conditional correlations (P3) improves return per unit of risk beyond its simple baseline, and none of the 8 exploratory tests clears zero. Vol sizing (P2) was demoted to descriptive after the harness (Amendment 1), so it was not tested; its Sharpe was lower than hold's, within noise.**
Universe: 7 equity ETFs (SPY QQQ IWM EWJ EWG FXI EWZ) and 3 commodity ETFs (DBC GLD USO), cash = SHY, monthly, long-only, 5-10 bps costs, May 2009 to Nov 2026
(4,405 days, 211 decisions; 2008 is warm-up).

| Portfolio (net of costs) | Return | Vol | Sharpe over cash | Max drawdown | Avg cash |
|---|---|---|---|---|---|
| EW equal weight, always invested | 9.2% | 16.3% | 0.53 | 33.8% | 0% |
| V inverse-vol, sized to 10% vol | 5.5% | 10.3% | 0.44 | 26.2% | 27% |
| G0 50/50 equity/commodity, sized | 5.3% | 10.1% | 0.42 | 27.9% | 25% |
| T1 G0 tilted 65/35 by regime | 5.2% | 10.2% | 0.42 | 26.1% | 27% |
| B4e min-variance, ordinary correlations, sized | 7.0% | 10.3% | 0.57 | 23.9% | 13% |
| **C min-variance, regime correlations, sized** | 6.9% | 10.3% | 0.56 | 23.9% | 13% |

| Primary test (97.5% interval, Bonferroni for 2) | Estimate | Claim |
|---|---|---|
| **P1 Regime tilt:** Sharpe, T1 minus G0 | -0.006 [-0.105, +0.091] | No |
| **P3 Regime correlations:** volatility, benchmark minus C (positive = C calmer) | vs B4e -0.02 pts [-0.05, +0.00]; vs V -0.06 pts [-0.37, +0.26] | No |
| (beside P3) Sharpe, C minus B4e / C minus V | -0.009 [-0.023, +0.003] / +0.124 [-0.041, +0.255] | Not claimed (P3 is judged on volatility) |
| P2 Vol sizing, descriptive: Sharpe V minus EW | -0.091 [-0.231, +0.072] | Not a claim |

Secondary (95%, 4 tests): max drawdown and Calmar for the tilt (+1.8 pts [-3.8, +3.8]; +0.01 [-0.08, +0.07]) and for regime correlations (0.0 pts [-0.8, +0.3]; -0.004 [-0.026, +0.004]): none. Annual return: tilt -0.02 pts [-0.97, +0.87]; regime correlations -0.09 pts [-0.24, +0.03].
Exploratory (8): 16-quadrant tilt +0.025 [-0.05, +0.11]; pure-regime correlations -0.021 [-0.049, 0.000]; 21-day lag tilt -0.040 and correlations -0.009; sub-periods 2009-14 / 2015-20 / 2021-26 -0.013 / -0.013 / 0.000; vs rolling-756 blind +0.007. Zero claims (about 0.2 expected by chance for one-sided 2.5% claims; PREREG's 0.4 assumed two-sided 5%).

## What the descriptive data say

- **Vol sizing did not raise Sharpe here.** Sized portfolios cut max drawdown (EW 33.8% to V 26.2%) and volatility by design, but the Sharpe of the sized portfolios (0.42-0.44) is below hold (0.53); a likely cause (a hypothesis, no run isolates it) is that the overlay parks about 27% in cash while equities rose, and inverse-vol weighting leans toward commodities. The gap is inside the noise (-0.09 [-0.23, +0.07]) but the sign is not what a risk-adjusted story predicts. `vol_state` showed vol sizing cuts drawdowns; it did not claim a Sharpe gain either.
- **Min-variance had the best Sharpe (0.56-0.57) but regime information has nothing to do with it.** B4e and C are indistinguishable, and if anything regime correlations are slightly worse on volatility (pure-regime vs B4e: C more volatile by 0.04 pts [0.00, 0.08]; vs rolling-756 blind: 0.08 pts [0.02, 0.15]). Average min-variance weights: GLD 20%, SPY 19%, DBC 15%, EWJ 13%, SHY (cash) 13%, QQQ 9%; C and B4e differ by only 2.5% of the book per month (two-sided). The +0.12 over V is inside the noise.
- **Equity-minus-commodity returns do differ by Compass bucket in sample, and the tilt did not capture it.** Annualised: C1 equities +12.6% vs commodities +1.9% (gap +10.7 pts, 1,898 days); C2 +9.3% vs +8.3% (gap +0.9); C3+C4 +9.3% vs +4.6% (gap +4.7). The group correlation is 0.33-0.46 everywhere. A walk-forward tilt using only earlier days of the same regime gained nothing (Sharpe -0.006). In-sample gaps are not forecasts; this is the same pattern `rank_oos` found for individual assets.
- **Risk is still equity risk.** The equity and commodity groups correlate +0.33 to +0.46 in every bucket, so adding commodities diversifies less than the label suggests.

## Harness

Plant 1 (group drift flips with the regime): found **8/8** at a gap of 0.0006 a day (about 15 pts a year), false claim **0/20**, smallest gap found in 6/8: **0.0004 a day (about 10 pts a year)**; 2/8 at 0.0002. This is the detection limit for the tilt on Sharpe: a real tilt effect below roughly 10 pts a year would be missed.
Plant 3 (regime-dependent hedge group), tested on volatility: **8/8** at gap 0.35, false **0/20**, smallest gap 6/8: **0.1** (7/8; 0/8 at 0.05).
Plant 2 (vol swings with ~50-day states, short against the 60-day vol window, so a weak form of vol timing): a Sharpe test found it **0/8** at a 5x swing (2/8 at 2-3x). Treat that as a limit of this plant and of a Sharpe test on 17 years, not of vol timing in general. This is why P2 became descriptive and P3 moved to volatility (Amendment 1). SELFTEST OK for the two arms that are claims.

## Caveats

1. **Sharpe is a low-power statistic here.** Over 17.5 years the interval on a Sharpe difference between two similar portfolios is about +/-0.1, mostly the luck of the mean return. A real improvement of 0.05 to 0.1 cannot be seen. "No gain" means none large enough to see.
2. **Amendment 1** (PREREG; the figures it quotes came from earlier harness runs not saved, only the final `harness_output.txt` is) changed the claims after the harness: P2 descriptive, P3 on volatility, Bonferroni for 2. No real-data number had been computed for this study; the earlier bond-heavy study was a null on the same questions.
3. **Label vintage is unproven** (stored labels are not first-print); lagging them 21 days changes nothing.
4. The vol-sizing overlay targets 10% volatility with no leverage and leaves cash idle, which lowers Sharpe in a rising market; a leveraged version or a different target is untested.
5. Dividend-adjusted Yahoo closes; 10 US-listed ETFs; USO is a futures-roll product with known roll drag (included in its adjusted close); no tax or slippage beyond 5-10 bps.
6. Regime estimates use Compass buckets only (C3+C4 pooled, 998 days). The 16-quadrant version is thinner and also null.

## What this means for Arvin's trading

Context only; nothing here is a size, rule or weight. Within equities and commodities, neither the Compass regime nor its correlation structure gave a reliable way to choose or size between the two groups, and plain volatility sizing mainly trades return for lower drawdown. If the goal is alpha from equities and commodities, it will have to come from somewhere other than regime tilts or regime correlations, such as selection within a group or his own trade edge, which Pulse measures. This study does not test either.

## Audit

Fresh-context audit 2026-11-05 (Sonnet, no memory of the study): **0 blocking.** Lookahead, costs (including the cash column), bootstrap signs, the 97.5% level, sub-period slices, test counts and the harness code path all checked clean; every RESULTS number matches the saved outputs. Non-blocking findings, all addressed above: average-weight figures added to `run.py` output; the cash-drag explanation labelled a hypothesis; the volatility cost of regime correlations stated; the chance-claim expectation reconciled; the verdict line says P2 was not tested; plant 2 described as weak vol timing. Also noted: drawdown and Calmar block-bootstrap intervals are approximate (biased toward smaller drawdowns); 0/20 false claims is compatible with a true false-claim rate up to about 14%; the harness uses 500 bootstrap draws vs 2000 in the real run; regime labels are not first-print (the 21-day lag moved the tilt Sharpe from 0.42 to 0.38, not significant).
