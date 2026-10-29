# Rendering pipeline — current production track

This track takes precedence over expanding the multi-game catalog. Use the
existing Ash Gate save as a regression source, but do NOT alter its dialogue,
assets, or active game state as part of automatic tests.

## Rendering modes

- **Background plate:** narrator provides a setting description. The worker
  merges it with an invariant environment contract: coherent location,
  framing and no foreground named actors. Output is a full opaque environment
  PNG, evaluated by technical QA and independent scene/location cues.
- **Character sprite:** narrator provides the action/look. The engine retains
  the current character variant (identity, wardrobe, pose, expression),
  full-body framing and a neutral backdrop suitable for removing background.
  Canonical facial references and alpha coverage are independently checked.
  An image is published only if QA passes.
- **CG:** narrator provides the actual shot; character identities, environment,
  outfit, camera and intended interactions are retained. The scene is a single
  coherent image, not a collage of separately generated bodies. Approved
  DWPose+ControlNet is mandatory only for exactly recognized/approved actions;
  if needed but unavailable, generation fails without GPU retries. Geometry
  check runs BEFORE the slower semantic/VLM check.

All of these invariants live in worker/render_invariants.py and/or shared
scene constraints; narrator text never overrides the rendering fundamentals.

## Targeted retries (rather than blind reseeding)

worker/render_retry.py maps the previous failure to a category:
pose_geometry, physical_contact, wardrobe, identity, environment, cardinality,
sprite_cutout, or unclassified. Each category injects specific corrective
instructions. Only pose_geometry increases ControlNet conditioning strength
on subsequent attempts (0.90, then 1.0); it does not weaken QA.

Missing required approved guides, mandatory ControlNet failures, absent
canonical identity and incompatible engine versions are structural errors:
they fail permanently after the first attempt. Transient HTTP/Comfy errors
remain retryable up to the existing bounded attempt budget.

No successful QA result is synthesized or forced. Existing acceptance
thresholds are unchanged.

## Debugging and reproducibility

For new GPU jobs the worker reports a RENDER_GRAPH_TRACE in the journal.
The QA report records its retry category and — when the worker completes
generation — seed, checkpoint, hashes of the assembled positive/negative
prompts, and ControlNet strength. These are enough to correlate prompt
preparation with the actual Comfy graph, without logging unredacted private
story prompts.

The original narrator prompt and character snapshot still live in the
per-game job spec. Investigations must distinguish (a) a missing reference,
(b) prompt mismatch, (c) actual incorrect generation, and (d) a false
semantic QA verdict; do not treat all rejected frames as a prompt failure.

## Verified in code (not a promise of perfect art)

- Unit tests cover all three narrator prompt modes, retry classification,
  non-story-specific environment tags, and terminal vs retryable errors.
- Preflight with REAL saved background/sprite/CG job JSON reconstructs all
  three Comfy graphs without running diffusion. For a scene pose failure at
  attempt #3, approved ControlNet remains connected and its conditioning
  strength increases to 1.0.
- Existing validated DWPose principal-geometry checks still reject bad
  ground poses and ignore tiny background skeleton detections.
- No production save or existing image needs migration for this release.

## Remaining quality milestones (not yet solved)

1. Replace unreliable hand/object semantic verification with a properly
   benchmarked stronger vision model or independent region/object detector.
   SmolVLM2-500M can misdescribe hands even when DWPose geometry is correct.
   Never accept a contact merely because its skeleton matches.
2. Make the storyteller produce a typed scene blocking/actor/action graph,
   including named principals, visual interaction objects, camera, supports,
   and independently chosen crowd/extras policy.
3. Establish validated multi-actor ControlNet guides and region-conditioned
   generation. Current successful 1–4 face-adapter graph construction does not
   guarantee correctly staged character interactions. More than four named
   principal identities require a multi-pass plan.
4. Benchmark the three pipelines on a fixed set of representative,
   non-explicit reference scenes with independent ground-truth acceptance:
   outdoor/indoor environments, solo/group sprites, multiple clothing
   variants, front/side/rear contact actions, and crowded public scenes.
   Report false accepts and false rejects separately, plus CPU/GPU timings.
5. Add bounded, reproducible targeted inpainting for a localized failure,
   rather than throwing away an otherwise good whole CG; ensure final
   composited image must pass normal QA.

The system is **not** visually complete until these points are measured and
shown to improve the real test scenes without relaxing QA.


## Scene blocking and bounded repair (29 October 2026)

A versioned `visual_contract` is attached to new CG job specs by the shared
`src/scene-contract.mjs`. Named principals are distinct from anonymous extras;
explicit normalized actor regions are optional and never invented. Story
narration and local directing can supply `actor_region`, `crowd_policy`, and
`contacts` with named actors, target objects and optional target regions.
Changed positions/camera/contact invalidate stale CG and unset obsolete ROIs.
Old job specs without this contract remain supported.

`worker/scene_contract.py` validates cast and typed contacts before GPU work.
For explicit hand-to-object regions, DWPose can mark strong spatial separation
as a contradiction, while proximity is merely plausible (not contact proof).
Occluded/rear view faces are marked unobservable in QA evidence, not identity
verified. Production CLIP/VLM still decides according to existing hard gates.

`worker/local_repair.py` allows strictly bounded masked repair of a rejected
candidate only with a single, grounded ROI (identity, wardrobe or contact).
Rejects lacking a trustworthy ROI use the existing full retry workflow.
Candidates are local private files, SHA-verified and permission-restricted;
repair uses ComfyUI `VAEEncodeForInpaint` and `ImageCompositeMasked`, then
re-enters the unchanged full QA without bypass. A separate GPU smoke on a
neutral CG verified the output size and zero modification outside the selected
mask, but the visual accuracy of repair remains to be benchmarked at scale.

Florence-2 object detections in `scripts/qa-actor-objects.py` are diagnostic
only. They can support spatial occupancy/extras analysis when explicit actor
regions exist, but cannot verify character identity. This model is not loaded
by production and does not add overhead to normal render jobs.
