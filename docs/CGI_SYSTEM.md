# CGI — the system, in seven parts

The reasoning the dashboard is built on, one factor at a time. Two halves
per factor: **what we track**, and **what we know** from testing it.

## How to read the provenance marks

Every section says where its reasoning came from, because that distinction
matters more than the content:

- **[Stated]** — the user's own framing, from a dated interview, recorded in
  `market-dashboard/docs/TRADING_SYSTEM.md`.
- **[Stated in code]** — the user's reading, captured in a module docstring
  at build time rather than in an interview. Same origin, less formal.
- **[Reconstructed]** — inferred from what the build does. **Not the user's
  words.** Replace these with a real interview via
  `docs/FACTOR_INTERVIEW_PROMPT.md`.

A measured result is only as good as its n, so n travels with every number.

---

## The frame

The regime is two 2×2 grids. **Compass** = Liquidity × Credit, **Grid** =
Growth × Inflation. Four axes, each moved by one scheduled release: FOMC,
SLOOS, CPI, GDP. Those four are the **state** — where are we.

The other three factors are **conditioning** — given the state, what matters
for the instrument in front of you.

The single most important measured fact about the whole framework:

> **64% of the variance in country-ETF returns is the regime itself. 2.5% is
> the country.** The state is doing nearly all the work; the conditioning
> layers refine an instrument choice within it, they do not override it.

---

## 1. LIQUIDITY — monetary policy and credit

Two Compass axes, taken together because they are one question: is money
available, and is it being lent?

### 1a. Monetary — set by the FOMC  **[Stated, 2026-09-17]**

**What we track.** The central bank sets rates on its dual mandate, so both
belong on the driver list. Rate expectations follow the market's front end —
the **3-month bill** and the **2-year**. Empirically the 3m bill's move has
to be followed by the Fed within that 3-month window; the 2y is the same
vote over a longer horizon. Both sit *above* the 10-year, which is a growth
and credit read, not a liquidity read. For employment: the unemployment
rate's change, plus Challenger job cuts as rate of change, with a level
above 150k as an intervention point.

Inputs: `US03MY`, `US02Y`, `DFEDTARU`, `UNRATE`, `CPIAUCSL`, `CHALLENGER`.

**What we know.** Measured at each 45-day FOMC window start, bucketed into
terciles of each driver's own history.

- **3m − target and 2y − target are the strongest single drivers on any
  axis.** Both in the top tercile → 22% flip rate, against 0–2% below
  target and an 8% base. Tested live on the 2026-09-16 hike: both top
  tercile, conditioned 14% before the decision.
- Unemployment separates as expected — the Fed moves when unemployment is
  flat (mid tercile 26%).
- CPI y/y is weak at this granularity.
- **Challenger is directional, not symmetric.** Easing state: low Challenger
  → 14% flip vs 2% when high — the Fed hikes into labour strength.
  Tightening state: low → 53%, high → 6% — the Fed cuts *before* the layoff
  count spikes. 2001, 2008 and 2020 all show the first cut months ahead of
  the 150K crossing.
- USDJPY tested and dropped: no separation for the US decision.

**Open.** The tightening state has too few windows since 2008-12 to score
properly. Extending history via `FEDFUNDS` (1954→) would fix that at the
cost of using the effective rate instead of the target.

### 1b. Credit — set by SLOOS  **[Stated, 2026-09-17]**

**What we track.** Bank lending is the curve: banks borrow short and lend
long, so the slope is the lending margin. The academic form is 10y−3m since
deposit costs track the policy rate; both were tested and **10y−3m is
cleaner**. Also: the curve against credit default swaps, and bank stocks as
KBE/SPY.

Inputs: `US10Y`, `US03MY`, `BAA10Y`, `KBE`, `SPY`, `NFCICREDIT`, `BUSLOANS`.

**What we know.** 91-day SLOOS windows: 47 easing-state, 42 tight-state,
since 2006. Base rates 32% / 38%.

| driver | easing → tighten? lo/mid/hi | tight → loosen? lo/mid/hi |
|---|---|---|
| 10y−3m level | **53** / 25 / 19 | 50 / 29 / 36 |
| Baa−10y 30d chg | 14 / 29 / **50** | **57** / 29 / 29 |
| KBE/SPY 30d | **50** / 27 / 20 | 38 / 54 / 23 |
| NFCI credit 13w chg | 27 / 6 / **62** | **71** / 29 / 14 |
| C&I loans 13w % | 20 / 19 / **56** | 50 / 43 / 21 |
| SPY 30d | **67** / 19 / 12 | 29 / 64 / 21 |

Dropped: 2s10s, Baa−10y level, KRE (identical to KBE), XLF/SPY (Berkshire,
JPM, V and MA dominate it — not lending-sensitive), NFCI level.

**The curve-language correction.** "Steepening" alone mixes two opposite
worlds, so the names say which end moved:

| | short end | long end | bonds | cause |
|---|---|---|---|---|
| bull steepener | falls fast | flat | up | Fed cutting into weakness |
| bear steepener | flat | rises fast | down | term premium, inflation, fiscal |
| bull flattener | flat | falls fast | up | flight to quality |
| bear flattener | rises fast | flat | down | Fed hiking (2022) |

The CDS observation is the **bull** steepener specifically — the curve
steepens because the front end collapses as the Fed cuts into a downturn,
which is when default risk reprices. H2 2023 bear-steepened just as hard
with CDS tight.

---

## 2. FISCAL POLICY  **[Stated, partial — not yet backtested]**

**What we track.** Dated announcements by country, each naming the themes
and tickers it should move. Monetary, fiscal, trade and geopolitical, kept
in `api/notes_data.py` as a register the user writes.

The design intent is that it works **forward**: a policy lands, it names the
themes to watch, and those themes are then checked against relative
strength. The point is to be early rather than to explain a rally six months
after the fact. A note stays on LIVE while any theme it points at is still
running on RS.

**What we know — honestly, not much yet.** This is the one factor with no
measured contract. The framing exists and the register is populated; the
backtest is queued, not done.

What is recorded rather than measured:
- Fiscal programmes (CHIPS, IRA, IIJA) are "a year's worth of growth as cash
  comes in" — a narrative that needs its own backtest.
- Japan, Oct 2025: Takaichi's spending programme. Oct 2025 → Mar 2026, Japan
  +13.8% in yen, USDJPY +8.1%, but EWJ only +5.3% because it is unhedged.
  **The read-through is as much about instrument as direction** — the right
  call on the country was the wrong call in the wrong wrapper.
- US, Apr 2025 reciprocal tariffs: refiners began running a month later
  (CRAK from 2025-05-05).

**This is the biggest gap in the system document.** Six factors have tercile
tables; this one has anecdotes.

---

## 3. INFLATION — Grid axis, set by CPI  **[Stated, 2026-09-19]**

**What we track.** ISM services and manufacturing prices paid, USCI, DBC,
USOIL, CPI, whichever gauge the Fed is leaning on (core PCE / core CPI), and
on the bond side TIPS less nominal. Live prices enter as a rolling ~30-day
move matched to the release frequency — "as oil goes up, the probability
that CPI rises". The panel should show which input is pushing the
probability.

**What we know.** 30-day CPI windows: 107 cool-state, 117 hot-state, since
2008-03. Base rates 33% / 30%. Swept 28 candidates.

| driver | cool → turn up? | hot → cool? |
|---|---|---|
| WTI 3m % | 20 / 25 / **53** | **46** / 26 / 18 |
| WTI 30d % | 9 / 33 / **56** | 41 / 26 / 23 |
| DBC 30d % | 11 / 39 / **47** | **44** / 28 / 18 |
| PPI commodities 3m % | 17 / 36 / 44 | 38 / 36 / **15** |
| Import prices 3m % | 17 / 36 / 44 | 36 / 38 / **15** |
| Dollar 30d % | 31 / 42 / 25 | 20 / 28 / **41** |
| 5y breakeven 30d chg | 14 / 33 / **50** | **44** / 26 / 20 |
| ISM svc prices m/m | 23 / 22 / **56** | **47** / 22 / 20 |
| ISM mfg prices (level) | 25 / 28 / **47** | 36 / 36 / **18** |

CPI m/m (last print) reads 11/25/**61** and **64**/18/8 — the strongest
numbers on the table and **near-circular**, since it is largely "what the
print said". Treated as such.

Dropped: DBA (13pp), copper (10pp), hourly earnings, Michigan 1y
expectations, 10y breakeven level, sticky CPI, shelter CPI. Baltic Dry was
inconsistent and is parked for a logistics tab.

**Not yet used but should be:** shipping prices; the dollar's effect through
net imports into prices, beyond the simple 30-day move.

---

## 4. GROWTH — Grid axis, set by GDP  **[Stated, 2026-09-19]**

**What we track.** ISM services and manufacturing, GDPNow, and anything
else that tests well.

**What we know.** 30-day GDP windows: 121 down-state, 103 up-state, since
2008-03. Base rates 39% / 43%. Swept 30 candidates.

| driver | down → turn up? | up → turn down? |
|---|---|---|
| **ISM mfg PMI 3m chg** | 18 / **54** / 44 | **53** / 35 / 40 |
| GDPNow (level) | 23 / 41 / **56** | 54 / 30 / 45 |
| Durables 3m % | 35 / 28 / **54** | — |
| Core capex orders 3m % | 28 / 40 / **49** | — |
| Claims 13w % | 45 / 48 / **24** | — |
| CFNAI (level) | 25 / 45 / 46 | — |

**ISM mfg PMI 3m change is the top driver on this axis.**

ISM services activity reads **inverted** — rising activity has gone with
*fewer* turn-ups (44/48/24). Kept as context, and the inversion is stated
rather than quietly sign-flipped.

Dropped: copper (22pp but inverted), XLY/XLP, SPY, KRE/SPY, 2s10s.
Conference Board leading index discontinued on FRED in 2020 — ignore.

---

## 5. FUNDAMENTALS  **[Stated in code, 2026-09; grid framing from the user 2026-09-27]**

**What we track.** Damodaran's five, **all as rate of change**, because
levels are priced and the change in the level re-rates the stock. The read
throughout is the second derivative: a company going from +30% to +20%
revenue growth is decelerating while still growing fast, and that is what
separates "the theme is working" from "this company is capturing it".

1. **revenue growth** — YoY, and the change in YoY in percentage points
2. **margin** — gross and operating, in pp, and their change
3. **return to holders** — (buybacks + dividends) as a share of operating
   cash flow. A *share*, not a yield: SEC filings carry no market cap, and
   inventing one would be worse
4. **interest rate risk** — interest burden, and the refinancing wall (debt
   due within a year against cash)
5. **risk of ruin** — Altman Z'' and cash runway against burn

Source is SEC XBRL, chosen over alternatives for real reasons: FMP's free
tier gates per symbol and caps history at 5 quarters; TradingView has no
server-side API. SEC has full history, true year-on-year, every filer, no key.

Constituents hang off theme names, so the universe is inherited from what
CGI already tracks rather than a hand-kept list that goes stale.

**What we know.** The **priced-in layer** reads a multiple two ways and the
disagreement is the output:

- the user's 10×10 **grid** of justified multiples by revenue growth and
  domicile 10Y — described by the user as "a rough approximation of how much
  the PE should be based on the rev growth and interest rate… keeps a
  grounded estimate". Kept as a labelled anchor of **unknown provenance**,
  because it is the number already being reasoned with
- a **reverse DCF** solving for the growth the price actually requires

Measured: the grid is roughly **2× more generous** than the DCF, and the gap
widens with growth. Worked example — NVDA at 22% reported growth and a 28.1×
trailing multiple: the grid justifies 21.5×, the DCF implies 19.4% growth,
so the price assumes *less* growth than reported. The grid and the market
disagree by more than the grid and the DCF do.

**Limit:** individual equities are not in `price-history`, so the actual
multiple must be supplied rather than computed.

---

## 6. TECHNICALS (the tape)  **[Stated in code — "the user's own reading, in his priority order"]**

**What we track**, in priority order:

**Net new highs (NYSE highs minus lows) is primary.**
- **red** (net < 0) — after a sell-off; historically the best buying window,
  held in the names stronger than the market
- **white** (chop) — the 8 and 20 day EMAs converged; take profits near a
  cross down from the top side
- **green** (net > 0) — participation broad

The EMAs mark the transitions: a cross *down* from the top starts chop; a
cross *up* from below while net is still red is where risk goes back on.

**NCFD / MMTW / MMFI below 30** are confirmations — oversold on the 5-, 20-
and 50-day participation measures. They distinguish "hold more" from "this
is a shorter-term hold".

Thresholds are 30/70, not medians: these are oscillators and a median split
washes them out — the 30/70 cut roughly triples the drawdown spread.

**What we know — and it is a negative result, carried through honestly.**
4,969 aligned trading days, 2006-11-02 → 2026-09-22.

> **Breadth does not predict direction.** Every correlation against SPY
> forward returns is |r| ≤ 0.10 at 5, 20 and 60 days. The strongest is NNH
> 8ema at −0.10 over 20 days, and it is *negative*.

What it does price is **risk**. MMTH (200-day participation), by quintile:

| MMTH | n | ret 20d | **drawdown 20d** | ret 60d | **drawdown 60d** |
|---|---|---|---|---|---|
| Q1 (3–37) | 993 | +0.7% | **−4.8%** | +1.6% | **−8.7%** |
| Q5 (70–93) | 994 | +1.1% | **−1.9%** | +3.6% | **−3.1%** |

Forward *return* barely separates. Forward *drawdown* separates by 2.5×.
Breadth is a position-sizing input, not a direction signal, and the
dashboard says so rather than implying otherwise.

---

## 7. POSITIONING  **[Stated in code]**

**What we track.** CFTC Commitments of Traders, free and direct from the
public API. Verified against an independent dashboard: NAT GAS NYME large
specs −221,587 on 2026-09-15 against an officemate's −222K.

Every futures contract has a long and a short, so the report only says who
is on each side:

- **commercials** — producers, refiners, utilities, merchants. Hedging a
  business, price-insensitive
- **large specs** — managed money, CTAs, macro funds. Momentum; most long at
  tops and most short at bottoms, **which is the edge**
- **small traders** — non-reportable, usually with the specs

**Why extremes matter.** Specs are trend followers. When they are maximally
short, nearly everyone who wanted to sell has sold: the marginal seller is
gone, so a catalyst forces buying-to-cover into no supply.

> **Extreme positioning does not cause a reversal. It removes the fuel for
> continuation and makes the risk asymmetric.**

Read via the Williams COT index — where this week's net sits within its own
range over a lookback, 0 = most short it has ever been, 100 = most long.

Gold and silver are reported every week whether or not they are extreme: an
extremes-only view makes a contract vanish in exactly the quiet weeks when
knowing it is *not* extreme is the useful fact.

---

## What this document does not have

- **Fiscal policy has no measured contract.** Six factors have tercile
  tables built on hundreds of windows; policy has three anecdotes. That is
  the largest gap, and it is a gap in the system rather than in the writing.
- **The conditioning factors were never interviewed.** Fundamentals,
  Technicals and Positioning are marked [Stated in code] because their
  framing was captured in module docstrings during the build rather than in
  a dedicated interview. That is the user's reasoning, but recorded second-
  hand and at a moment chosen by the build rather than by him. Running
  `docs/FACTOR_INTERVIEW_PROMPT.md` on those three would upgrade them.
- **No factor has an out-of-sample test.** Every tercile table is in-sample
  over its full history. The daily pre-registered probability log in
  `regime-signals` is the forward record being accumulated to fix that, and
  it is currently 22 rows.
