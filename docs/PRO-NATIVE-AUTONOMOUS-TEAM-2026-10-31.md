# web-vn Pro / ChatGPT-native autonomous development v16 — 2026-10-31

**State of the system, not a claim of game readiness.** Mandatory reading order: root `AGENTS.md` then `docs/DEVELOPMENT-AND-TESTING.md` in full. Also `docs/AUTONOMOUS-FIRST-SHOT-CYCLE-2026-10-31.md`, `docs/FIRST-SHOT-GPU-ASSAULT-2026-10-31.md`, `docs/RENDER-HANDOFF-2026-10-31.md` and [P0 issue #20](https://github.com/Riannoni/web-vn/issues/20). This file supersedes the **obsolete 5-active-task cap and old role allocation**, not G1/G2/G3, private assets, exact-source requirements, or GPU ownership.

## What Pro actually enables

OpenAI's current Scheduled Tasks documentation states an **active task limit of 15 for ChatGPT Pro**, versus 5 for Plus: https://help.openai.com/en/articles/10291617-scheduled-tasks-in-chatgpt . This Pro account successfully created **seven additional ordinary ChatGPT Scheduled worker tasks**, confirming the former five-slot obstacle is gone. Tasks run at most hourly under their saved schedules. **The model and reasoning effort of Scheduled worker runtimes are not exposed by the current automation connector**; prompts cannot enforce Astra or Extra High and must log `MODEL_UNVERIFIED` absent actual runtime metadata.

User preference and budget restriction: **NO Codex CLI, NO ChatGPT Work, NO paid API, NO CLIProxyAPI model requests**, even when agents could use them. The prior local four-subagent GPT-6 Astra High research audit was manually stopped after the Codex OAuth proxy reported 5h `100%`; it was expensive and never finished. Do not re-enable or silently switch to local Codex/Work. All substantive LLM work is via **native ChatGPT Scheduled Tasks** and available connected GitHub / SSH-MCP actions. The host-side minute timers, SQLite, Comfy queue and deterministic Python tests are not billed model tasks.

**Dots as an optional future Chief:** Official docs: https://help.openai.com/en/articles/20001530-getting-started-with-your-dot and https://openai.com/index/introducing-dots/ . A Dot runs on GPT-6 Astra, has its own cloud computer and can retain an always-on project goal. Its conversation usage is separate from ordinary ChatGPT limits, but deep Work/Codex tasks created by a dot consume those allowances, and the first dot includes a finite deeper-work allowance. Eligibility is gradually rolled out to adult Pro users **outside the EEA, UK and Switzerland**. A marketing card does NOT prove account entitlement. `https://chatgpt.com/dots` is the safe availability check. No Dot is provisioned/assumed, and the project must not depend on it. If a Dot becomes available, use it initially for **non-Work, non-Codex reporting/coordination** and preserve the existing real source/GPU acceptance gates.

## Live native ChatGPT team and isolated ownership

All of these are normal Scheduled chat automations, **not** Codex or Work. On 2026-10-31, **12 enabled** worker slots (out of documented Pro 15), with old hourly read-only reporter PAUSED. Chief gives hourly owner updates; never create duplicate reports.

| Duty | Scheduled automation ID | Independently owned work / gate |
|---|---|---|
| **Chief** | `6ae57ba332a48191923e7f51ccfe7dd5` | P0 decision, repo/PC state, independent SHA review, task issuance, downstream wake, final stop/go, hourly progress |
| **GPU Renderer** | `6ae57b3727688191ab20279ff8fba0af` | one-factor GPU candidate, exact prompt/PNG/workflow, G1, no self-G2 |
| **Golden independent pixel review** | `6ae57b3d794c8191aff21eac865b780b` | authentic original pixels + canonical references, G2 negative/positive; no GPU submit |
| **Reliability + current QA** | `6ae57b40434c8191857969a577627d2f` | live controller/host failures, CPU QA; avoid overlapping new dedicated workers |
| **GPU Broker Engineer** | `6ae5d49054d48191ba1a0c2f2ba55816` | PR #78 single GPU admission broker, cutover safety and bypass prevention |
| **Golden Evidence Engineer** | `6ae5dcacb7908191b72d98510a3db5b6` | [#76](https://github.com/Riannoni/web-vn/issues/76), native teamctl G-only visual-evidence submission with exact SHA and fence, NO fake Git code diff |
| **Exact Pose Researcher** | `6ae5dcafbf7c8191aaf823beed911ff2` | [#77](https://github.com/Riannoni/web-vn/issues/77), independent real rear-oblique pose reference + experimental vs approved guide distinction |
| **Identity and Wardrobe Engineer** | `6ae5dcb38de4819193cccf1a9c5954d2` | canonical face and outfit source conditioning, tested native ROCm path, no cross-model unsupported adapter |
| **E2E and Latency Engineer** | `6ae5dcb6f8c88191b2cc46a83f64d8da` | real browser action→narrator→GPU→VLM QA→publish, true stage P50/P90, no synthetic E2E success |
| **Broker Independent Reviewer** | `6ae5dcb9fb3c8191935b5ef13fab8f5b` | independent adversarial read-only review of [draft PR #78](https://github.com/Riannoni/web-vn/pull/78); cannot self-deploy or weaken testing |
| **Release/Integration Reviewer** | `6ae5dcbce2c481919e6cd302c223c279` | cross-PR independent SHA/CI/deployed status and privacy/negative regression, not an extra queue planner |
| **Source Contract/Provenance Engineer** | `6ae5dd11d4748191adb005926b42c083` | authentic creation-time scene/save/actor/outfit/workflow/prompt/PNG/contract binding; cross-scene and forged provenance negative tests |

**Conflict rule:** Each specialist owns an isolated repo branch and independently scoped worktree. Existing local SQLite source-only coordinator is a **four-lane implementation**, not a twelve-lane scheduler. Do not claim that new specialist roles automatically gain independent SQLite claim/fence. Their PR/issue provenance and Chief independent review are coordination authority until the controller supports typed tasks and disjoint owner scopes. Do not write a file another active worker is modifying; agree integration order through Chief. Parallel source/CPU/G2 work is encouraged; GPU writes are serialized.

## Actual system diagram

```text
Owner goals + frozen authentic Scene Contract / canonical source refs
                  |
       Chief: selects earliest G2 failure + falsifiable hypothesis
                  |
      Independent specialists work in parallel on disjoint source branches
       |           |              |               |
   Identity     Pose guide       QA / provenance    Broker / E2E
       \           |               |               /
        Independent code/security reviews + tested exact SHA
                  |
          One bounded disposable GPU job
      (host-side 1-minute dispatcher and **central enforced broker**)
                  |
            Original PNG + prompt ID + SHA + stage times
                  |
           Golden reads original pixels + canonical refs
                  |
          Independent scene-mandatory G2 receipt
               / FAIL          \ PASS
       diagnose one factor      next frozen case
               \                /
                Chief updates cause + next experiment
                   |
           Repeat until 5/5 first-shot G2
                   |
           Disposable browser E2E, QA p50/p90
                   |
           >30 independent human-labeled cases, restart/rollback
```

## Why more roles alone are not sufficient

1. **PR #78 is real progress but NOT deployed:** it proposes Comfy broker at public-to-clients localhost 8188, guarded backend 8189, durable exclusive ownership, fixes bypassing worker.py + Model Lab + dispatcher, and tests 26/26 broker, 4/4 Kobold, 28/28 first-shot. Draft at latest reviewed SHA, independent reviewer and Chief must explicitly accept all negative cases then perform reversible deployment/real smoke. The old direct POST /prompt bypass is a genuine race; vacant queue is insufficient.
2. **Read-only Golden was falsely BLOCKED:** G-10 independently viewed R-13 original, G2 FAIL, but legacy `teamctl` forced non-empty `changed_paths` / Git diff for any `submit`. #76 owns a separate evidence-only kind and tests; cannot reuse blocked G-10 or claim a source change exists.
3. **Pose-guide gate had a cycle:** G-11 created only a synthetic 2D 41.9° projected lean guide but lacked genuinely independent HMAC approval and source 3D evidence. R-14 depended on G-11. #77 separates `experimental_unapproved` guide (safe one-factor lab A/B, only after broker) from `production_approved` guide. Original rear-oblique refs remain DRAFT; the side-view approved guide is a WRONG view for CG-03. An independent G2 review after GPU is the real test; 2D preflight alone cannot prove hand-to-wall contact.
4. **Identity is unanchored:** the fast native Z-Image graph defaults to private text-only, no canonical identity conditioning. A beautiful 5–11s PNG is NOT a stable character. Must prove reliable identity, wardrobe, location and prop contact with measured ROCm-compatible references before claiming five consecutive real first-shot passes.
5. **Full game remains slow/unproved:** standalone submit-to-PNG 5–11s is distinct from observed 100s browser path with slow QA. The E2E engineer must measure true narrator, GPU, postprocess, VLM QA, retry and publish stage timings. No optional stage may bypass mandatory QA to meet a target.
6. **Cloud cadence still hourly:** separate 12 schedules reduce waiting and Chief bottleneck; native scheduled tasks currently do not have an official subhourly schedule, and broker's local minute timer cannot create creative hypotheses. Event-triggered tasks execute in **Work**, prohibited by owner's cost preference, so do not silently create Work webhook tasks. **The earlier ready-task idle ≤10 min goal is an SLO, not a guaranteed 24/7 contract.** Measure and report its actual breaches.
7. **Total ChatGPT workload still finite:** even Pro's 15 task slots do NOT imply infinite model tokens or compute. No Codex/Work escape hatches. If many Scheduled sessions run without meaningful independent backlog, pause or narrow them. Multiple concurrent GPU jobs are not inherently faster on one AMD card; require measured VRAM/latency A/B before increasing concurrency.

## Mandatory evidence and stop conditions

For each real GPU candidate: exact case+source-state SHA, actor canonical refs SHA and outfit version, complete typed Scene Contract and negative evidence, seed/model/graph/pose, single changed factor, durable prompt ID, original PNG SHA, first GPU attempt index, stage times + VRAM, source/game save hash before/after, Golden direct-original pixel verdict for environment/cast/identity/outfit/props/landmarks/pose/contact/camera/sprite RGBA, honest `unobservable`, independently accepted exact source SHA and separate deployed status. Never substitute GPU G1 or false automated QA for G2. No fake human labels or retained production assets from a failed candidate. After 2–3 controlled failures of the same cause, STOP and challenge architecture rather than blind rerolls.

No successful five-frame G2 score is claimed yet. Frozen v1: G1 5/5, G2 only synthetic background pass; original R-13 disposable attempt 2 G1 PASS in 6.029s but G2 FAIL (wrong view/lean/crop/contact/identity). G3 NO_GO. Broker and Golden evidence remediation remain gating items. Browser E2E still NOT VERIFIED.

## Practical next handoff

1. Independent Broker Reviewer validates PR #78 head, protocol, OS backend guard and rollback; Chief approves and supervises deployed single-owner path. Broker Engineer owns source implementation; **only** this team touches GPU broker code.
2. Golden Evidence Engineer implements #76 separately (not the Broker engineer), with adversarial tests and independent Chief review; migrate future visual-only tasks to correct schema, preserve blocked historical IDs.
3. Exact Pose Researcher validates original rear-oblique reference, labels synthetic 2D only `experimental_unapproved`, and hands Renderer a frozen single-factor plan for one real controlled post-broker GPU candidate.
4. Identity/Source Contract specialists verify authentic actor/outfit/scene reference attribution, then source-conditioned generator/correct outfit. E2E specialist profiles actual full game pipeline and independently verifies G2 and failed QA handling.
5. Chief issues genuine next stage R-15 only after broker and source contracts, promptly wakes ready cloud workers when possible. Golden inspects every new original PNG before releasing next candidate. Chief reports to owner hourly.

No extra reporter automation, Dot dependency, silent local Codex run, or Work tasks are part of this operating plan.

## V17 — correct provider-scoped wake quota

The `vn-proxy-quota --provider codex` sample measures **Codex OAuth**, not ordinary ChatGPT Scheduled Task usage. Do not block a genuine Scheduled `run_now` on a missing/full Codex OAuth meter. The native platform is the authority for Scheduled quota and actual admission. `wake_guard.py` keeps atomic reservation, 120s cooldown, clean worktree/scope/dependency check and per-hour rate budgets. This is never permission to launch Codex, Work or paid API. Check `peek` for task enabled/not running before invoking official `run_now`; a request is not evidence of startup or a SQLite claim.

## V17 — 5-minute phase-staggered native Scheduled wake mesh

The 12 active Scheduled jobs still run **no more frequently than once an hour each**, per official ChatGPT paid Scheduled-task limits. They have now been *actually rescheduled* across a rolling hour (Europe/Helsinki time): Broker :00, Broker Independent Reviewer :05, Chief :10, Integration Reviewer :15, Renderer :20, Golden :25, Golden Evidence :30, Pose :35, Identity :40, Provenance :45, Reliability :50, E2E :55. This means **one different worker has a normal scheduled trigger every five minutes**, not that a specific worker is guaranteed to run within five minutes.

Each worker also performs a bounded **useful handoff check** before finishing its scheduled run. When an actual new PR SHA, independent source approval SHA, new original PNG SHA, fixed critical blocker, or exact contract/ref SHA makes a *different* worker actionable, call the existing native Scheduled API `Automations.peek` for that worker and, if enabled/not already running, reserve one cross-wake via `scripts/native_team/ops/scheduled_wake_mesh.py` on the PC. Only after a successful reservation use **official `Automations.run_now`**. This is an optional request, not a guarantee of cloud startup or a model entitlement. Never wake tasks for repeated unchanged evidence, no meaningful ready task, missing SHA or unreviewed GPU candidate. The mesh does not invoke a model and is not a substitute for a legitimate review.

Example (with verified source commit and Cloud role):
```bash
python3 control/scheduled_wake_mesh.py --root "$HOME/.local/share/web-vn-native-team/run-20261031-full" --target chief --event-kind source_pr_ready --evidence-sha "EXACT_40_HEX_SHA" --requestor broker --reserve
```
In the currently installed layout `control/scheduled_wake_mesh.py` is the deployed copy of `scripts/native_team/ops/scheduled_wake_mesh.py`. Exact event kinds: `source_pr_ready`, `review_accepted`, `visual_candidate_ready`, `blocker_cleared`, `contract_verified`, `integration_ready`. Only grounded 40/64-character lower-hex evidence hashes are permitted. Cross-wake SQLite reservations are unique per target/kind/SHA, atomic across simultaneous workers, minimum 240s between target wakes, maximum 3 extra wakes/target/hour and 18 across the team/hour. Local SQLite permissions restricted to 0600.

**Provider separation:** `vn-proxy-quota --provider codex` measures local **Codex OAuth only**, and no longer blocks normal ChatGPT Scheduled wake requests. Codex/Work/pay-per-token remain forbidden. The ChatGPT Scheduled platform alone grants or refuses real runs; account plan and usage limits are still enforced by the platform. This avoids false pauses when Codex's five-hour/weekly meter is missing or depleted. Existing wake_guard gates still enforce task scope, dependencies, clean worktree, 120-second cooldown, per-lane hourly budget. Cross-wake complements them for the seven specialist roles not in the four-lane SQLite source controller; it never creates model quota.

**Honest SLO:** ready worker idle ≤10 minutes is an objective. Five-minute stagger helps notification latency but Scheduled tasks may be delayed, run long, return no_update, hit model usage limits or require approval. No unsupported subhourly native recurrence or backdoor API calls. Report actual timestamps for requested, cloud started, SQLite claimed, evidence submitted, independent review complete, and final GPU original G2. A request is never a claim or success. If no meaningful backlog or missing verified event, idle is legitimate, and no synthetic task is created.
