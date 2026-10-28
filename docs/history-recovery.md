# Settled market history recovery

Every paper-engine run checks that the benchmark cache contains the expected
settled session before the existing reliability preflight. A missing or stale
cache triggers one two-year universe refresh, bounded to 20 minutes. Explicit
manual refreshes and the post-close schedule still force a refresh.

A partial current-day benchmark bar does not satisfy this check. If the expected
session remains absent, execution stops. The portfolio, ledger, checkpoint and
entry-risk checks remain mandatory. This refresh does not reset capital or
relax paper trading rules.

Validated refreshed market files are saved before the execution preflight so an
unrelated execution failure does not discard recovered data. Fresh caches skip
the download. Scheduled delivery can still be delayed by GitHub; this change
recovers stale market data when a run actually starts, rather than guaranteeing
delivery time. Checkpoints record only the latest settled benchmark bar; an
unfinished current-day candle is excluded from freshness evidence. Render reads
that corrected shared evidence without requiring a dashboard deployment.
