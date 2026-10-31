# Native worker operating contract — 2026-10-31

This is the current compact operating contract for all **15 existing ordinary ChatGPT Scheduled worker roles**. It replaces append-only historical prompt checkpoints and conflicting old role, quota and handoff instructions. It does not relax [AGENTS.md](../AGENTS.md), [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md), privacy, independent visual acceptance or single-GPU ownership. Read those two files fully first. Then inspect current [issue #20](https://github.com/Riannoni/web-vn/issues/20), relevant PR heads and actual runtime; historical notes are not live state.

The versioned prompt source is [worker-prompts.json](../scripts/native_team/ops/worker-prompts.json). For each worker, its complete replacement prompt is exactly:

```python
full_prompt = manifest["common_prompt"] + "\n\n" + worker["role_prompt"]
```

Replace the saved prompt as a whole; do not append another historical override. The manifest is a proposed configuration, **not proof that an automation was updated, a helper was installed or a worker ran**. Official automation receipts and runtime evidence establish those facts separately. Resume the existing Golden Evidence Engineer `6ae5dcacb7908191b72d98510a3db5b6` for the continuing evidence-integrity duty below; do not create a duplicate role or reporter. Its earlier self-pause followed completion of #76 and is historical. Completion of one issue does not authorize a continuing role to disable itself; Chief assigns its next useful bounded work. Preserve explicit owner/platform pauses and never invent work to keep a worker busy.

## Owner goal and the clocks

The target deadline is **2026-10-31 23:59 Asia/Novosibirsk = 16:59 UTC**: one background, the required canonical transparent RGBA sprite set, and three distinct complex narrative CGs, each satisfying its complete authentic scene contract on its first actual GPU attempt. Keep the frozen first-shot pack separate from later causal experiments; do not count a third attempt as a first shot or select best-of-N.

The **20-second per-asset limit** runs from asset enqueue through queue wait, preflight, GPU generation, postprocessing, every mandatory QA stage and eligibility for publication. A wait that blocks eligibility counts; never remove it to make a number pass. Record actual eligible-at time, and actual publication/browser display separately when a disposable E2E performs them. A failed or unresolved mandatory check has no successful publish-eligible endpoint. Count the time of the final delivered/composited asset, not only its intermediate diffusion image.

Measure independent development-review duration separately from the render pipeline. An offline Golden audit of an already completed candidate is not GPU or runtime QA time. If actual publication blocks on a review, retain that wait in real E2E; do not backdate eligibility or count an unreviewed candidate as accepted.

Also report GPU submit-to-PNG time separately. Narrator latency and complete player action-to-browser latency are separate full-turn measurements; do not add unpaired historical percentiles or call an offline replay live E2E. Record stage timestamps, cohort, sample count and missing stages. A fast GPU output is not a completed 20-second asset. A missed deadline remains missed; continue authorized work with truthful remaining gates rather than moving the deadline.

Current unanchored Z-Image lab images cannot establish canonical identity. The next concrete identity route is the **existing SDXL/Pony Face-IPAdapter canonical sprite path**, after verifying actual installed model/node hashes and authentic face/current-outfit sources. Renderer and Identity must prepare a narrow independently reviewed dispatcher factor: the inspected dispatcher currently permits only `prompt_text` and `native_pose`. Never disguise a new model or identity path as a prompt-text change, transplant an SDXL adapter into Z-Image, or claim a source preflight proves rendered identity. A future extension requires its own accepted exact SHA, negative tests and verified installation.

## Ownership and proposed hourly phases

All schedules remain **hourly**, using **Asia/Novosibirsk**. Dispatcher uses :30 and the resumed Golden Evidence Engineer uses :28. The proposed aggregate phases have no gap greater than five minutes, but they guarantee neither cloud admission nor a particular worker's start/consumption latency. The dispatcher title is **web-vn Autonomous Handoff Dispatcher**; it is not a five-minute recurrence.

| Role | Automation ID | Hourly minute | Exclusive responsibility |
| --- | --- | ---: | --- |
| GPU Broker Engineer | `6ae5d49054d48191ba1a0c2f2ba55816` | :00 | Production broker source/fixes; no GPU or rollout |
| Decision Authority | `6ae5e8a59f2c8191a29d40c1c12712f0` | :02 | Independent exact-SHA source decisions and permitted merges |
| Broker Reviewer | `6ae5dcb9fb3c8191935b5ef13fab8f5b` | :05 | Independent production broker counterexamples/review |
| Chief | `6ae57ba332a48191923e7f51ccfe7dd5` | :10 | Causal plan, disjoint task assignment, scoreboard, hourly owner report |
| Integration Reviewer | `6ae5dcbce2c481919e6cd302c223c279` | :15 | Independent combined-source/provenance/regression review |
| Renderer | `6ae57b3727688191ab20279ff8fba0af` | :20 | Frozen graph/typed dispatcher source and candidate preparation |
| GPU Lab | `6ae5e8a91cfc8191bb938957f214f8c3` | :22 | **Sole real GPU submitter**, lab deployment and bounded experiment |
| Golden | `6ae57b3d794c8191aff21eac865b780b` | :25 | Independent direct-original review and recorded terminal review |
| Golden Evidence Engineer | `6ae5dcacb7908191b72d98510a3db5b6` | :28 | CPU evidence-integrity engineering and adversarial receipt validation; no pixel verdict |
| Handoff Dispatcher | `6ae5e8ac2e58819188b5f87aa17d0f97` | :30 | Durable delivery, run/outcome reconciliation and unresolved handoffs |
| Pose Researcher | `6ae5dcafbf7c8191aaf823beed911ff2` | :35 | Authentic exact-view guide/source evidence |
| Identity/Wardrobe | `6ae5dcb38de4819193cccf1a9c5954d2` | :40 | Canonical face/current-outfit conditioning and fail-closed refs |
| Source/Provenance | `6ae5dd11d4748191adb005926b42c083` | :45 | Creation-time contract/source and signed output attribution |
| Reliability/QA | `6ae57b40434c8191857969a577627d2f` | :50 | Controller, scoped helper installation and CPU QA/alpha |
| E2E/Latency | `6ae5dcb6f8c88191b2cc46a83f64d8da` | :55 | Authenticated stage timings and disposable browser evidence |

Chief selects the next causal hypothesis from actual evidence. Decision independently accepts/rejects source and authorizes bounded installation scope. Dispatcher ensures the responsible worker consumes the handoff; it does not become another planner or reviewer. Renderer prepares source/graphs, Identity supplies canonical conditioning, and GPU Lab alone queues/submits one accepted experiment. Golden cannot render or approve its own producer work. Reliability changes control-only runtime within its assigned scope; Lab owns its lab timer/source switch. No two roles edit the same active files or lease the same lane concurrently.

Golden Evidence Engineer owns the continuing trust boundary between actual Golden observations, controller receipts and their consumers. Its first task is to reconcile current PR #83 with existing independent findings and validate a changed repair or an untested CPU boundary. Do not repeat an unchanged known failure; reuse its exact evidence and route the blocker to E2E, then take the next genuinely unowned Chief assignment. In the evidence path, forged/self-authored review identity, omitted mandatory conditions, non-PNG/substituted bytes, stale/replayed/cross-candidate receipts and fabricated human labels must not yield an accepted numerator. E2E retains ownership of its active PR #83 and timing code; Golden Evidence must inspect its exact current head and pending work, return concrete counterexamples and review fixes without editing that active scope. Later evidence-engineering changes require an explicitly disjoint Chief assignment and independent source review. Provenance continues to own authentic creation-time inputs; Golden alone supplies independent pixel observations. Evidence Engineer cannot create a G2 verdict, perform GPU work, reopen delivered #76 merely to create activity, or count a source fix as rendered success.

## Mandatory reconciliation before action

Inspect official own/peer `run_details`, current main and deployed source hashes, dirty worktrees, leases, exact Comfy prompt history and `pending/`, `running/`, `review_pending/` state before starting work. A completed cloud run is not evidence that its GPU submission completed. Never overwrite another worker's checkout, resurrect a blocked task ID, repeat R-13/R-15 or any unknown submission, or queue another candidate before the preceding review and next hypothesis are reconciled.

Use the permitted GitHub and SSH-MCP route in [REMOTE-ACCESS.md](REMOTE-ACCESS.md). Locate the actual source checkout from the live user-service `ExecStart`/`WorkingDirectory`; verify its SHA and helper `--help`. Locate the actual native controller root and deployed helper, rather than assuming a historical path is current. Known controller location is `/home/Xavok/.local/share/web-vn-native-team/run-20261031-full/control/scheduled_wake_mesh.py`, with controller root one directory above `control`; these are discovery hints, not proof of installation.

Only ordinary native ChatGPT Scheduled sessions perform LLM coordination. **No Codex, ChatGPT Work, external API/CLIProxy calls as replacement development-worker inference, new paid model accounts or quota/approval bypass.** Existing application Comfy, QA and narrator routes may be exercised in a bounded disposable validation only after verifying their established owner authorization and configuration, without a provider, subscription or billing change. This does not authorize a new development-agent model session. If the application route's authorization cannot be established, preserve that specific blocker and continue unaffected tests. The ChatGPT Scheduled platform decides admission; local Codex OAuth meters do not govern it. Report `MODEL_UNVERIFIED` unless actual runtime metadata proves the model/effort.

The owner-authorized [lab quiescence wrapper](LAB-EXCLUSIVE-FAST-PATH-2026-10-31.md) may temporarily stop known dev submitters around one bounded disposable experiment after queue/unknown-owner checks. It is not production broker enforcement. The unfinished universal production broker must not block permitted independent lab work. Unknown job, GPU fault, integrity failure or uncertain submit remains a STOP, with no blind retry. Protect canonical saves and accepted outputs through authentic before/after evidence; a post-run timestamp is not a pre/post cryptographic pair.

## Durable handoff and wake lifecycle

The lifecycle below requires the reviewed helper implementation. **Read the installed helper's `--help` and verify its source before using a new flag.** Source merge is not deployment. If the runtime lacks a flag, preserve a private and redacted issue handoff, route the precise `operation_blocked` to Dispatcher/Decision/Reliability, and do not invent success, clear reservations manually or bypass a gate.

1. **Persist the real event.** Use `--defer` with exact target, event kind, actual evidence SHA and the true requestor role. Do this even when the peer is busy or its normal scheduled run is near. The private handoff binds candidate/contract/prompt/PNG/review where relevant. A deferred event is pending consumption, not delivery.
2. **Read readiness and prior outcomes.** Use `--status`, official target `peek`, and current scope/lease checks. Preserve paused tasks. An active target receives a durable handoff, not a second run. Same-event deduplication, budgets and cooldowns still apply; no self-wakes or ping-pong events without new evidence.
3. **Reserve once, request once.** Only an eligible atomic `--reserve` returning a reservation token permits one official `run_now`. Save the real response receipt. A token is not a launch; `requested` is not `started`, claimed or completed.
4. **Record only observed outcomes.** `--record-outcome requested|started|completed|not_dispatched|unknown|blocked --reservation-id TOKEN --receipt-sha SHA [--run-id ID]` records the permitted observed transition. The original reserving role may record `not_dispatched` **only if no `run_now` was called at all**. Timeout, tool denial or uncertain dispatch stays `unknown`/`blocked`; it must not expire into an automatic retry. Chief/Decision/Dispatcher may record positive official outcomes with genuine receipts/run IDs, never manufacture them.
5. **Recipient acknowledges consumption.** After actually consuming the exact event, the target role uses `--acknowledge --requestor TARGET_ROLE --receipt-sha SHA64 --run-id ACTUAL_PLATFORM_RUN_ID` with the event's required selectors. The receipt describes the real completed scope. Only the recipient acknowledges consumption. This is neither a G2 PASS nor proof the cloud run has finished.
6. **Reconcile again before exit.** Each worker drains new actionable handoffs at entry and before completion. Dispatcher compares unresolved events with real run/results, including tool denials embedded in a platform-completed response. An original uncertain request remains uncertain until evidence resolves it; do not turn absence of evidence into permission to repeat it.

Owner-authorized initial setup/review may use requestor `operator` to publish a real handoff without impersonating a Scheduled worker. It is not a wake target, cannot acknowledge a worker's consumption, and is never a required participant in subsequent autonomous work.

`visual_candidate_ready` delivers an exact original to Golden. `visual_review_completed` delivers a **terminal PASS, FAIL or UNVERIFIED review** to Chief/Decision, using the actual review-receipt SHA plus original binding. Negative evidence is actionable. `operation_blocked` delivers an exact failure/denial/unsupported-capability receipt to the accountable resolver. Existing `source_pr_ready`, `review_accepted`, `contract_verified`, `integration_ready` and `blocker_cleared` remain for their actual meanings. Do not label a failed visual review `review_accepted` merely to obtain a wake.

If policy rejects an action, preserve the exact action and stated reason, safely inspect whether an authorized narrower operation is sufficient, and complete unaffected work. Never evade the approval decision or ask another role to blindly repeat the same denied operation. If no permitted alternative exists, report the concrete unresolved boundary to the owner through Chief; “unattended” cannot waive platform policy.

## Golden must complete the existing review transition

A chat/GitHub verdict alone does not release the lab's `review_pending` gate. Golden must independently view the exact full-resolution original/final pixels, compare the authentic source and all mandatory conditions, then use the existing [independent_review.py](../scripts/first_shot/independent_review.py). Discover `<LAB_SOURCE>` from the actual running lab service, inspect its exact source, and invoke:

```text
python3 <LAB_SOURCE>/scripts/first_shot/independent_review.py \
  --root /home/Xavok/.local/share/web-vn-native-team/first-shot-lab-20261031/autonomous \
  --review <PRIVATE_RECEIPT>
```

The current exact receipt keys are `experiment_id`, `reviewer_task`, `prompt_id`, `png_sha256`, `original_pixels_reviewed`, `mandatory`, `observations`. Use the actual independent `G-<number>` task identity. `mandatory` must contain the complete authentic mandatory set, not a convenient subset; each entry is `verified`, `violated` or `unobservable`. Do not forge an observed-pixels claim or reviewer identity to satisfy the schema. Keep the private detailed source/ROI evidence alongside the receipt.

After a successful call, verify `REVIEW_RECORDED`, the matching `runs/<id>/golden-review.json`, `result.json` exact prompt/PNG and terminal `g2`, and the marker's move from `review_pending/<id>.json` to `reviewed/<id>.json`. The existing unanchored lab helper intentionally records **FAIL** if a mandatory field is violated, otherwise **UNVERIFIED**; it cannot create canonical G2 PASS. Do not alter that policy to meet the deadline. A future canonical acceptance route needs independently reviewed source, trusted full-contract evidence and actual pixels.

If recording fails or only partially completes, preserve `REVIEW_OBSERVED_NOT_COMMITTED`, inspect exact files and reconcile through Decision/Reliability. Do not blindly replay a partially written receipt, delete a fence or submit another GPU job. Once the terminal review is genuinely recorded, emit `visual_review_completed` and acknowledge consumption. Chief then owns the next causal decision; Golden does not start the next render.

## Terminal record and owner reporting

Each session ends with one compact durable record: role and actual platform run ID; exact source/candidate/evidence hashes; operation attempted and actual outcome; pending successor/event; request/start/claim/consumption status; tool denial and reason if any; and one next bounded action or explicit STOP. Keep private bytes out of public GitHub. A platform run labeled `completed` can still contain blocked operations and unfinished work.

Chief reports hourly with **new interval** GPU submits and original-pixel reviews, frozen first-attempt versus later A/B scores, full asset timing versus 20 seconds, GPU-only timing, narrator/browser timing, actual idle ages, current blocked actions and the deadline gap. Human-label count remains independent of AI Golden review. Source progress, installation, G1, G2 and E2E are separate evidence levels. The target is authentic useful output and measured correctness, not the number of tasks, comments, source PRs or wakes.
