# Study backlog

Proposed studies from Video intake (`/video-to-study`) and elsewhere. Arvin approves a row; the CGI chat builds it in
`research/<name>/` with a self-test harness and RESULTS.md. Status: proposed / approved / done / rejected. Nothing is promoted into CGI without out-of-sample improvement over the simple baseline.

| Date | Source | Claim | Honest prior | Status | Result |
|---|---|---|---|---|---|
| 2026-10-04 | Arvin (Kalman idea) | A latent factor beats the Markov base rate as P(flip) | Likely null | done | No edge (`latent_state`) |
| 2026-10-05 | Gaussian process video | Better probability models for CGI | Mixed | done | Liquidity "today" figure has an edge; growth/inflation don't (`probability_check`) |
| 2026-10-08 | Medallion video | Calm/stormy HMM risk state beats vol sizing | Likely null | done | No; plain vol sizing cuts drawdown a lot (`vol_state`) |
| 2026-10-08 | Deferred | Regime best/worst-20 lists predict the next episode | Likely null | done | Coin flip (`rank_oos`) |
| 2026-10-08 | Medallion video | Peer-overshoot reversion pays after costs | Weak | done | ~0.1%/event, decaying (`peer_reversion`) |
| 2026-10-08 | Markets Unscripted (Shapiro) | COT extremes + price confirmation, and how long until a turn | Weak | done | Slow ~0.8% fade; confirmation doesn't help; don't fade at ADX > 30 (`cot_turns`) |
| 2026-10-09 | Luke Gromen Q&A | Oil and dollar up together -> equities and Treasuries weaker over 4-8 weeks | Likely null (inside the liquidity figure) | rejected | Skipped by Arvin 2026-10-09: the liquidity figure likely already covers it |
