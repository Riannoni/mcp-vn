# Native ChatGPT engineering team — operational design and rollout (2026-10-31)

> **DRAFT / source-only commissioning.** Read [../../AGENTS.md](../../AGENTS.md), [../DEVELOPMENT-AND-TESTING.md](../DEVELOPMENT-AND-TESTING.md), [../RENDER-HANDOFF-2026-10-31.md](../RENDER-HANDOFF-2026-10-31.md) before touching any source, model, image or game. No merge to main, GPU or production deployment is implied.

## Desired outcome, not a proxy metric

The owner expects **a reliable, playable Ash Gate browser VN**, with the actual characters and visuals matching the canonical story. The present P0 [master issue #20](https://github.com/Riannoni/web-vn/issues/20) requires a first-attempt changed-outfit Sprite and **three sequential constrained CG** with exactly correct identity, outfit, world, required prop/landmark, pose and contact. The first-acceptance sequence must be independently inspected at the original PNG pixels. Release-level `render-v1` further needs **30+ real independently human-labeled scenes**, false accept/reject/unobservable, P50/P90 total turn and stage timings, restart/retry/rollback/save preservation, and real version-fenced integration into the browser game. Source unit tests and synthetic 30-scene manifests are **not** G2/G3. Story-package imports/Kagesekai catalog are later phases, not this milestone.

**As of installation:** G2 UNVERIFIED; G3 NO-GO. No unattended agent can promote a visual gate by reading its own test results.

## Five independent responsibilities

| Team member | Cloud execution | Local checkout / focus | Current task queue |
| --- | --- | --- | --- |
| **Renderer** | Scheduled ChatGPT, hourly | `lane-renderer`: actor-prop geometry, staged masks, source grounding; reference draft PR #47 | R-01, R-02 |
| **Semantic QA** | Scheduled ChatGPT, hourly | `lane-qa`: frame/scene/actor/object/contact provenance, fail closed; base PR #49 | Q-01, Q-02 |
| **Golden benchmark** | Scheduled ChatGPT, hourly | `lane-golden`: real-vs-synthetic golden-label contract and QA metrics; base previous local B commit | G-01, G-02 |
| **E2E reliability** | Scheduled ChatGPT, hourly | `lane-reliability`: source fingerprint, idempotent publish, restart/rollback contracts; base main | S-01, S-02 |
| **Chief orchestrator/reviewer** | Separate Scheduled ChatGPT, hourly | Read all four worktrees/evidence/issue/PR; independently replay tests, accept or reject `review_pending`, replenish meaningful backlog, publish hourly status | Lead, review and incident response |

Cloud task IDs are managed through ChatGPT Scheduled UI and should be recorded with their scheduling state in the private PC run manifest (not hard-coded into production code). Technical scheduler tasks are not the same as a Codex CLI daemon.

**Persistent PC checkout root:** `~/.local/share/web-vn-native-team/run-20261031-full/`. It contains `source/` (independent Git objects), four `lane-*/` worktrees with distinct local `native-team/20261031-*` branches, `control/`, `state/team.sqlite3`, private `evidence/<lane>/`, and `logs/`. The old Codex night-runner and the previous two-worker experiment remain untouched.

## Deterministic control plane

The installed local control plane derives from the separately tested SQLite coordinator in [draft PR #51](https://github.com/Riannoni/web-vn/pull/51). The deployed evolution in this branch is `scripts/native_team/coordinator.py` plus `scripts/native_team/teamctl.py`.

- **SQLite WAL atomic claims** with 4 global active leases, one task per lane at a time, path-scope conflicts rejected, unique per-attempt fence, heartbeat and ~45-minute lease.
- **No blind retry:** an expired lease moves to BLOCKED; a new agent cannot assume the previous model/tool action did not change the checkout. Strict path scope and clean checkout preflight prevent overwriting another worker.
- **Separated evidence:** worker writes a private JSON with changed paths, red→green tests, source status, `g2=UNVERIFIED` and `g3=NO_GO`, commits locally, then calls `submit`. Result becomes `review_pending`, **not** `done`.
- **Independent review:** cloud orchestrator verifies Git diff/commit, branch lineage, source-only scope, re-runs actual negative/positive tests and validates evidence digest before `review --approve`. Rejected code is blocked, not silently accepted.
- **Bounded backlog:** eight prioritized starter jobs, separate scopes. Once work is done, same scheduled worker may claim another queued job within its turn. Hourly chief checks latest issue/PRs, dependencies and prior failures, then enqueues the next falsifiable nonduplicate task. A local process cannot invent a new high-quality research hypothesis without a model.
- **Local watchdog:** a systemd user timer runs the deterministic check around **every minute**, recording stale leases, blocked/idle lanes and a sanitized quota snapshot. It is not an LLM worker or a way to launch a new ChatGPT turn ahead of schedule.
- **Quota:** `~/.local/bin/vn-proxy-quota --provider codex --json` is read-only, and `state/quota-timeline.jsonl` records 5-hour/7-day percentages. This instrument **does not measure ChatGPT plan usage**. The first prototype showed parallel ChatGPT sessions without a visible rise in the rounded Codex gauge, not unlimited capacity.

## State diagram / lifecycle

```text
issue #20, actual SHA, current heldout evidence
                |
        chief creates task spec
                |
  [QUEUED] --atomic lane claim--> [LEASED]
      ^                            |
      |                  controlled source tests, commit,
      |                     fenced evidence submit
      |                            |
      +-- new meaningful task   [REVIEW_PENDING]
                                   |
                        independent test + diff review
                               /         \
                            DONE         BLOCKED
                              |             |
                    draft PR only      reconcile/stop,
                                      no blind resubmit

Production/GPU/image release:
  isolated GPU lease (not yet implemented)
  -> original-PNG review (G2)
  -> >=30 real human labels + E2E/restart/rollback (G3)
  -> explicitly reviewed deployment and verification
```

`DONE` here refers to one **source** task, not the master issue or a visual gate. A task may be blocked due to missing human visual evidence: do not game the gate.

## Operating commands on Xavok-PC

```bash
root="$HOME/.local/share/web-vn-native-team/run-20261031-full"
python3 "$root/control/teamctl.py" status
cat "$root/state/watchdog-latest.json"
tail -n 10 "$root/state/quota-timeline.jsonl"
systemctl --user status vn-native-team-watchdog.timer
journalctl --user -u vn-native-team-watchdog.service -n 30 --no-pager
```

All workers must use the `claim`, `heartbeat`, `submit` path in `teamctl.py`; never write task table state directly. The chief uses `review` and `enqueue` only after independent evidence. Only the owner can authorize a final merge, service restart or irreversible action.

**Stop procedure** (when explicitly requested): pause the five ChatGPT Scheduled Tasks using the Automations UI/tool; run `python3 "$root/control/teamctl.py" stop --reason 'owner request'` on PC and `systemctl --user disable --now vn-native-team-watchdog.timer`; retain all worktrees, SQLite and evidence for review. Never delete or reset another agent's dirty worktree. Old `vn-night` remains stopped independently.

## Limitations and on-call policy

The **local watchdog is continuous**, but native ChatGPT Scheduled Tasks are **hourly** and finite individual executions, not perpetual streams. Multiple open ChatGPT tasks do not establish separate quotas. A task can pause for service/platform limits, app authorization, quota or network; report PAUSED/BLOCKED and why. A stalled task with unsaved changes cannot be automatically recovered safely by declaring it complete. The chief can do reversible known safe repairs, but resource-intensive GPU/no-publish render validation needs exclusive GPU permission and actual pixel review; current implementation does **not** yet contain a GPU governor.

The full-time engineering loop is therefore **persistent, self-monitoring and hourly model-driven**, not guaranteed uninterrupted model inference until the product is good. Progress is tracked by independently reviewable artifacts, accepted G2/G3 evidence and working browser E2E, not tokens, number of commits or an unbounded count of tasks.
