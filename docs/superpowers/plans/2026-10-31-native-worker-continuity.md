# Native worker continuity implementation plan

**Goal:** repair observed autonomous-worker handoff defects without weakening visual evidence, quota enforcement or single-GPU ownership.

**Authorization and scope:** the owner requested this audit and necessary corrections, with no dependency on the interactive chat. Keep native Scheduled workers, the existing SSH route and deterministic host controller. Do not enable Codex, Work or paid model APIs. Changes affect worker coordination and its operating contract; they do not certify render quality or deploy product code.

## Evidence and design

- At `0c5fb609`, `coordinator.claim` permits disjoint R/Q/S tasks to hold leases in the same lane worktree. Enforce one active lease per lane transactionally, including lane-inferred calls.
- `scheduled_wake_mesh` inserts permanent event deduplication before `run_now`. Separate event identity from delivery attempts. Preserve legacy reservations as unknown. Add token-fenced outcomes and a durable deferred-event outbox. Only a positively recorded **not dispatched** attempt may be reserved again; accepted, uncertain or policy-blocked attempts never expire into automatic retries. Retain all attempts for rate accounting.
- Golden must commit its SHA-bound independent review through the existing review API and verify `review_pending → reviewed`, including FAIL/UNVERIFIED, before a terminal-review handoff. Busy target roles need durable handoffs, not discarded notifications.
- Replace contradictory appended prompts with one current contract and per-role ownership. Preserve 14 enabled workers; move Dispatcher from :42 to :30, rename it honestly, use Asia/Novosibirsk and retain hourly recurrence. This does not promise continuous model availability.

## Execution and verification

- [ ] Reproduce same-lane parallel claims and add isolation/concurrency regressions; implement the minimal coordinator guard.
- [ ] Add wake lifecycle regressions: explicit pre-dispatch failure recovery, unknown/accepted/policy-blocked no retry, stale token/owner refusal, retained retry budgets, deferred busy events, concurrent reservations and legacy migration.
- [ ] Implement backward-compatible wake CLI (`--defer`, `--status`, token-fenced `--record-outcome`) without network/model calls.
- [ ] Replace obsolete operating instructions and role prompts; require a real canonical-reference sprite candidate before more unrelated text-only pose attempts.
- [ ] Independently review changed code and run controller/first-shot regressions and relevant syntax checks. Keep unrelated failures visible.
- [ ] Publish the reviewed branch/PR, install only controller files with verified backup and hashes, update existing automation prompts/schedules, then inspect a real handoff and recorded runtime state.

## Review focus

Legacy unknown submissions must not be retried. Delivery completion is not artifact acceptance. A denied action is not silently rerouted. A busy peer must not lose an event. Same-lane worktrees must remain exclusive while independent lanes can progress. GPU first-shot and complete generation timings stay distinct, and research attempt 3 cannot become first attempt 1.

## Acceptance

Control-plane tests and live installation prove coordination changes only. Today's product milestone remains a frozen canonical background + sprite set + three distinct complex CG scenes, first attempts, every mandatory visual fact independently verified and complete per-image generation at most 20 seconds. Record full browser-turn latency separately. If the deadline is missed, keep working and report the miss honestly; do not lower QA or rename an old experiment as a new first-shot success.
