# GPU first-shot autonomous development — gap audit and changes (2026-10-31)

**Status: NOT YET sufficient for 5/5 G2 first-shot or ≤20 seconds complete E2E.** Read root AGENTS.md and docs/DEVELOPMENT-AND-TESTING.md first. This file supersedes planning-only instructions, not source/privacy/G1-G3 gates.

## Architecture now

Cloud schedules (hourly): Chief independent reviewer/planner; Renderer actor/pose/CG experiments; Golden independent original-pixel reviewer; Reliability and QA implementation; fifth slot is an hourly read-only user report. On PC: native SQLite teamctl, one-minute watchdog, Comfy GPU, prompt- and SHA-bound private evidence. Cloud workers share one GPU and need independent fenced leases. Latest observed source-only tasks R-12/G-09 accepted, S-13 blocked in independent environment suite; QA Q-10/Q-11 blocked by connector file-transfer policy. No new successful post-baseline GPU→visual→fix→GPU cycle proved. Frozen five-frame baseline: 5/5 G1 in 5–11 s submit-to-PNG, only BG passes synthetic G2; actual canonical identity and full game 100 s latency are unproved.

## Why this cannot yet reach the requested target reliably

1. **Correctness, not GPU raw speed:** Native Z-Image-Turbo text-to-image graph (worker/zimage_backend.py) explicitly forbids canonical identity adapter and allows ONLY private unanchored evaluation. Consequently a matching face/outfit, repeated environment, correct physical interaction and transparent sprites cannot be guaranteed by prompt-only search. Source and canonical reference binding must be tested on native ROCm conditioning (e.g., pose/source-specific workflow, not blindly ported SDXL IPAdapter).
2. **No actual GPU close loop:** Cloud worker A/B source fixes are not automatically submitted and independently original-pixel reviewed when their task completes; human-driven interactive-chat GPU baseline filled this gap once. The user now forbids chat as the manual render/review executor.
3. **Cloud Chief review and scheduled cadence:** one-hour cloud timers, with optional run_now only from live cloud runs; local watchdog cannot invoke official Cloud API. 10-min idle is a measured objective, not guaranteed. Chief source review can serialize evidence and cause starvation; review independent source changes in parallel where safe, but GPU submissions serialize.
4. **QA bottleneck:** full game may exceed 100 s even when isolated GPU submit-to-PNG is 5–11 s; live stage receipts missing. Entire P50/P90/QA/publish cannot be inferred from lab.
5. **Missing source-bound benchmark:** public five cases are synthetic, no private immutable canonical face, true scene/save/source contract; even visually attractive T2I frames must remain UNVERIFIED for identity.
6. **Agent model verification:** official Scheduled task metadata/actions expose no model ID or reasoning effort fields; task prompts cannot change actual model selection. Do not claim all Cloud agents use GPT-6 High/Astra. Existing local Codex CLI configuration explicitly has model=gpt-6-astra and model_reasoning_effort=high but its earlier night-runner is STOPPED; those are settings, not proof of currently running Astra. Model selection for eligible ChatGPT task conversations is managed in UI, availability depends on plan. Reporter does not need maximal intelligence.

## Concrete additions in this change

**One additional deterministic local GPU execution worker** `scripts/first_shot/autonomous_dispatch.py` with 1-minute systemd service/timer, not using model tokens. Renderer submits a private, exact-schema proposal with case, frozen baseline SHA, falsifiable hypothesis, one changed factor (prompt_text), task ID. Executor validates it, reserves exclusive lab file lock also used by original runner, confirms Comfy queue empty, submits ONE 90-second-bounded disposable GPU candidate with one prompt/job ID, exact PNG SHA and timing. This A/B is explicitly attempt 2 for old frozen case, NOT first-shot improvement by sleight of hand. Candidate moves to `review_pending`; **no further GPU test until independently visually reviewed** by Golden. On timeout, unknown job, invalid output or crash, executor leaves a fail-closed `running` fence and never automatically retries it. No job is started without an actual preapproved hypothesis. Direct /prompt paths from other processes are not magically OS-enforced by a file lock: if observed concurrent or unknown, STOP and investigate. This executor can progress while cloud planner is sleeping once candidate is queued. In the first rollout, no candidate will be auto-created or benchmark-score manipulated.

**Separate Golden review receipt** `scripts/first_shot/independent_review.py` validates exact prompt UUID, original image SHA bytes and independent G task before releasing the lab candidate; all prompt-only unanchored cases remain G2 UNVERIFIED or FAIL for canonical identity rather than fabricated PASS.

**Worker count is not capped at five.** The previous platform limit was five simultaneously enabled Plus Scheduled Automation **records**, now Pro allows fifteen, so reporter is paused and a fifth Broker Engineer task is enabled. Four local Codex Astra High subagents were configured for bounded CPU/read-only parallel audits; this is not proof of runtime model selection in cloud task runs. Distinguish automation slots from actual workers. A fifth heavy cloud worker would displace the hourly user report or another necessary reviewer. The correct extra capacity is the local deterministic GPU executor; later independent local multimodal reviewer with explicit Astra High can be piloted only after actual test of image transport, fresh quota and independent error calibration. Existing Codex Astra High was previously stopped after high token usage, so do not silently enable another long-running uncontrolled model.

## Correct next experiments, in priority order

- Renderer: prove native reference/identity+outfit preservation and genuine exact-view pose conditioning on held-out original pixels. One controlled factor and bounded attempts, not generic prompt-only retries.
- Reliability/QA: resolve Q-10/Q-11 transport blockers with different supported file route, establish reproducible CPU RGBA matte and deterministic negatives; instrument actual full game trace, not isolated GPU time.
- Golden: inspect each NEW original PNG and private reference, independently reject false accepts, feed exact first blocker back to Chief.
- Chief: approve matching SHA/tests, create next single causal hypothesis immediately, enqueue and wake Renderer, and track full wall-time and authentic G2.
- After first correct BG + canonical sprite + one CG, perform full 5-case first-shot fresh pack plus genuine disposable game E2E; only then consider deployment and broader 30+ human-labeled G3 cases.

## Commands and safeguards

Install the dispatcher with its pinned code from this branch into a dedicated PC lab checkout and a systemd user timer that calls:
`python3 .../scripts/first_shot/autonomous_dispatch.py tick --root ~/.local/share/web-vn-native-team/first-shot-lab-20261031/autonomous`.
It is safe with no proposals: `NO_APPROVED_WORK`, no GPU/model usage. Worker task R-n enqueues an explicit one-factor proposal:
`python3 .../autonomous_dispatch.py queue --root .../autonomous --plan .../private-proposal.json`.
Place plans only in private 0700 dirs, never GitHub when prompt contains private scene text. Actual PNG review is a separate model-run, not CPU unit tests. The local dispatcher MUST NOT automatically publish assets or claim G2 PASS. Any SLO on ≤10 min worker idle depends on Cloud event availability and is not guaranteed by the minute timer alone.

Do not weaken first-shot criteria, replace an accepted game save, publish failed images, infer human labels from AI review, or claim a configured model was the actual model without evidence.


## V14 19:01 current follow-up

Checked on live PC: timer `web-vn-first-shot-autonomous.timer` is active, installed lab source patch `ae6967c` passed independent 29/29 smoke. Real R-13 prompt `7b3b344b-fd8c-4068-8bd6-e541266ec174` finished with 6.029s G1 PASS and SHA `a10c347a814d4a212b8e6b02245d0c0e4ad85fb0a244457ea59d1005cc2f43ef`; Golden inspected original pixels and G2 FAIL, no re-run. `G-10` review task incorrectly blocked by a source-only commit requirement; S/Q worker must add an evidence-only, exact-PNG/SHA/id/fence independent review path, with adversarial tests. `G-11` synthetic 2D guide is not source reference or physical-contact proof; independent rear-oblique original guide review required. R-14 must wait for signed valid guide and real central broker; do not weaken constraints. Direct `/prompt` sinks found in `mcp-vn/worker.py`, Model Lab `server.py`, and first-shot dispatcher; all must be brokered and bypass technically blocked. Cloud Chief reports hourly, dedicated reporter paused; 5 enabled automations is an account Schedule limit, not worker-concurrency cap.

## V16 Pro native worker expansion and no-Codex policy

See [PRO-NATIVE-AUTONOMOUS-TEAM-2026-10-31.md](PRO-NATIVE-AUTONOMOUS-TEAM-2026-10-31.md). Official Pro Scheduled Task active cap is **15**, user has **12 active ordinary ChatGPT workers**, old hourly reporter paused, Chief reports. Older 5-task cap was Plus/account-state historical. All background Codex/Work/CLIProxy model execution is prohibited by current owner preference and an earlier 5h quota exhaustion. Six additional specialized workers plus the independent source provenance worker implement #76, #77, #78 review, identity, real E2E, final code review and creation-time contract. Ordinary Scheduled ChatGPT worker model/effort cannot be directly set through the available automation action; mark actual runtime model MODEL_UNVERIFIED rather than claiming Astra High. Optional Dots is conditional on user entitlement/region, and any deeper Work/Codex tasks it spawns are likewise disallowed. Native teamctl is still four-lane locally; extra specialists work on separate PR branches and Chief integrates without overlapping writes. The first-shot 5/5 G2, canonical references, and browser E2E remain unverified.
