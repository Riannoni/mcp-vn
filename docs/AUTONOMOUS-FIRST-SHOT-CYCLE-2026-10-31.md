# Autonomous first-shot GPU → original pixel → QA → fix loop

**Effective:** 2026-10-31. Owner instruction: **the workers execute rendering, inspections, fixes, comparative experiments, and independent acceptance autonomously**. The interactive assistant chat is an interface for task setup, exceptions, and receiving reports, not a human-in-the-loop render executor. Precedence: read `AGENTS.md` first, full `docs/DEVELOPMENT-AND-TESTING.md` second; this document assigns roles and workflow within those invariants. Current P0 target `docs/FIRST-SHOT-GPU-ASSAULT-2026-10-31.md`, frozen `scripts/first_shot/pack-v1.json`, baseline `docs/FIRST-SHOT-GPU-RESULT-2026-10-31.md`, issue #20.

## Permanent objective and gates

On one RX 9070 XT, prove BG + identity-preserving transparent sprite + 3 different sequential CGs from the first actual GPU attempt **per case**, with **≤20 s submit-to-final PNG per case as a target**, full per-stage timing, **all 5 original images independently passing G2**, followed by actual game E2E. No picking best-of-N, no fake source-only GPU success, and no claiming entire turn latency = isolated GPU latency. Current independently observed frozen v1: G1 5/5 in 5.05–11.04 seconds; G2 only BG-01 PASS; other four FAIL; 0 human-labeled new cases; G3 NO_GO. **Every failure must produce one evidence-linked next causal hypothesis or a concrete blocker, not silence or arbitrary source-only tasks.** No release until broader independently human-labeled 30-case and regression gates.

## Active scheduled autonomous work + report

The ChatGPT account has a maximum of five enabled task automations. Assign four autonomous agents and one **read-only hourly reporter**:

| Function | Automation / lane | Responsible for |
|---|---|---|
| Chief/independent reviewer | `6ae57ba332a48191923e7f51ccfe7dd5` / C | review exact SHA/negative tests, approve or block; new specific task from G2 failure; wake ready workers; own P0 scoreboard and stop/go |
| Renderer / GPU owner | `6ae57b3727688191ab20279ff8fba0af` / R | one-factor model/pose/scene/identity A/B, disposable real Comfy jobs, original PNG + source, seed, graph and stage evidence; no self-approved G2 |
| Reliability + QA implementation | `6ae57b40434c8191857969a577627d2f` / S **and QA lane Q as independently scoped second worktree** | fix/measure CPU alpha, segmentation, fail-closed QA, queue/preflight/Comfy/postprocess/QA/turn metrics, GPU ownership and VRAM |
| Golden / independent visual reviewer | `6ae57b3d794c8191aff21eac865b780b` / G | fetch exact **original** PNG by prompt ID/SHA and original private scene refs, independently inspect pixels, verdict every applicable typed constraint, mark new candidate G2 PASS only when all mandatory VERIFIED |
| Hourly read-only reporter | `6ae5c7e719648191a68a4ffb4117452a` | report in the user-initiated ChatGPT task flow once per hour in Europe/Helsinki, beginning Oct 31 at 13:00; report actual GPU/PNG counts, G1/G2, commits, E2E latency, active leases/blockers and quota, without running experiments |

Earlier QA-only schedule `6ae57b3a03a48191889e3b0073c8e359` is intentionally **paused** to free an active automation slot: its Q-10 lease ended BLOCKED after platform SCP rejection, not a code/GPU failure. Move its legitimate QA duties to Reliability's separate **Q-lane** with independent Chief reviewer, without claiming Q-10 PASS or bypassing the known blocker. Golden is retained as independently executing visual evidence role. If Golden cannot retrieve full original pixels through scheduled tools, report `NOT_REVIEWED` and escalate; do not substitute image filenames, thumbnails, CLIP/VLM captions or a summary written by a different worker.

**Hourly report delivery limitation:** scheduling is provided by the ChatGPT Automations service; it cannot guarantee a real-time exact execution instant or that arbitrary other worker chat messages appear in this exact thread. The reporter was explicitly created from the user's current conversation and must write a substantive answer there rather than a GitHub-only comment. If UI/task delivery routes elsewhere, report the discrepancy—never pretend a notification arrived.

## Autonomous closed-loop state machine

1. **OBSERVE** (Chief/Renderer/Golden): read main SHA, live PC Comfy queue, active GPU owner, immutable private frozen pack contract/refs, actual last Comfy prompt ID, exact PNG SHA, latest scoreboard, outstanding SQLite tasks, quota. Do not reuse historical success as a new test. Existing `scripts/first_shot/scoreboard.py` must independently hash first-shot raw pixels and cross-check review prompt ID/SHA.
2. **DIAGNOSE** (Golden+QA): for each new original PNG, independently inspect mandatory environment, named principals, identity where visible, clothing, props, landmarks, pose, actual contact, camera and alpha. `violated` or `unobservable` mandatory → G2 FAIL. Log exact failure and ROI, categorize first blocker. QA's automated warnings never override pixel evidence. If an *unreviewed* original exists, Golden review takes precedence over another GPU render.
3. **PLAN ONE FACTOR** (Chief): take the earliest concrete G2 FAIL, define one falsifiable hypothesis, frozen source/model/seed/contract and exactly one changed factor, estimated VRAM, GPU runtime budget (normally one shot, at most bounded 2–3 causal tests), permitted paths and STOP condition. Atomically enqueue a scoped real task (unique task ID, dependency and lane); **do not add synthetic backlog** merely to fill uptime. Review queued source-only changes independently before attributing GPU impact.
4. **EXECUTE REAL GPU** (Renderer only): validate model/graph on target ROCm, no known other queue job, acquire a real owner/fenced lab lock (do not assert that filesystem lock alone locks external /prompt routes), label a **disposable** scene/save and isolated output prefix, record output path, first-shot index, UUID prompt ID, exact SHA, queue/Comfy times. Run exactly one candidate per preapproved hypothesis; do not silently rerun failed generations. Owner authorized changing experiment-only samplers/steps/CFG/conditioning/masks/model variants/QA performance. Parallel CPU prep, pose extraction, downstream postprocess allowed; GPU diffusion concurrency >1 only after controlled VRAM and per-job latency A/B without ROCm faults. Live-game save is NOT a scratchpad.
5. **QA AND ORIGINAL PIXEL** (Reliability/Golden): CPU fail-fast input→geometry→targeted semantic; no dropped mandatory checks, timed stages. Golden independently opens final full-resolution original candidate and (if composite) exact final derived image, uses private contract/references and provides SHA-bound visual verdict. Experiment author cannot self-approve G2. For multi-stage outputs, preserve first GPU vs repair distinction.
6. **DECIDE** (Chief): if G2 FAIL, create next one-factor hypothesis or STOP after 2–3 identical causal failures; if G2 PASS, record only that exact output and test next frozen scene. Never overwrite v1 score with v2: each version has own frozen pack and report. Only when 5/5 exact pack pass can move to disposable game E2E, then broader G3 tests and optional deployment with explicit evidence.
7. **REPEAT** (cloud workers): within *each* scheduled cloud run, make multiple bounded **useful** steps when evidence is available rather than exiting after source-only unit tests. Re-evaluate actual queue and CPU/GPU headroom. Chief wakes the next ready lane via official platform run_now after quota and cooldown guards; local one-minute watchdog handles deterministic catalog/telemetry, **not** magical cloud launches. If an official run_now is requested but cloud has not started, distinguish `REQUESTED` from actual `started/claimed`. No other assistant in chat should manually generate/inspect images on behalf of the workers.

## Event / artifact contract

Private PC root: `~/.local/share/web-vn-native-team/first-shot-lab-20261031` (0700). For each case or A/B candidate store: `case`, `pack_version`, `scene_contract_sha256`, reference SHA or explicit missing, `source_sha`, `model/checkpoint` hash, `workflow_graph_sha256`, `seed`, changed factor, `prompt_id`, `original_png_path`, `png_sha256`, `first_attempt`, `output_kind`, actual queue/preflight/Comfy/postprocess/QA/full time, `gpu_vram`, `g1`, `g2`, `reviewer`, `pixel_reviewed`, `mandatory_checks`, `failure_reason`, `next_hypothesis`. No private content in GitHub.

Each hourly report must include the number of **new** real GPU submits and G2-original-image reviews **during that reporting interval**, not cumulative count masquerading as progress; G1/G2 5-pack score, new accepted/failed cases, observed per-stage timings (or NOT MEASURED), individual blocked/leased/review_pending Q/G/R/S tasks, 10-minute ready-task idle SLO, real changes/commits/CI vs deployed status, quota samples, next concrete hypothesis. Reports are always delivered, including truthful `no new GPU jobs` hours. Golden AI pixel review is **not** a human label.

## Infrastructure and quotas

Use SSH-MCP from ChatGPT via `home` to PC as documented in AGENTS.md. Local minute watchdog/SQLite WAL, atomic unique fenced task claim, scope conflict fencing, no re-execution of an unknown GPU job. Reserve wake through local `wake_guard.py`, with fresh Codex OAuth sample under the existing 75% 5h/7d soft guard, never circumvent plan/token limits or use a paid API. Quota sample may NOT measure Work exactly. **Idle 10m is an SLO, not a guaranteed cloud schedule SLA**, and must be measured.

Never weaken actual positive/negative scene QA, forge source receipt, fabricate manual human labels, or publish failed images to active game. After a ROCm pagefault/OOM, source image/save corruption, two overlapping GPU owners or untrusted producer provenance, stop that hypothesis and record BLOCKED with evidence. Unsafe or genuinely impossible gates are blockers requiring an alternative tested architecture, **not excuses for indefinite source-only work**.

## Current first follow-up queue

- `R-12` candidate A/B pose/CG controller, source evidence awaiting independent review then one real GPU candidate.
- `S-13` timed pipeline evidence, independently reviewed before use; then assist QA with alpha/cutout (fresh Q-lane task, not resurrection of blocked Q-10).
- `G-09` original-pixel independent 5-frame evaluation, and immediate inspection of any new A/B candidate.
- `Q-10` **BLOCKED due SSH/SCP policy**, no commit; Chief creates a new Q-lane task with fresh independent paths and proven-safe connector writes rather than reusing a blocked lease.
- `BG-01` baseline G2 PASS; `SPR-01` no alpha/identity; `CG-01` unfolded map; `CG-02` duplicate box; `CG-03` insufficient forward wall lean. G1 5/5, G2 1/5, real VN full-turn ≥100s previously observed; G3 NO_GO.

**A successful source test without a newly reviewed real original PNG is a supporting engineering result, NEVER closure of the render quality milestone.**
