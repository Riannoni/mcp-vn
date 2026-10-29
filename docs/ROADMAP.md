# mcp-vn / Kagesekai — durable roadmap (2026-10-29)

This master roadmap plus linked Issues is the source of truth after any chat ends. Current pilot: Ash Gate. Do not claim render-v1 ready until golden-set and end-to-end gates have evidence. Keep private game saves, dialogue, CG, face references, tokens and model weights out of GitHub.

## Architecture invariants
- Canonical narration is atomic, version-fenced and separate from asynchronous visual work.
- One shared engine for all games; per-game story, assets, state and memory isolated.
- Scene Contract: named principals, world/setting, outfit, camera, regions, crowd policy, object contacts. Never silently transform unknown evidence into verified.
- QA verifies independently: correctness of location, cast, identity where visible, pose/contact when observable; retry/repair then publish only if the scene fingerprint still matches.
- Single AMD GPU: model or custom-node addition requires measured benefit. All public dependencies pinned and licences checked.
- Regression tests must run on temporary games, not production playthroughs.

## P0 — render-v1 release blockers
- #2 Golden human-labeled E2E suite (>=30 independent scenes), positive/negative, P50/P90 complete turn latency, accuracy and retries.
- #3 Named principals versus ambient extras: align Scene Contract and count evidence, unknown remains unknown.
- #4 Fail-closed on semantic QA unavailable for mandatory checks.
- #5 Shared explicit actor region/mask treatment for Scene and Local CG.
- #6 Isolated live GPU/temp-game validation including retry, replacement, publishing, restart and rollback.

- #21 P0-06 Required CG location must be verified, not merely absence of hard contradiction; live E2E caught a gray studio portrait mispublished as a market.
- #23 P0-07 Per-character outfit/wardrobe continuity QA for CG, including exposed body/cloak mismatches, without blanket filtering.

## P1 — reliability
- #7 Face observability / ambiguous identity and physical-contact evidence: never assert exact hand/object contact from mere proximity.
- #8 GitHub Actions Node/Python/security/schema CI.
- #9 scoped, dry-run Comfy temp pruning with queue guards; never touch canonical data.
- #10 durable render manifest, prompt IDs, retries, post-restart recovery and fault injection.
- #11 declarative environment, style, workflow configuration; no game-specific code changes.
- #12 performance and quality budget: TTFT, completion, queue wait, GPU, CLIP/VLM and repair P50/P90, error/uncertain ratios.

- #22 P1-07 Background-grounded neural CG, identity-mask localization for solo principals, detection of duplicated named actors in crowd. Live E2E still required.

## P2 — after render-v1
- #13 **Narration streaming**: player action → prompt LLM with moderate/low thinking and token streaming → provisional text in UI → validate complete structured output → atomic canonical commit with action ID, optimistic version and idempotency → separate asynchronously completed visual plan → ComfyUI and QA. Partial JSON, connection loss, cancellation or browser reconnect must never corrupt canon. Goal first provisional words **2–5 seconds**, ordinary complete turn **10–20 seconds**: engineering targets, not claims of provider performance; measure TTFT and p90.
- #14 SAM/Impact Pack/FaceDetailer mask precision on grounded ROIs if proven helpful.
- #15 GenEval2-like atomic visual assertions (objects, count, colors, positions, physical relations), VLM A/B including Qwen/Florence as shadow variants only until calibrated.
- #16 3–4+ actor staged rendering, independent face masks, depth and identity.
- #17 robust story package v2, manifest, metadata, branching, media, versioned migrations and transactional data-only import.
- #18 permitted source adapters, Kagesekai library/catalog UI and independent sessions.
- #19 QA inspector, human arbitration, scene blocking editor and audit logs.

## Import design (#17, #18), intentionally postponed
Today story.v1 and offline import exist; do not break. Proposed story.v2 includes rights provenance and URLs, author/licence, story/character stable IDs, localized text, lore/world bible, scenes, branches/conditions, state variables, media references and versioned style/QA profiles. Staged parse/size checks, no executable scripts, no arbitrary remote URLs/path traversal/zip bombs, dry-run with diff and rights confirmation; commit only after whole package verifies; migration with backup, rollback, idempotent re-import; never overwrite running save. Catalog: filters, preview, start/resume, game-specific media cache, provenance, import progress and errors. External adapters ONLY via authorized APIs, user-provided exports and rights-cleared content; no unauthorized scraping.

## Open-source reference ledger
- TaleWeaver: per-story styles, ComfyUI workflow portability and scene assets (reference, not copied code).
- Krita AI Diffusion: spatial prompting, editable masks and local inpaint.
- ComfyUI Impact Pack: segmentation, detailers and selective fixes; evaluate dependency/security costs.
- IPAdapter Plus: per-actor identity region consistency and staged conditioning.
- Openovel: foreground narration vs background analysis/directing separation.
- SillyTavern: world info, character cards, expressions and asset reuse.
- GenEval2: decompose scene into object/count/attribute/relation checks rather than one vague score.
- Official ComfyUI APIs: prompt/job ID, history, status, queue, scoped resume/cancel.
Sources: https://github.com/TaleWeaverAdmin/TaleWeaver ; https://github.com/Acly/krita-ai-diffusion ; https://github.com/ltdrdata/ComfyUI-Impact-Pack ; https://github.com/cubiq/ComfyUI_IPAdapter_plus ; https://github.com/Feed-Scription/openovel ; https://github.com/SillyTavern/SillyTavern ; https://github.com/facebookresearch/GenEval2 ; https://github.com/Comfy-Org/ComfyUI/blob/master/openapi.yaml

## Acceptance / evidence contract
Each issue only closes when relevant code, tests, measured output (without private CG), deployment revision, rollback and remaining unknowns are documented. Baseline immediately after prior rollout: 372 historical jobs (281 done, 40 failed, 51 superseded); zero post-rollout visual_contract/evidence samples at that moment. This baseline is not proof of new QA accuracy. Keep a live scoreboard and prevent scope creep until render-v1 works on the test game.
