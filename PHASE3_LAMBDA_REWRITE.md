# Phase 3 — Lambda rewrite for BACKTEST refresh

Status: **plan only, no code, no deployment.** Written 2026-09-07 after
the Render chunked-refresh approach (`PHASE3_PLAN.md` + its 2026-09-08
chunking addendum) was diagnosed as fundamentally blocked: production
timing tests showed every request to `cgi-api-9mim.onrender.com`
(including a bare, unauthenticated `GET /`) paying a consistent ~75s
TCP-connect delay — three back-to-back pings all landed at
connect≈75.08s, starttransfer within ~0.3s after that. This is Render's
origin not accepting the connection at the network layer, not a Python
cold-init or compute-speed problem, and it recurred on every request
tested, including immediate repeats. Root cause (dead keep-warm cron?
aggressive free-tier scale-to-zero? something else?) was not fully
pinned down — cron-job.org and Render dashboard access were needed to
finish that diagnosis and weren't available in-session. Decision: stop
fighting Render's execution environment for this workload and move the
refresh compute to a Lambda in `ap-southeast-1`, matching every other
piece of this pipeline (all 12 backend Lambdas already run there,
adjacent to DynamoDB, zero cross-region penalty).

The **read path stays on Render** — `GET /api/backtest/{compass_q}/
{grid_q}` and `.../occurrences` are cheap S3 reads that were never the
problem (the 75s issue affected every route, not just refresh, but the
refresh compute is the piece with a hard timing budget to meet; reads
have no such constraint and there's no reason to relocate them absent
further evidence they're actually broken in steady state).

---

## 1. New Lambda: `cmon-stage-backend-backtest-refresher`

**Handler logic**: a direct port of the compute already built and
verified in `api/backtest_data.py` this session — `build_regime_periods`,
`get_occurrences`, `compute_stats`, and the per-ticker fetch functions
(`_fetch_model_history`, `_fetch_price_history`) carry over essentially
unchanged. What's dropped: the chunking/manifest/hash-sharding machinery
(`chunk_for_ticker`, `refresh_chunk`, `refresh_tickers`, the
`Cache/backtest/manifest.json` coordination layer) — none of it is
needed once compute runs in-region with no Cloudflare/Render timeout
ceiling to work around. What's kept from the chunked version regardless
of chunking: the **per-ticker try/except resilience** (one bad ticker
or one AccessDenied/throttle on a single symbol shouldn't kill the
whole run) — this was a real bug caught and fixed during the chunked
build's testing (Step E.2) and the fix is orthogonal to chunking, worth
carrying forward unconditionally.

No HTTP wrapper, no FastAPI, no auth token — Lambda-invoked (EventBridge
schedule), not HTTP-invoked. This also means it does **not** need the
`sssiutils` layer other backend Lambdas carry (that's for `Logger`/
`DynamoDB` helper classes `api/backtest_data.py` doesn't use — it uses
plain `logging` and raw `boto3`) — just the default Lambda Python
runtime's bundled `boto3`. Zero custom layers needed. Smaller, simpler
deployment package than any other Lambda in this project.

**Full-universe, single-shot, no chunking**: local full-refresh measured
127.56s wall-clock for all 129 tickers (2026-09-07, this session,
against production DynamoDB from a laptop over ordinary internet). A
Lambda in `ap-southeast-1` running right next to DynamoDB should be at
least as fast, plausibly faster (AWS internal network vs. laptop→ISP→
AWS path) — the "~2-3 min" estimate in your framing is a reasonable,
slightly conservative target. Recommend configuring the Lambda's own
timeout well above that (10 min) for safety margin on a first real run,
and checking actual CloudWatch duration after that run to right-size
it down if desired. Lambda memory: not measured this session (local
process peak RSS wasn't profiled) — start at 512MB, check CloudWatch
`Max Memory Used` after the first invoke, adjust if needed.

**Storage — recommend the simplification to a single blob**, per your
framing: `Cache/backtest/occurrences.json` containing
`{schema_version, last_refreshed_at, tickers: {ticker: {group, combos}}}`
— the same shape already used inside each chunk file, just unchunked.
Reasoning: the chunked design's whole purpose was fitting inside
per-request timing ceilings that don't apply to a Lambda; with a single
writer and no partial-refresh-under-time-pressure requirement, the
manifest/sharding coordination layer is pure complexity with no
remaining benefit. One tradeoff worth naming: the *occurrences* endpoint
(single ticker) currently reads only the one chunk containing that
ticker (targeted, cheap); with a single blob it reads the whole ~3.9MB
object every time. Still fast in absolute terms (S3 GetObject of a few
MB is typically ~100-300ms), just no longer as targeted — acceptable
given the size, not worth preserving chunking for.

**EventBridge schedule — recommend `cron(30 3 * * ? *)` (03:30 UTC)**,
matching your proposal. Checked against the full existing schedule from
this session's context: 00:05 (price/fred/us-yield/gdp updaters), 00:10
(yahoo-finance), 00:15 (inflation-rate), 00:20 (derived-metrics), 00:25
(compass/grid/clock model updaters), 00:30 (dashboard-generator, MTD
report), 00:55 (regime-signal-updater / Markov), 01:00 (regime-outcome-
backfill), 02:15 (alpha-vantage-updater), 23:59 (crypto-price-updater).
03:30 sits over an hour clear of the last (alpha-vantage at 02:15) and
well ahead of the next day's 00:05 cycle — no collision, and it runs
after every price/model-update Lambda has already landed that day's
data, so the backtest refresh always sees the freshest possible regime
periods and prices.

**IAM role** (new, least-privilege, matching the pattern already used
for `regime-signal-updater`/`regime-outcome-backfill`):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "QueryPriceHistory",
            "Effect": "Allow",
            "Action": "dynamodb:Query",
            "Resource": "arn:aws:dynamodb:ap-southeast-1:369568916817:table/cmon-stage-backend-price-history"
        },
        {
            "Sid": "QueryModelHistory",
            "Effect": "Allow",
            "Action": "dynamodb:Query",
            "Resource": "arn:aws:dynamodb:ap-southeast-1:369568916817:table/cmon-stage-backend-model-history"
        },
        {
            "Sid": "WriteBacktestCache",
            "Effect": "Allow",
            "Action": "s3:PutObject",
            "Resource": "arn:aws:s3:::cmon-stage-backend-369568916817-ap-southeast-1-reports/Cache/backtest/*"
        }
    ]
}
```

No `s3:GetObject` needed — a full-rebuild-every-time design never reads
its own prior output before overwriting it. Standard Lambda execution
role trust policy + `AWSLambdaBasicExecutionRole` (CloudWatch Logs) on
top, same as every sibling Lambda.

**Deployment discipline — matches Plan 3A exactly**: publish-version
before every `update-function-code`, `live` alias for the EventBridge
target (rollback = repoint the alias, not redeploy), Lambda resource
policy scoped to `events.amazonaws.com` with a `SourceArn` condition
tied to the new rule (same shape as every existing schedule in this
project).

---

## 2. Render-side changes — AFTER the Lambda ships and verifies, not before

- Delete `POST /api/backtest/refresh` from `api/main.py` entirely
  (`require_refresh_token`, the endpoint handler, the `Body` import if
  nothing else uses it).
- Delete `refresh_chunk`, `refresh_tickers`, `_refresh_tickers_into_chunk`,
  `chunk_for_ticker`, `CHUNK_COUNT`, and the manifest-handling functions
  (`_read_manifest`, `_write_manifest`, `_chunk_key`) from
  `api/backtest_data.py`.
- **Rewrite** (not "leave unchanged" — the storage format is changing)
  `build_table_response` and `build_occurrences_response` to read the
  single `Cache/backtest/occurrences.json` blob instead of manifest+
  chunks. The endpoint *signatures* (`GET /api/backtest/{compass_q}/
  {grid_q}`, `.../occurrences?ticker=X`) and response *shapes* stay
  identical — only the internal S3 read path changes. Flagging this
  explicitly since "keep the GET endpoints unchanged" could be misread
  as "don't touch this file" — the public contract is unchanged, the
  implementation underneath necessarily isn't.
- Revert the `QueryPriceHistoryForBacktest` statement just added to
  `cgi-vercel-render-svc`'s IAM policy (this session, via
  `aws iam put-user-policy`) — Render no longer touches `price-history`
  once refresh moves to the Lambda. Least-privilege improvement:
  removes an access grant that becomes unused dead weight.
- Delete the `REFRESH_TOKEN` env var from Render's dashboard — no
  endpoint checks it anymore once the refresh route is gone.
- No cron-job.org cleanup needed — per your own note, those jobs were
  never actually configured (Step 4's production timing gate failed
  before Step 5 was reached), so there's nothing to delete there.

## 3. Migration approach

1. Ship the Lambda, verify it independently (section 4) — **the old
   chunked Render refresh path stays as dead code, untouched, while
   this happens.** It was never wired to cron-job.org, so it's not
   actively running against anything; no risk in leaving it in place
   temporarily.
2. Once the Lambda is proven (real S3 output verified correct), deploy
   the Render-side deletions (section 2) as a **separate commit**,
   pushed only after step 1 is confirmed good.
3. **Never run both write paths at once.** The chunked Render refresh
   and the new Lambda write to different S3 keys by design (chunks+
   manifest vs. single blob), so there's no literal collision risk, but
   running both would mean two divergent, stale-relative-to-each-other
   datasets and double the AWS spend for the same result — the old path
   should be fully decommissioned once the new one is trusted, not kept
   "just in case."
4. Cleanup: after cutover, delete the orphaned
   `Cache/backtest/manifest.json` and `Cache/backtest/occurrences_
   chunk_{0,1,2,3}.json` objects from S3 — they'd otherwise sit as
   stale, unreferenced data indefinitely.

## 4. Verification plan

Same discipline already used for the MACRO port and the FX swap canary
this session — read-source-first, verify against ground truth, don't
assume:

1. **Manual Lambda invoke** (`aws lambda invoke`, not waiting for the
   03:30 UTC schedule) — confirm it completes within its configured
   timeout, check CloudWatch Logs for per-ticker failures (should be
   zero against current data, matching the 129/129 clean result already
   achieved locally this session).
2. **Verify S3 output shape directly** — `schema_version` present and
   matching what the Render read code expects, `last_refreshed_at` is a
   fresh ISO timestamp, `tickers` contains all 129 `BACKTEST_UNIVERSE`
   symbols, each with a `group` and non-empty `combos` for at least the
   currently-live regime combo.
3. **Hit Render's (updated) read endpoints** against the Lambda-written
   cache — confirm `/api/backtest/2/4` and `.../occurrences?ticker=SPY`
   return data, with `last_refreshed_at` matching the Lambda's write
   time.
4. **Streamlit cross-check, same rigor as this session's chunked-version
   test** — feed identical fetched data into both the original pandas
   `backtest_engine.py` and the Lambda's ported logic within one script
   (eliminates timing-skew as a variable, the way the earlier 39-mismatch
   red herring was resolved down to 2 negligible floating-point-rounding
   differences out of ~774 compared values). Re-run for at least the
   current live regime combo (compass=2×grid=4) plus one or two others.

## 5. Risks + open questions

- **DynamoDB read cost/capacity**: pulling full history for 129 tickers
  once daily via unbounded Query — `price-history`'s billing mode
  (on-demand vs. provisioned) wasn't checked this session. Worth
  confirming before the first real run so a provisioned table with low
  RCU doesn't get throttled by a burst of 129 sequential full-table
  scans landing in a ~2-3 minute window.
- **No chunking = single blast radius.** If the Lambda fails partway
  (timeout, OOM, an unhandled exception outside the per-ticker try/
  except), the whole day's refresh doesn't happen at all, versus the
  chunked design's partial-failure isolation. Mitigate with a
  CloudWatch alarm on Errors/Duration for this Lambda, matching the
  "one alarm per provider Lambda" pattern already established for the
  other 7 alarmed Lambdas in this project — not yet decided whether to
  add here, flagging as an open question.
- **Ad-hoc/partial refresh capability is dropped**, not preserved. The
  chunked version's `tickers=[...]` ad-hoc path (used for one-off fixes,
  like the SPY/QQQ tests this session) has no equivalent in a bare
  Lambda-invoked, no-event-payload design. If a future one-off ticker
  fix is ever needed, the precedent from this project is a local
  windowed-pandas script writing directly to the target table (same
  technique as the 2026-09-01 SPX derived-metrics repair) rather than
  routing through the Lambda — worth deciding explicitly rather than
  assuming, since `derived-metrics-updater`'s own `lambda_handler`
  ignoring its event payload was flagged as a real, still-open bug
  earlier in this project; this new Lambda should not repeat that
  pattern by accident if partial-refresh-via-payload is ever wanted
  later. For now, the plan is full-rebuild-only, by design, not by
  oversight.
- **Root cause of Render's ~75s connect delay is still not fully
  confirmed** (needs the cron-job.org execution history and Render logs
  this session couldn't pull). Moving refresh off Render sidesteps the
  problem for that one workload but doesn't explain it — if it's a dead
  keep-warm cron or a Render-side outage/misconfiguration, it may still
  be silently affecting the read endpoints or other Render-hosted
  routes (LIVE, MACRO) that this session didn't re-test after the
  finding. Worth a quick follow-up check on those once this settles,
  separate from the Lambda work.
- **Estimated LOC + effort**: Lambda handler + compute (~150-180 LOC,
  smaller than the current `backtest_data.py`'s ~430 lines since the
  chunking/manifest layer is removed rather than added-to) + IAM role/
  policy (~30 lines JSON) + EventBridge rule (a few CLI/console steps,
  not LOC). Render-side changes are net-negative LOC: removing the
  refresh endpoint and chunking machinery (~200+ lines deleted) while
  rewriting the two read functions to the simpler single-blob format
  (~60-80 lines, smaller than their chunked equivalents). Most of the
  hard part — the occurrence/stats computation logic itself and its
  correctness verification against Streamlit — is already done and
  tested this session; this is a relocation and simplification, not new
  algorithm work. Estimate: one build session, comparable to or faster
  than the original chunked build.
