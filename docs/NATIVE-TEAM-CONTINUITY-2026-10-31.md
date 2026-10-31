# Native Team continuity V8 — 31 October 2026

## Goal and honest operating contract

User target: useful web-vn P0 source development while allowance is available, with **actionable ready-to-claim idle <=600 s**, aspirational <=300 s, and no fabricated work or reduced quality. This is a **measured SLO, not a platform-guaranteed SLA**: ChatGPT scheduled tasks can be hourly and an extra `run_now` has no guaranteed start time. Work and Codex share included agentic usage allowance; the local Codex OAuth meter is **not** an authoritative Work usage meter. No paid API, OAuth bypass or silent model switch is permitted.

The automation may be idle legitimately when there is no meaningful approved independent P0 source task, no permitted quota, missing GPU/human G2 evidence, an unresolved dependency, or an unsafe state.

## Installed architecture (Bazzite Xavok PC)

- Immutable source-only control-root: `~/.local/share/web-vn-native-team/run-20261031-full`.
- One-minute `systemd --user` watchdog and user linger. Only local SQLite WAL and deterministic Python code; **no LLM/model/network/GPU calls**.
- `control/task_catalog.py` reads `control/task-catalog.json`: curated exact source-only P0 specs, path whitelists, idempotent task IDs, validated deps, at most two pending jobs per lane. `BEGIN IMMEDIATE` serializes concurrent enqueue with Cloud Chief. New specs must be separately grounded in observed P0 issues and reviewed handoffs; never invent tasks for uptime.
- `teamctl.py enqueue` is transactional, so a worker cannot claim a half-populated record. `coordinator.py` and `wake_guard.py` fence overlapping blocked and review-pending paths but allow **independent non-overlapping work** to proceed. An unapproved dependency is never considered done.
- `control/lease_recovery.py`: the owning worker may explicitly quarantine a definitively failed leased task using its exact owner/fence and specific diagnostic reason. It never retries automatically. Reboot and expired leases remain fail-closed.
- `control/idle_metrics.py`: actionable idle starts after the task is enqueued **and** all its dependencies have an actual independent `review_pass`; blocked/conflicting scopes are excluded. Separately exposes `review_wait_seconds` and a `planning_deficit_seconds` when a lane has no backlog. Planning deficit is **not** misreported as a ready-task SLA failure.
- `control/quota_gate.py` permits extra wake requests only with a fresh (<180 s) local sample and under 75% of either 5h or 7d Codex OAuth windows; official Work usage and plan limitations can additionally refuse. The old per-lane 1/h guard was replaced with bounded 120 s cooldown, 6/lane/hour, 20 worker/hour combined and 12 Chief/hour.
- Cloud Chief retains the **independent reviewer** role, running 2–3 safe, bounded read-only test worktrees in parallel and acknowledging exact SHA + evidence. It plans *new meaningful* P0 work only when the curated or recently completed handoff leaves a genuine gap. Other cloud workers use the official `Automations.run_now` path when eligible and recover their own failed leases.

Do not mistake a submitted `run_now` for a real start; confirm the cloud recorded run and the SQLite `claimed` event.

## Verified rollout and tests

- Installed only the **local controller** on Xavok PC; no product deployment, direct Comfy submit, game saves or accepted assets were changed.
- `R-07` (no authentic creation-time receipt) was manually quarantined **after** independent confirmation that its cloud session ended, the relevant handoff said BLOCKED, and its git worktree was clean. No replay.
- Chief independently approved Q-06, S-07, S-08 and S-09 during observed continuation; R-08 and Q-07 reached `review_pending`, G-06 took a real lease, and S-09 progressed. R/Q/G extra runs were confirmed as requested, then actual claim rows appeared.
- One earlier observed S-08 enqueue→claim was 347 s. This **does not** establish a 24/7 600 s upper bound.
- Isolated source checkout of this PR branch: `python3 -m unittest discover -q -s scripts/native_team/tests -p 'test_*.py'` — **70 tests passed** on 2026-10-31. Some Python ResourceWarnings from fixture DB cleanup, not failed assertions.
- Do not confuse source-only approval with render quality. **G2=UNVERIFIED, G3=NO_GO** until independent original-pixel and 30+ human-labeled E2E gates are passed.

## Incident diagnosis / rollback

1. On PC, inspect `control/teamctl.py status`, `state/wake-ready.json`, `state/catalog-latest.json`, `state/quota-latest.json`, `state/team.sqlite3` PRAGMA quick_check, and `systemctl --user status vn-native-team-watchdog.timer`.
2. When a worker is leased after its cloud session ended, do **not** blindly reclaim or repeat it. Check exact `owner`, `fence`, original evidence and whether any external GPU job might exist. The owner-fenced recovery command can quarantine it. If unknown, leave blocked for investigation.
3. When `review_pending` accumulates, have Chief independently verify exact submitted SHA, provenance, negative regression and evidence. It can run *independent read-only* checks concurrently; approvals themselves remain serialized SQLite CAS.
4. If no curated task is runnable, distinguish blocked dependency, no meaningful backlog and exhausted quota; do not report all as SLA breach.
5. Backup-first live controller files are available alongside each touched file with `.before-*20261031` suffix. Roll back **only this controller** with stopped timer and verified DB state. Never revert product/runtime assets to debug a source-only dispatch issue.

This PR is a source checkpoint; merging is not a production deployment. The official scheduled-task platform does not provide a hard external 5–10-minute start SLA; an always-on paid/API or local inference executor would have a separate quota and quality tradeoff. No such executor was silently enabled.
