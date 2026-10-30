# Render-v1 gate — first-attempt private GPU canary (2026-10-30)

**Verdict: FAILED (visual conformance). Do not label render-v1 production-ready.**

## Reproduction and isolation

The actual PC ComfyUI ROCm worker was exercised against a read-only copy of an existing one-adult-character game job. The 3 tests used freshly generated ephemeral job IDs and a staging directory outside the canonical data store. The test runner **never called the server's publish, save, action, or game mutation API**; it only generated images, evaluated them, and wrote private local test artifacts. Production services were left untouched.

The evaluation is a coherent neutral market sequence: (1) one sprite wearing an explicitly changed blue travel jacket; (2) a CG of the character studying a folded map by a market stall; (3) a CG walking under a stone arch with that map. Each test used exactly one GPU generation attempt. The images, personal game state, identities, and model weights are **not** committed to GitHub.

## Grounded results

| Shot | GPU generation | CPU QA | Total | Automated QA | Human-observed scene conformance |
| --- | ---: | ---: | ---: | --- | --- |
| Sprite, changed outfit | 11.16 s | 12.98 s | 24.14 s | rejected: `Sprite shows several people` | FAIL: one visible adult protagonist, but an unrelated studio camera/tripod is generated; clothing differs from the requested precise jacket state. VLM person-count claim likely false. |
| CG-1, study folded map | 10.54 s | 13.49 s | 24.03 s | passed | FAIL: protagonist presents a basket of fruit instead of studying a map; correct broad market context alone is insufficient. |
| CG-2, pass beneath stone arch | 10.46 s | 14.07 s | 24.53 s | passed | FAIL: required arch and map are absent, and undergarments/outfit continuity shift; broad market context alone is insufficient. |

All three ComfyUI generations completed technically; zero of three satisfy the human-checked complete shot contract. The CG automatic QA **false-accepted 2 of 2** among these specific negative examples; this is not a population false-accept estimate. Sprite QA includes a likely false reject for additional people even though it correctly should reject the unrelated camera prop and inaccurate garment. Repeated trials and a labeled gold set remain required.

## Follow-up first-attempt sprite probe (not promoted)

One further private one-shot sprite experiment appended explicit negative terms for photography equipment, tripod, studio camera, lighting stands and boom microphone, while preserving the face-only reference. ComfyUI again produced a camera in the upper-left foreground, and **changed the intended standing pose to seated**. Automatic QA rejected for `several people` (the image showed one main person and a camera) and low face similarity **0.79** versus the configured **0.80** threshold. GPU generation **11.16s**, QA **13.33s**, total **24.49s**. Different random seed, therefore *not* a controlled A/B effectiveness estimate. These unverified negative prompt changes were rolled back in source; the test establishes only that more negative prompt words did not ensure a correct first-attempt render in this run. No private artifacts were published.

## Code change under evaluation

- `worker/render_invariants.py`, `worker/worker.py`: explicit alternate outfits never reuse an old **full-body** sprite through img2img; a fresh latent still receives the immutable canonical **face** IPAdapter. Default-outfit revisions retain existing reuse behavior.
- `worker/scene_constraints.py`: per-actor required wardrobe is included for *all* explicitly changed outfits in a mixed cast, never using a global negative garment list that contradicts other actors.
- `tests/worker-prompt-contract.test.py`, `tests/scene-constraints.test.py`, `tests/sprite-graph-wardrobe-isolation.test.py`: new regression coverage for wardrobe isolation, mixed cast, and actual Comfy graph wiring.
- `scripts/neutral-render-canary.py`: private, no-publish GPU regression harness. It deliberately does **not** upgrade the QA verdict into a human visual pass.

Static and component evidence: Python worker tests on isolated PC checkout (35 prior test files + new two-case graph test), Node 141/141 tests with the complete checkout in a network-isolated Docker runner, compileall and git diff whitespace validation. Actual GPU canary executed once with the candidate code copied to a separate PC staging path. None of these facts certify the pipeline.

## Architectural defects requiring further work

- QA currently verifies approximate count and broad setting but generally does not verify **the mandatory object, actor-object relation, architectural landmark, or garment continuity**. A plausible image can be silently published despite missing the requested scene (#32).
- Fixed outfit and face conditioning do not automatically control body shape, pose, accessory placement, camera angle, or precise garment opening/closure (#23, #31). Face similarity and person count are weak global CLIP/VLM proxies.
- The physically constrained live rear-view wall action still lacks a verified approved reference for that exact action/view. No alternative pose should be substituted silently. A correct DWPose skeleton is not proof of hand-to-wall contact (#29, #7).
- Need a typed shot object/relationship contract and a human-labeled false-positive/negative benchmark before mandatory semantic acceptance can be trustworthy (#2, #15, #20, #32).

## Release gate and rollback

**NOT MET:** first-attempt correct sprite + specified constrained CG + two linked complex CG shots, independent QA, and visual verification. Treat any green `passed` status without complete constraints as insufficient. Do not deploy this experimental branch into production until it passes the required gate. Existing production commit and active saves remain intact; rollback is leaving the production branch, production worker, and services unchanged. The isolated candidate worktree and disposable GPU artifacts may be removed after evidence is retained. See master roadmap #20 and issues #31 / #32.

## 30 October follow-up: new model, atomic claims and identity probes

**No production changes and no change to the gate verdict.** All generated files,
character references and screenshots remain private on the gaming PC. The
experimental GPU graph never submits server/game mutations.

### Why switching the generator matters

The preexisting SDXL/Pony single-pass CG generated a fruit basket instead of
an explicitly required paper map and omitted the requested stone archway, yet
passed general location/count QA. We tested the already-installed Z-Image-Turbo
community FP8-scaled transformer on the same categories using a native ComfyUI
graph: UNETLoader / Qwen3 4B `lumina2` / AuraFlow shift 3 / SD3 latent /
AE VAE / 8 steps / CFG 1.0 / `res_multistep` and `simple`. This is a
**different architecture** from SDXL; SDXL IPAdapter, its ControlNet and its
face crops are not portable directly to it.

The official INT8 ConvRot checkpoint failed under the current Comfy/ROCm
quantization loader. FP8 generated an accurate map scene in one attempt;
at 1216×704, subsequent batched jobs encountered a GPU process crash and
ComfyUI automatic restart. Kernel amdgpu page faults were observed. The
one-off attempts that succeeded do not establish high-res stability.

### Stabilized compact no-publish GPU smoke (two independent seeds)

With no image dimension above **1024** (CG 1024×592, sprite 704×1024),
Z-Image FP8 produced four consecutive technical successes for seed
`2026103001` and four for `2026103002`, **8/8 first-attempt graphs**
with **zero additional ComfyUI restarts** during those two series:

| Frame | Seed 2026103001 | Seed 2026103002 | Visual observation |
| --- | ---: | ---: | --- |
| Paper-map market CG | 10.02s | 6.01s | Visible map held/opened; outdoor market retained |
| Stone arch gate CG | 6.01s | 6.01s | Protagonist framed beneath a stone arch; rolled map |
| Rear wall brace CG | 6.01s | 6.00s | Both palms visually near/on stone; torso hip-hinge varies; exact contact **unverified** |
| Full-length changed-outfit sprite | 8.01s | 8.01s | One standing adult, jacket closed, trousers/boots, gray matte; alpha not validated here |

**These times are GPU-job wall-clock measurements, not complete narration+QA
turn latencies.** Prompts are neutral clothed evaluation scenes, **not** the
original story scene. Outputs were inspected, but no physical-action
DWPose+surface-contact certification or original-saved-beat end-to-end publish
was performed. The game requires 1216×704/832×1216; compact output needs
quality-checked resize or an integrated scaler before adoption. No sample
constitutes an achieved full render-v1 release gate.

### Identity consistency: strong within one scripted seed, not canonical

The existing Florence-2 CPU model (cached on the PC) proposed a single
face ROI in each shot in approximately 0.8–0.9 seconds. CLIP face-crop
similarity comparing compact seed-1 Z-Image sprite to its two front-facing
CGs was **0.8616 (map)** and **0.8736 (arch)**. These are advisory embedding
scores, not calibrated biometric identity guarantees. The rear-wall image
received **0.6417** but its face is not observable from behind.

Crucially, Z-Image frames still do not use the game’s established canonical
face anchor. A private SDXL + Face IPAdapter *face-only inpaint* was tested
on the good Z-Image map and sprite, without disturbing scene backgrounds.
It generated images but **decreased** similarity to the canonical anchor
(map 0.7234→0.7128, sprite 0.7694→0.7428) and introduced an overly smooth
face. This repair is **not accepted or deployed**. A real Z-Image-compatible
identity conditioning method and a multi-seed, multiple-camera review are
release blockers.

### New atomic-assertion QA (shadow mode, 4 labeled comparisons)

`scene.required_visuals` is an optional bounded, typed set of explicitly
requested objects, landmarks and relations. The narrator's parser validates
and forwards it, the server scene fingerprint tracks it, the worker prepends
it to generation instructions, and the independent QA reports a
three-state object/landmark contrast instead of inferring success from the
overall scenery. A required *physical relation* or actor action is **never**
certified by whole-frame CLIP alone; unsupported relations remain
`unobservable`/fail closed. The rollout is draft-only.

A separate candidate CPU vision daemon on port 9313 replayed four manually
classified private images (no canonical assets touched):

| Ground truth | Atomic score | QA decision |
| --- | ---: | --- |
| SDXL fruit basket where paper map required | 0.1956 | rejected (violated) |
| Z-Image visible unfolded map | 0.8586 | supported (verified label) |
| SDXL public square where stone arch required | 0.4734 | rejected (unobservable) |
| Z-Image visible stone arch | 0.9381 | supported (verified label) |

This **4/4 small-fixture classification** is not a population error-rate
estimate. The CLIP score is relative to a QA-controlled counterfactual;
its numeric value is not a probability that the object exists. Independent
object grounding, physical relations, character identity and human-reviewed
>=30-scene gold tests are still required. Existing generic QA allowed false
accepts of the first and third images; the candidate prevents that only when
`required_visuals` is explicitly supplied and the new QA daemon is deployed.

### Safe staging / rollback

The code lives in the draft branch `fix/render-wardrobe-isolation-20261030`.
`worker/atomic_visual_evidence.py` and `scripts/zimage_model_probe.py` are
intended for source-controlled testing; the remaining local fixture and face
scripts are workstation-only. Existing main, production API/worker/vision
server and actual story save are **unchanged**. The local model canary is
opt-in and not an additional selectable canonical image backend. Results
inform #20, #31, #32; a follow-up issue is required for Z-Image face
identity and deployment-size stability.

Useful upstream references:
- https://developer.amd.com/playbooks/comfyui-image-gen/
- https://huggingface.co/Comfy-Org/Z-Image-Turbo
- https://comfy.org/hub/workflows/z-image-turbo-fun-union-controlnet-7553d92529e0/
- https://github.com/Acly/krita-ai-diffusion

**Current go/no-go remains NO-GO** for automated first-pass publishing.

## 30 October 12:30 Novosibirsk — recovery after interrupted run

The earlier chat run timed out before its concluding write-up. Work was
recovered without modifying production services. The earlier GitHub Actions
run (`40998638483`) for PR #33 / commit `9cdfadf` finished **successfully**;
ComfyUI, production worker and production vision were active, queue empty.

### Third compact first-attempt set and native output

Refactored the proven FP8 Comfy workflow into the isolated
`worker/zimage_backend.py` pure builder. **Intentional release interlock:**
only a `private_unanchored=True` experiment can invoke this T2I graph;
any canonical face asset is rejected, and no production call site uses this
backend. It pins the known compatible FP8 checkpoint, Qwen3 4B, AE VAE,
AuraFlow sampler and max 1024px source dimensions; it rejects mismatched
model graphs and unsupported identity claims.

An additional seed `2026103003` generated all four test frames consecutively
on the real ROCm GPU, no additional Comfy restart. All four generated in their
first GPU attempt: map 6.14s, arch 6.12s, wall 6.10s, sprite 8.96s
(including conversion to game canvas and sprite cutout). Local postprocessing
converted CG to **1216×704 RGB** and sprite to **832×1216 RGBA**. For that
sprite, alpha transparent fraction **0.7793**, nonempty bbox
`[254,64,589,1172]`; cutout geometry still needs human QA, and these are
not proof of identity/pose. Thus the **three compact batches totaled 12/12
technical first-attempt outputs** with no new Comfy restart in those batches,
versus the prior high-resolution series that crashed. Complete scene
conformance and release gate are **not** certified.

### Canonical-character img2img experiment: FAIL

An independently staged experiment fed the **existing full-body canonical
reference** as a Z-Image img2img latent while changing outfit to a closed blue
jacket (fixed seed `2026103003`). Both one-attempt graphs completed, but:

- denoise **0.62**: preserved the previous green cloak/brown garments;
  required wardrobe change failed; canonical face-crop CLIP cosine **0.7559**;
- denoise **0.82**: changed to the correct blue jacket/dark trousers but did
  **not** preserve the canonical face; cosine **0.7346**;
- same T2I seed without reference: canonical face cosine **0.7579**.

The CLIP scores are comparative diagnostic signals, not biometrically
calibrated probabilities. The img2img experiment did not improve canonical
identity and exposed the exact *wardrobe-versus-identity* coupling seen in the
old rendering stack. Neither candidate was promoted. The two images and
canonical references remain private to the PC; only redacted metrics are
included in repository documentation.

**Next required work:** train/evaluate a Z-Image-native identity LoRA on a
curated authorized multi-angle data set or validate a compatible reference
adapter (with real ROCm benchmark). Evaluate exact-object and wall-contact
conditioning with the official Z-Image Union ControlNet; don't use SDXL
ControlNet nodes on the transformer. Until accepted, keep existing game
renderer unchanged and leave PR #33 draft.

Sources: https://huggingface.co/Comfy-Org/Z-Image-Turbo ;
https://docs.comfy.org/tutorials/image/z-image/z-image-turbo ;
https://huggingface.co/blog/content-and-code/training-a-lora-for-z-image-turbo
