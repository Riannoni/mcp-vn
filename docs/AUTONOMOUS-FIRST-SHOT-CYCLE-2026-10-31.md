# Autonomous first-shot GPU → original pixel → QA → fix loop

**Current operating authority:** [WORKER-OPERATING-CONTRACT-2026-10-31.md](WORKER-OPERATING-CONTRACT-2026-10-31.md), with reviewed Scheduled prompt text in `scripts/native_team/ops/worker-prompts.json`. Read root `AGENTS.md` and full `docs/DEVELOPMENT-AND-TESTING.md` first. This document describes the execution cycle; [PRO-NATIVE-AUTONOMOUS-TEAM-2026-10-31.md](PRO-NATIVE-AUTONOMOUS-TEAM-2026-10-31.md) records the roles. The issue #20 evidence trail and live checks establish current state. Historical experiment protocols do not replace the owner's current acceptance criterion.

The workers execute rendering, original-pixel inspection, QA, comparative experiments, fixes and independent acceptance autonomously. Interactive chat is for the owner's instructions and reports; reopening it is not a prerequisite for an already authorized next step.

## Today's objective and separate gates

**Deadline: 23:59 on 31 October 2026, Asia/Novosibirsk (16:59 UTC).** On the existing single AMD GPU, demonstrate one background, the required identity-preserving transparent sprite set and **three different sequential story CGs**, each on its first actual GPU attempt for a frozen case, with every mandatory G2 fact independently verified.

**Generation latency must be ≤20 seconds per asset through readiness to publish.** Start at the asset-generation request and include queue wait, preparation, model/load work incurred by that request, GPU execution, postprocess, all mandatory QA and the ready-to-publish decision. Report GPU submit→PNG separately. Report narrator latency and the full game turn separately; do not substitute either for generation latency. Offline independent development Golden review duration is recorded separately from this runtime pipeline clock. Any actual publication-blocking runtime wait still belongs to the appropriate end-to-end interval; mandatory runtime QA cannot be renamed away. If the interval or any mandatory stage is missing, the ≤20-second goal is NOT MEASURED, not PASS.

Predeclared CPU postprocessing such as sprite alpha removal belongs to the measured first-attempt pipeline and requires independent inspection of the exact derived image as well as the original. A late repair, rerender, different seed or post-failure selection is not a first-shot pass. Keep every negative result. Freeze a new held-out pack before its first run; never overwrite the failed v1 pack or call a later A/B its first attempt.

G1 technical success, G2 original-pixel correctness and G3 release reliability remain separate. **No current evidence establishes this complete target.** The release gate still requires at least 30 independently human-labeled positive and negative scenes, calibrated false accepts/rejects/unobservable, complete timing evidence, restart/retry/rollback and save integrity. AI Golden reviews are not human labels.

## Current workers and reporting

The audited project roster has **15 role records, 14 enabled**. Golden Evidence Engineer is paused after delivering #76; Golden independent pixel review remains enabled. The older separate reporter and QA-only task are paused. Chief owns the hourly substantive owner report. Official `Automations.peek`, not a document's count, establishes enabled/running status before each handoff.

Development-agent reasoning uses ordinary ChatGPT Scheduled workers. **No replacement development inference through Codex CLI, ChatGPT Work, paid API or CLIProxyAPI model requests.** The existing application's already-authorized Comfy, QA and narrator runtime may be tested in a bounded way after verifying its established owner-authorized route/config; do not introduce a new model/account/billing route. Do not restart earlier local model-agent services. Deterministic host timers, SQLite, source tests and the authorized local Comfy experiment are distinct from model-agent execution. Codex OAuth quota is not Scheduled Tasks quota; only official Scheduled admission can accept/refuse its runs. Runtime model identity remains `MODEL_UNVERIFIED` without actual metadata.

Each specialist works in a disjoint source scope/worktree. The existing R/Q/G/S source controller does not automatically gain a new lane for every Scheduled role. Reconcile the exact owner, fence, active task and runtime controller version before claiming; do not create a second same-lane lease to escape a blocked task. A historical blocked ID stays blocked. A genuinely new independent task needs its own scope and reviewed dependencies.

Hourly reports must state new GPU submits and terminal original-pixel reviews **within the interval**, latest prompt/PNG/review timestamps, first-shot pack score, stage and generation→ready latency (or NOT MEASURED), blocked/running/review-pending work, source/merged/installed/E2E status, next hypothesis and the ready-task idle SLO. Do not turn a cumulative count, `run_now` receipt or another worker's summary into new progress. Chief reports actual delivery limitations rather than claiming a notification arrived in the owner's thread.

## Production ownership and the authorized disposable LAB route

Production game submissions require the independently reviewed technical single-owner broker and bypass prevention. An empty queue or a local `flock` alone is not host-wide exclusivity.

For one disposable experiment, the owner's V19 [lab-exclusive wrapper](LAB-EXCLUSIVE-FAST-PATH-2026-10-31.md) is an authorized alternative while the universal broker is unfinished. It snapshots known dev submitters, temporarily quiesces them, verifies attributed/empty Comfy state, runs one immutable candidate and restores only previously active services after known terminal completion and empty queue. Unknown/foreign prompt, unresolved running record or timeout means STOP without resend or speculative restart. This route is LAB ONLY and never claims production protection.

A SHA-bound `experimental_unapproved` exact-view guide may be tested once in that isolated lab; this is not production guide approval. Actual camera, both palm contacts, anatomy, identity and clothing still need independent original-pixel G2. Do not recreate the circular requirement that a guide prove its generated contact before any experiment.

GPU Lab owns actual submissions. Renderer and Identity prepare and independently review executable graphs; other specialists may do disjoint CPU/read-only work concurrently. No parallel diffusion writers, active-save edits, overwrite of accepted assets, automatic publication of failed candidates or blind repeats. GPU concurrency above one requires a separately justified measured VRAM/latency experiment.

## Execution cycle

1. **OBSERVE:** Chief and relevant worker reconcile main/experiment/runtime SHA, official peer status, local task owner/fence, Comfy history/queue, exact latest PNG and review, frozen private contract/references, and save/accepted-asset integrity. Read current evidence before acting. A JSON claiming G2 or matching a file SHA alone is not authenticated independent review; use the trusted contract and independently accepted receipt.
2. **DIAGNOSE:** Golden opens the exact full-resolution original by prompt ID and SHA, with authentic canonical references. Record environment, named principals, visible identity, current clothing, objects, landmarks, pose, actual contact, camera and alpha as verified/violated/unobservable/not_applicable. A mandatory violation or unobservable fact cannot pass. An unreviewed original takes precedence over another GPU candidate.
3. **PLAN ONE FACTOR:** Chief/Decision Authority selects the earliest causal failure, states one falsifiable hypothesis and its executable graph/input changes, frozen controls, resource budget and STOP condition. Use one candidate; after 2–3 failures of the same cause, stop and revisit architecture. Do not fill queues with invented tasks or another helper that cannot reach a real image.
4. **EXECUTE:** GPU Lab uses the production broker or the authorized disposable lab wrapper, as appropriate. Recheck current ownership and graph/source hashes, preserve a unique immutable intent and exact prompt ID, then execute once. Unknown submission state is investigated, never automatically retried. Preserve the original PNG, exact graph, all stage clocks and first-attempt index privately.
5. **QA AND PIXELS:** QA runs fail-closed input, structural/geometry and mandatory semantic checks with measured durations. Golden independently inspects original and final derived output against the contract. The experiment author cannot self-approve. Record both visual correctness and generation→ready latency; a quality pass over 20 seconds is a latency failure.
6. **DECIDE AND HAND OFF:** Decision Authority accepts/rejects the exact evidence or identifies one minimal repair; Chief selects the next useful task. Complete a bounded transition in the same Scheduled run when possible. If another role is now actionable, use the canonical handoff protocol and official `peek`/`run_now` with durable reservation/receipt reconciliation. `REQUESTED`, cloud `STARTED`, local `CLAIMED`, artifact produced and independent review complete are distinct.
7. **ADVANCE:** After development evidence supports a candidate architecture, freeze the new held-out five-case test and run each case once. All five require full mandatory G2 and measured ≤20-second generation→ready. Then verify disposable game/browser integration and the separate G3 release suite. Neither one good scene nor source CI authorizes a release.

## Concrete next work: canonical reference route

The fast native Z-Image lab graph is intentionally unanchored and rejects canonical face input; its current dispatcher supports only text and native-pose changes. It cannot satisfy canonical story continuity by producing more synthetic pose candidates.

R-15 now has a terminal Golden FAIL; after reconciling that exact receipt, Identity and Renderer should deliver **one real canonical visible-face sprite experiment** using the existing SDXL Pony/Face-IPAdapter route. Source/Provenance freezes the genuine face bytes, scene/save/outfit revision and mandatory contract; Identity verifies actual adapter→sampler wiring and tests fresh body latent against historical garment leakage. The executable one-factor graph needs a narrow independently reviewed lab-dispatcher route; do not merely add another offline validator. Use the existing authorized lab wrapper, measure all generation stages, apply reviewed CPU matte and retain all mandatory QA. No new model research or production rollout is implied.

A successful sprite is followed by three distinct source-bound story CGs under the same canonical continuity requirement. If a quality-correct candidate exceeds 20 seconds, a subsequent bounded speed experiment changes one supported factor while preserving every mandatory check. Do not claim the installed stack already meets the time goal.

## Historical evidence and superseded blockers

These checkpoints remain reproducible history, not instructions to repeat their tasks:

| Checkpoint | Evidence and limitation |
|---|---|
| Frozen v1 five-frame pack | G1 5/5, submit→PNG 5.050–11.040s; G2 1/5, synthetic BG only. Sprite alpha/identity and CG map/box/lean failed. The timing excluded downstream postprocess/QA and is not today's ≤20-second criterion. |
| R-13 / G-10, reviewed by 11:50 UTC | Prompt `7b3b344b-fd8c-4068-8bd6-e541266ec174`, PNG `a10c347a814d4a212b8e6b02245d0c0e4ad85fb0a244457ea59d1005cc2f43ef`, 6.029s, attempt 2, G2 FAIL: upright torso, wrong view, cropped boots; contact/identity unobservable. Do not resubmit. Historical G-10 remained blocked by the old source-only schema despite real negative review. |
| #76 control-plane delivery, 13:23 UTC | Evidence-only Golden submission was merged and installed with additive migration, 102/102 source tests and watchdog smoke. Preserve historical blocked tasks; do not recreate this completed implementation. No new image quality was proved. |
| R-15, original about 14:10 UTC | Prompt `3287d7d6-cfa2-4d66-b666-97b2ec135bc0`, PNG `632a20a06e7d8e2d64cb3cebec316d44f15330296017d9f9e1efab9568a48241`, native pose, 8.019s submit→PNG, attempt 3. Golden terminal receipt at **14:26:19 UTC: G2 FAIL**, review recorded and review_pending→reviewed. Palm contact improved; legs/full boots and required 40° lean were not proved; canonical identity UNOBSERVABLE. Reconcile the exact receipt; never replay this historical plan. |

Sources: [v1 report](FIRST-SHOT-GPU-RESULT-2026-10-31.md), [R-13 review](https://github.com/Riannoni/web-vn/issues/20#issuecomment-6542989185), [#76 rollout](https://github.com/Riannoni/web-vn/issues/76#issuecomment-6543925935), [R-15 receipt](https://github.com/Riannoni/web-vn/issues/20#issuecomment-6544519370). Earlier R-12/G-09/Q-10/Q-11/S-13 and five-slot/Codex plans are historical; current task state must be read, not reconstructed from old prose.

## Private evidence and STOP

Keep private source, scene text, images, canonical references and keys on protected PC storage. Every candidate retains case/pack version, contract/source/reference hashes, model/graph/seed, changed factor, immutable intent, prompt ID, original and derived PNG hashes, attempt index, queue/preflight/GPU/postprocess/QA/ready and full-turn timings, VRAM, before/after integrity evidence, independent reviewer, all mandatory verdicts, failure cause and next hypothesis. Publish only the redacted index.

After ROCm pagefault/OOM, unexplained overlap, save/source corruption, untrusted provenance or unknown submission, STOP and preserve evidence. Never weaken mandatory QA, fabricate a source receipt or human label, clear an unexplained lease, or publish a failed image. A source-only test is supporting engineering evidence, never closure of the rendering goal.
