# Theme legs: audit and extension (2026-10-09)

Run read-only first; this file is the record of what was applied. Prices for the test: one consistent free
source (Yahoo daily closes, 2005+) for every leg and candidate; theme state recomputed with `themes_data._run`.
Redundancy: correlation of 20-day relative strength vs SPY (Oct 2021+), ff53fbc method. Rules: keep if < 0.90 vs every
existing leg and >= 400 days overlapping SPY; one theme per leg; no leveraged products; STANDING untouched.

## Fixes

- URA -> URANIUM in uranium / nuclear (URA last bar 2026-09-01, no registry row; URANIUM is the live copy, correlation 1.00).
- BOTZ (AI) and MOO (agriculture) had no price rows: onboarded.
- KBWR does not resolve: not used.

## Existing themes

| Theme | Added | Dropped (max corr) | Lead before -> after |
|---|---|---|---|
| AI | ARKQ (0.6), CHAT (0.82), THNQ (0.87) | — | AIQ -> AIQ |
| semis / memory | XSD (0.89) | PSI (0.95) | SMH -> SMH |
| cloud / software | IGV (0.85), ARKW (0.79) | XSW (0.91), CLOU (0.93) | SKYY -> SKYY |
| cyber | — | BUG (0.92), IHAK (0.9) | CIBR -> CIBR |
| copper | — | — | none running -> none running |
| gold | — | RING (0.99) | none running -> none running |
| silver | — | SILJ (0.97) | none running -> none running |
| steel / metals | PICK (0.84), REMX (0.6) | — | none running -> none running |
| uranium / nuclear | NUKZ (0.84) | URNM (0.94) | none running -> none running |
| power / grid | — | — | none running -> none running |
| defense | SHLD (0.69), ARKX (0.64) | PPA (0.95) | none running -> none running |
| energy: upstream | — | FCG (0.98), XES (0.98), PXE (0.99) | IEO -> IEO |
| energy: refiners | — | — | CRAK -> CRAK |
| energy: midstream | AMLP (0.87), EMLP (0.87) | ENFR (0.99) | none running -> none running |
| biotech / healthcare | XBI (0.8), ARKG (0.53), IHE (0.87), IHF (0.66), XPH (0.7), XHE (0.74) | IYH (0.99) | IBB -> ARKG |
| banks | — | KBWB (0.92), IAT (0.98) | none running -> none running |
| retail / consumer | — | PEJ (own theme) | none running -> none running |
| homebuilders | — | ITB (0.97) | none running -> none running |
| real estate | REZ (0.88) | MORT (own theme) | none running -> none running |
| shipping / logistics | BOAT (0.84) | JETS (own theme) | SEA -> BOAT |
| infrastructure | PAVE (0.22), IFRA (0.67) | — | none running -> none running |
| EV / battery | DRIV (0.78) | LIT (0.91) | none running -> none running |
| solar / clean | QCLN (0.76), PBW (0.73), PBD (0.85) | — | none running -> none running |
| crypto equities | ARKF (0.77), WGMI (0.86) | BKCH (0.93) | none running -> none running |
| China | CQQQ (0.87) | MCHI (0.99) | none running -> none running |
| Japan | — | — | DXJ -> DXJ |
| Korea / DRAM | — | — | EWY -> EWY |
| agriculture | — | VEGI (0.94) | none running -> none running |

Flag: biotech lead moves IBB -> ARKG (onset 2026-04-10, late); shipping lead SEA -> BOAT (onset 2025-12-01, late).

## New themes (discovery layer; promotion stays your monthly decision)

| Theme | Legs | Dropped | Lead now |
|---|---|---|---|
| insurance | KIE | KBWP (0.93 vs KIE), IAK (0.96 vs KIE) | none running |
| capital markets / brokers | IAI, KCE | — | none running |
| private equity / alternatives | PSP | — | none running |
| staples / food | XLP, PBJ | — | none running |
| leisure / travel | PEJ, JETS | — | none running |
| social / media | SOCL, XLC | — | none running |
| gaming / esports | ESPO | — | none running |
| mortgage REITs | MORT | — | none running |
| environmental / water | EVX, PHO, CGW | — | none running |
| cannabis | MJ | — | none running |
| Israel tech | IZRL | — | none running |
| innovation / disruptive growth | ARKK | — | ARKG |
| industrials (broad) | XLI | — | none running |
| materials (broad) | XLB | — | none running |
| Magnificent 7 | MAGS | — | MAGS |
| coal / lithium / nickel | COAL, LITHIUM, NICKEL | — | none running |

## Onboarded (27 tickers, not previously stored)

AMLP, ARKX, BOAT, BOTZ, CGW, CHAT, CQQQ, DRIV, EMLP, IFRA, IGV, IHF, MOO, NUKZ, PAVE, PBW, PHO, PICK, QCLN, REMX, REZ, SHLD, THNQ, WGMI, XBI, XPH, XSD

Each: TradingView symbol via scripts/build_tv_symbols.py, metrics-source row (marketstack), backfill (Marketstack;
TradingView bars where Marketstack lacks history), HUD_GROUPS entry with a rationale comment.

## Caveats

- Correlations use Yahoo closes; production uses Marketstack closes (same exchange prints).
- 'Lead' before/after recomputed from the same source, so production onsets may differ by a few days.
- Theme count rises from 28 to 44; all new themes are discovery-only.
