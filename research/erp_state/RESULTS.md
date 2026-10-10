# Does Damodaran's implied equity risk premium add anything beyond regime and 20-day volatility?

Run 2026-10-10. Offline only; nothing here is deployed. Reproduce: `fetch_data.py`, then `check_harness.py` (must print
SELFTEST OK), then `run.py`. Method and information rules are in the header of `erp_study.py`.

**Data.** Damodaran's monthly implied ERP (trailing-12-month version), Sept 2008 to Oct 2026, stored in CGI as `ERP_T12M`
(and his annual year-end series back to 1961 as `ERP_ANNUAL`). 216 decision months; after tercile and training warm-ups,
about 145 months are scored out of sample (mid-2014 to 2026). At each decision month only the ERP row from the PRIOR month
is used, terciles come from an expanding window, and each regression trains only on months whose forward window had ended.

## Verdict

**No. ERP adds nothing to regime + 20-day volatility out of sample. It makes the forecasts slightly worse.**

Paired out-of-sample squared error, baseline (regime quadrants + log 20-day vol) versus baseline + ERP terciles, 95%
moving-block bootstrap interval of the mean difference (positive = ERP helped). The pre-registered primary test is the
first maxdd3m row; the secondary is ret3m; the other ten are exploratory (12 tests, so about one false claim is expected
by chance at 95%; none appeared).

| ERP feature | Target | n | Relative error change | 95% interval of mean difference |
|---|---|---|---|---|
| level terciles | 3m max drawdown (**primary**) | 145 | −3.3% | [−3.30, +1.12] |
| level terciles | 3m return (secondary) | 145 | −3.8% | [−3.72, +0.26] |
| level terciles | 1m return | 149 | −2.7% | [−1.13, −0.02] |
| level terciles | 3m vol | 145 | −5.9% | [−9.98, +0.87] |
| 3m change | 3m max drawdown | 143 | −2.3% | [−1.49, −0.24] |
| 3m change | 3m vol | 143 | −2.9% | [−4.11, −0.93] |
| 3m change | 1m / 3m return | 147 / 143 | −0.8% / −0.5% | [−0.68, +0.29] / [−1.89, +1.24] |
| ERP minus T-bond terciles | 1m / 3m return | 149 / 145 | −1.4% / −3.1% | [−1.26, +0.74] / [−3.77, +0.67] |
| ERP minus T-bond terciles | 3m max drawdown / vol | 145 | −3.9% / −3.9% | [−3.33, +0.33] / [−7.62, +0.79] |

All twelve are negative. A negative number means the extra dummies add estimation noise and no information.

## What happened after each ERP level tercile (descriptive, walk-forward terciles)

| ERP level | n | Fwd 1m | Fwd 3m | Worst 3m drawdown | 3m vol |
|---|---|---|---|---|---|
| Low (thin cushion) | 87 | +0.86% | +3.00% | 7.35% | 15.9% |
| Middle | 57 | +1.58% | +3.96% | 6.03% | 13.8% |
| High (thick cushion) | 37 | +1.50% | +3.72% | 6.22% | 14.8% |

Low minus high: 3m return −0.72 pts [−3.64, +2.07]; worst 3m drawdown +1.13 pts [−0.99, +3.99]. The direction is the one
a valuation story predicts (thin cushion, slightly lower returns and deeper drawdowns), but every interval includes zero.
Inside the Compass quadrants the same sign shows up (C1 +1.99, C2 +0.88 pts of drawdown, low minus high); C3 and C4 have
too few months to report.

## Long-horizon supplement (annual file, 64 years, 1961 to 2024)

Year-end ERP against the next calendar year's S&P 500 price return: Spearman rho +0.25, 95% [−0.00, +0.47], borderline.
Against the next year's worst drawdown: 0.00 [−0.24, +0.25]. ERP minus T-bond: +0.05 and +0.02 (no relationship). This
covers the 1960s to 2001, when the gap was mostly negative, and finds nothing for the gap in that territory either.

## Caveats

- **Power.** About 145 scored months with overlapping three-month windows. The harness finds a strong planted effect 8/8
  and a moderate one (0.6 of the noise sd) 7/8 on clean synthetic data; real returns have fat tails and overlap, so real
  power is lower. "No clear gain" means none large enough to see here, not none.
- **Today is outside the sample.** On Oct 1 the ERP is 3.70% (lowest of 217 months) and ERP minus T-bond is −1.59 pts. In
  the monthly sample the gap was never below about −0.7. The study cannot say what such readings precede; only the annual
  file visits negative gaps, and it shows nothing for one year ahead.
- The study's latest decision row uses the Sept ERP (4.09%, gap −0.66) because of the one-month lag, so its "now"
  bucket is "thin" either way.
- ERP is built from the S&P price, the T-bond rate and analyst forecasts, so it shares information with price and rates.
- Revisions: the workbook is the latest version, not a vintage archive. Row dates are start-of-month; his first-week posting
  is the reason for the one-month lag.

## Harness

`check_harness.py`: strong planted effect found 8/8; noise falsely claimed 0/20; moderate effect found 7/8. SELFTEST OK.

## What this means

- The ERP gauge on the CGI tab stays as context ("valuation cushion, descriptive, not a forecast"). It is not turned into a
  sizing or drawdown rule, and nothing is handed to the execution project.
- Plain 20-day volatility sizing remains the thing to beat, as in `vol_state/`.
- Revisit when there are more months in negative-gap territory, or if a different premium measure (for example one built
  from forward earnings) is available.
