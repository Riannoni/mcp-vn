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
