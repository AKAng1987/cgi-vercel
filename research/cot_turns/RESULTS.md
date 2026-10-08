# COT extremes: how long until the crowd is wrong, and what confirms it

Run 2026-10-08. Offline only; nothing deployed. Reproduce: `check_harness.py` (SELFTEST OK) then `run.py` (CFTC
public API + price-history, read-only). 822 extreme episodes (speculator 3-year index ≥ 95 or ≤ 5, first week of
each episode, dated at the Friday publication) across 27 futures contracts mapped to CGI's daily prices, 2006-2026.
Returns are measured AGAINST the crowd and demeaned by the instrument's own average move, so a market that simply
trends all sample does not count. Intervals bootstrap over event weeks.

## Verdict

**Crowding alone is a weak, slow fade. Price confirmation does not help. Trend strength (ADX) is the useful filter:
don't fade a crowd in a strong trend.**

1. **No faster turn than chance.** 92% of crowded markets broke a 4-week extreme against the crowd within 13 weeks,
   median 16 trading days, versus 95% / 12 days from random dates. Crowded markets, if anything, keep going a bit
   longer before turning.
2. **Fading at the report:** +0.09% (2 weeks), +0.49% (4 weeks), **+0.77% at 8 weeks [+0.09, +1.49]**, +0.75% at 13
   weeks (not significant). Small, and only over months.
3. **Waiting for price to confirm made it worse:** −0.2% to −0.4% after the breakout against the crowd. The same holds
   for every 4-week breakout on these instruments (−0.2% to −0.4%, significant), so breakouts here tend to give back,
   and the COT reading does not rescue them.
4. **ADX at the report separates the cases** (8-week fade):
   - ADX < 20: +0.94% [−0.28, +2.13]
   - ADX 20-30: **+1.43% [+0.05, +2.84]**
   - ADX > 30: −0.10% [−1.79, +1.24]. In a strong trend the crowd stays right.
   ATR% (volatility vs its own year) did not separate cleanly.
5. **Crowded LONG fades work; crowded SHORT fades don't:** +1.54% [+0.62, +2.46] versus +0.07% [−0.92, +1.01].
6. **Not decaying:** 2006-15 +0.48%, 2016-26 +1.04%.

About a dozen splits were checked, so single splits that barely clear zero (ADX 20-30) should be read cautiously;
the crowded-long result is the clearest. The full split table is in `results.json` and the events in `events.csv`.

## For the trader

- COT extremes are context with a slow, small edge (about 1% over 8 weeks), not a timing signal. Shapiro's "a filter,
  not a trigger" holds.
- The most useful rule: **do not fade a crowd when ADX > 30.** Strong trends keep the crowd right.
- If you fade at all, crowded longs (index ≥ 95) with ADX under 30 are where the edge was.
- "Wait for price to confirm" (a 4-week breakout against the crowd) did not improve the result on this data.

## Caveats

27 contracts, uneven event counts (Russell and the 2/10-year notes have very few); ETF proxies for some futures
(CORN, SOYB, WEAT, CANE, SHY, IEF, TLT, UUP) and USD-quoted FX; no costs (multi-week holds, so costs are small);
CGI's own COT panel marks extremes at 10/90, while this study used 5/95.
