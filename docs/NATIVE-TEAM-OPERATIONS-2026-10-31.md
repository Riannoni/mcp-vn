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

## First full four-lane cloud cycle — verified 2026-10-31 12:35 Asia/Novosibirsk

**Execution:** Four separate native ChatGPT Scheduled Tasks completed concurrent runs, working on **four independent local PC Git worktrees** via SSH-MCP. Local user-systemd minute watchdog remained active, old Codex night agent inactive. Four lanes developed two source-only tasks each (R-01/02, Q-01/02, G-01/02, S-01/02). Each created a local commit and private evidence (no GitHub pushes).

**Independent chief review:** a fifth scheduled native ChatGPT task was run immediately and independently reviewed all **8/8** source-only outputs, re-ran an aggregate **165 targeted Python tests** on the PC, checked commit SHA/path scope and accepted each as source task DONE in SQLite; original red regressions verified for at least R-01/Q-01/G-01. The reviewer then enqueued **R-03, Q-03, G-03, S-03** based on actual heldout blockers. Thus the first complete workflow **claim → actual source changes → local testing → review_pending → independent review → DONE → next meaningful task** is evidence-backed. Final check 12:35 showed **4 pending, 0 leased, 0 blocked**. The next model work starts on the next hourly ChatGPT schedule, while watchdog remains one-minute. Beware the wider historical reliability test suite still has **1 unrelated failing test** (`test_bounded_retry_moves_on`), not considered fixed by the targeted 31/31.

| Lane | Latest local SHA | Independent source tests | Next milestone |
| --- | --- | --- | --- |
| Renderer | `46977a1` | 50/50 targeted | R-03 bind proposed hand plan to immutable source PNG |
| QA | `8f38189` | 49/49 targeted | Q-03 exact PNG SHA shadow evidence |
| Golden | `064b999` | 35/35 targeted | G-03 P50/P90 complete turn and stages |
| Reliability | `f8d9ab7` | 31/31 targeted | S-03 exclusive GPU preflight, source-only |

**Runtime:** GitHub `main` `5e4e0bf`; production game worker/vision/Comfy and existing proxy remain active, LAN game HTTP 200 at last chief check, Comfy queue idle. No accepted live image replaced, no GPU commands issued, no deployment or merge. The previously documented held-out wooden box had independently measured width/shoulder ratio **1.0668 > 1.0**, so **G2 remains UNVERIFIED and G3 NO-GO**. Source-only approval is never release acceptance.

**Quota:** During four parallel native ChatGPT sessions the whole-percent Codex OAuth gauge after its natural 5-hour reset remained **0% / 36%** (5h used / 7d used). This gauge cannot track actual ChatGPT plan usage, and no unlimited capacity claim is justified.

**Five cloud schedules** currently active (all recurring hourly):
- Renderer `6ae57b3727688191ab20279ff8fba0af`
- QA `6ae57b3a03a48191889e3b0073c8e359`
- Golden `6ae57b3d794c8191aff21eac865b780b`
- Reliability `6ae57b40434c8191857969a577627d2f`
- Chief `6ae57ba332a48191923e7f51ccfe7dd5`

These use five of the available scheduled-task slots. Cloud execution depends on plan quota, connected SSH/GitHub app availability and platform delivery. If any task fails, the chief must state the exact failure; local minute watchdog cannot summon another model turn. All source code remains local PC worktrees and this coordination draft PR; production release still requires separately verified real first-shot G2 and multi-scene G3.
