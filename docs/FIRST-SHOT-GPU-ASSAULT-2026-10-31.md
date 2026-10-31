# P0 — FIRST-SHOT FIVE-FRAME GPU ASSAULT (2026-10-31)

Owner mandate: **stop producing source-only progress without pixel results.** First useful milestone TODAY (2026-10-31 local PC time) is an independently judged, fixed, disposable **BG ×1 + sprite ×1 + three DIFFERENT sequential story CG**, first GPU attempt per frame, with measured target **GPU render ≤20 s per frame** and separately recorded queue, preparation, postprocess, automated QA and full-turn latency. No guarantee that current hardware/workflow meets the target. **5/5 first-shot visual success** is the experiment's goal, not a release claim.

This operational priority supersedes V6/V7/V8/V9 **planning order** in automation prompts. It does **not** supersede AGENTS.md and docs/DEVELOPMENT-AND-TESTING.md: image truth, separate G1/G2/G3, immutable evidence, independent pixel review, no fake human labels, no corrupted active saves, no secret publication, STOP when ROCm faults or false accepts. Owner authorizes experiments on local GPU and changing **experiment-only** model/sampler/steps/workflow/QA configurations, even while current VN render is broken. Never use user game saves as the scratch dataset; no automatic publish of failed candidates.

## Frozen benchmark pack v1 (public abstract fixtures; private concrete refs live only on PC)

All IDs and non-sensitive mandatory controls are stored in `scripts/first_shot/pack-v1.json`. Source from one local frozen private scene contract and one canonical adult character reference; if immutable source and reference are missing, mark specific fields UNOBSERVABLE and do not invent them. In the same environment and actor continuity:
- **BG-01:** medieval market square, recognizable stone architecture, arch and stalls, no named foreground principals; opaque environment.
- **SPR-01:** full-body adult principal, canonical identity when visible, updated dark-blue outfit and boots, real RGBA silhouette with clear alpha (not studio background rendered opaque), complete limbs.
- **CG-01:** matching actor/outfit in established market, paper map clearly held using both hands, coherent scene and correct prop scale.
- **CG-02:** same character/costume and marketplace architecture, small closed wooden box at waist with observable two-hand grip, projected box/shoulder ratio within independently frozen contract.
- **CG-03:** actor facing stone arch wall, both palms in actual contact with masonry, body leaning forward, exact required camera view, same character and clothing.
A first-shot is **the first actual GPU image** for the exact frozen case. A second candidate, different seed, local inpaint or late compositing is tracked as `repair`, not first-shot. Case packs for visual stress should include the real user's challenging scene separately as a **private** benchmark, without putting sexual material/private dialogue in public GitHub.

## Execution today, in order

1. **Preflight 0 GPU:** verify GPU ROCm, power/VRAM, Comfy /queue idle, exact active backend, checkpoint hashes, available nodes, source/scene/PNG refs, existing unfinished job ownership. Snapshot/save checksum and no destructive operations. Create a private experiment root with restrictive 0700 perms; no active game save mutation.
2. **One positive baseline:** use already measured native Z-Image FP8/Union (historical 14.06 s GPU at 1024×592; not yet a repeat success). Freeze one job input + seed + graph digest + reference. Run a **single** GPU job against an isolated output prefix, not the normal game's publish path; write prompt_id, first candidate SHA and timings. If producer's receipt is missing, the test is allowed only as an isolated lab G1 probe; G2 linkage remains NOT VERIFIED.
3. **Pixel inspection immediately:** Golden reviewer gets **original PNG** by exact prompt_id/output SHA and exact private scene contract plus canonical face/outfit reference. Mandatory fields marked `verified|violated|unobservable|not_applicable` with ROI or visible observation; mandatory unobservable/violated => G2 FAIL. Never substitute thumbnail, caption or CLIP for original pixel evidence.
4. **Single-variable A/B:** speed worker explores **one** of native model, steps, resolution, sampler, prewarm per A/B; quality worker examines **one** causal change for the **earliest** observed G2 failure, same source/seed/model otherwise. At most two/three bounded attempts for one cause; STOP, reassess architecture. Keep rejected images, do not call best-of-N first-shot.
5. **Whole five-frame pack:** only when the selected baseline is G1-stable, run BG→sprite→CG1→CG2→CG3 on one frozen pack, independently pixel-reviewed at first attempt. Do not convert blocked/UNKNOWN into PASS. Record 5/5 result and exact reasons for every missing criterion.
6. **Scoreboard:** counts first-shot G1, G2, missing references; timings GPU, queue, preflight, postprocess, QA, full-turn P50/P90; max VRAM/peak temperatures; human review *separately* from AI visual reviewer; actual 0/5 vs 5/5 cannot be hidden. Update issue #20 and a short handoff every cloud cycle. Today’s fallback milestone: **BG+sprite+≥1 story CG** first-shot inspected and honest baselines for other CGs.

## Multi-worker topology and maximum speed

**Chief**: single scoreboard/stop/go owner, exact task queue and frozen contracts, independent reviews in parallel (separate read-only worktrees), no bottleneck for *preapproved* tasks. Escalate GPU gate and new image at earliest opportunity; no more pseudo-progress by purely source-only loops.
**Renderer / speed+quality**: one owner of Comfy submission in each run. Prepare graphics and conditioning on CPU concurrently, improve graph at one variable at a time, record first-shot, no silent retries. Parallel CPU preflight on next frame while current GPU works.
**QA**: fast **fail-closed** Stage 0 input and invariant check; Stage 1 CPU structural/geometry; Stage 2 targeted semantic only when needed, preserving mandatory checks and independently recognizing detector `unobservable`. Never disable mandatory QA to hit speed target. Performance target QA 5–10 s is aspirational and measured, not permission to skip.
**Golden**: receives original bytes and private canonical reference, independent visual verdict for every new generated PNG, keeps all negatives; AI review is not a **human label**. Organizes 30+ independent human-labeled G3 calibration only after 5-pack.
**Reliability**: GPU ownership and routing, queue/prompt attribution, duplicate fencing, monitors ROCm/VRAM/failures and experiment isolation. Existing multiple direct Comfy /prompt writers are known. No claim of **exclusive GPU** based on merely empty queue. A single lab controller and OS file lock can serialize lab submissions, but cannot exclude arbitrary other processes: inspect externally visible queue and workers before each submit and STOP if uncontrolled traffic appears.

**GPU concurrency**: baseline **one diffusion job at a time** on one AMD GPU; run CPU pose, image staging and QA in parallel. Do not grant 2 GPU diffusion writers until instrumented A/B proves sufficient free VRAM and improvement in throughput **and** per-job latency without ROCm faults. A graph that takes 14 s standalone may take >28 s at 2 concurrency; measure, do not guess. For experiments using live Comfy rather than a truly isolated instance, perform an immediate /queue pre/post and isolate assets/output; any concurrent unknown prompt cancels series.

## Evidence, gates, stop/rollback

A case row MUST contain: fixed case/seed; base commit/deployed version; typed scene contract SHA; canonical refs SHA or explicit missing; style/model/workflow SHA; prompt_id; exact original PNG file hash/dimensions; wall clock and GPU/CPU stage times; first_attempt index=1; job/output link provenance; per-mandatory G2 verdict; G1 status; G2 status; original save fingerprint before/after; private artifact path; reject class; next hypothesis.
- **G1 PASS** = executed, output structurally valid. **G2 PASS** = independent original-pixel proof every mandatory fact; no unknown. **G3** remains NO-GO without broader 30+ independent human-labeled end-to-end scenes, restart/retry and rollback.
- Protect original game state: experiment snapshots and temp save IDs; no overwrite of canonical assets or automatic publish. A broken game is not permission to corrupt player data.
- Budget initial 1 baseline frame, then fixed one-factor comparison if necessary. Only proceed to 5-frame test with validated inputs and no observed fatal mismatch. STOP immediately on ROCm pagefault, OOM, duplicate/unattributed GPU prompt, corrupted save, or 2–3 repetitions of same defect without causal explanation.
- Store all images, face refs, exact prompts and gameplay text **private on PC**, not in GitHub. Only redacted status, timing, case ID, hashes may enter issues/PRs.
- This source protocol by itself does **not** perform GPU tests. A GPU job is real only with recorded Comfy prompt_id, runtime and exact PNG hash. A cloud `run_now` request is not a confirmed started execution.

## Current known baseline (not a new pass)

Prior fixed native Z-Image Union CG had GPU 14.06 s, G1 PASS, G2 FAIL (contact/prop scale). Other wooden-box heldout took 22.55 s, G2 FAIL projected prop/shoulder ratio 1.1194 > frozen 1.0. User browser showed ~103.5/107.9 s total on rejected CG, Comfy ~22–43 s, QA ~57–81 s; these are **user-visible evidence**, not unambiguously instrumented component wall time. Current source-only lanes' tests and GitHub merge cannot replace GPU first-shots.

**Today's score:** 0/5 new pack first-shot G2 VERIFIED until actual images and audit arrive. Start with GPU experiments and genuine G2 rather than another unbounded source-only backlog.
