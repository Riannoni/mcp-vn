# Render-v1 stabilization audit — 2026-10-29

**Decision:** safe to begin controlled human playtesting, **NOT** certified
render-v1. This file links to [the permanent roadmap](ROADMAP.md) and [GitHub
Issue #20](https://github.com/Riannoni/web-vn/issues/20).

## Implemented in this change set

- Mandatory semantic QA availability for new sprites and neural CG, with a
  regression that fakes an offline vision daemon; do not publish under
  technical-only success when semantic verification was required.
- CLIP count logic takes the versioned crowd policy into account. Ambient
  anonymous extras may exceed the named cast count; this is compatibility
  evidence, not verified facial identity. Solo imagery must not pass an
  expected two-person scene.
- Explicit per-principal actor regions can be used by 1–4 local CG
  IPAdapter masks; earlier code applied masks to only two people. Stage
  fallback and real 3–4 person visual quality still need calibration.
- Face similarity bypass requires corroboration of occlusion by scene
  description in addition to requested pose. Hidden face never becomes
  face-identity verified.
- Scene-location evidence no longer reports strongly indoor CG as a
  verified outdoor market merely because forest/urban CLIP tests pass.
  Ambiguous location scores are unverified; a human-labeled false-
  positive/false-negative corpus is still necessary.
- CPU-only versioned QA environment text banks for fantasy, modern and
  science-fiction settings; default fantasy label text unchanged.
  Multi-world integration in imports remains future work.
- Comfy manifest: permission-restricted job ID / prompt ID / attempt
  / workflow digest. Restart path resumes a known accepted prompt; image
  outputs are read by exact history reference, not latest glob. This is
  best-effort deduplication, not crash-proof exactly-once across POST/fsync.
- GitHub Actions build/test/static checks; Python/Node tests are isolated
  from real saves. CI run results require verification after publication.
- Weekly cleanup timer for aged ComfyUI temp files with 30-day retention,
  allowlisted names, empty-queue check and dry-run command. Initial dry run
  found zero deletable files; canonical assets untouched.
- Read-only historical performance CLI. Post-upgrade end-to-end latency,
  TTFT, and numerical QA quality still require real measurements.

## Verified checks

- Node Docker build 141/141 tests successful.
- Python test-file run on isolated PC source copy: 33/33 files passed;
  separate 14/14 VN Web tests passed.
- Offline QA service regression for sprite passed.
- A stubbed Comfy history test confirmed a repeated call reuses the same
  saved prompt ID (one submit, two reads).
- Production worker, CPU vision daemon, ComfyUI, model lab and home API
  responded to health checks after deployment. Queue was empty on rollout.
- Live read-only QA replay of three prior neutral CGs: 12.78 s, 12.72 s,
  12.96 s, respectively. The strong indoor/market contradiction discovered
  in replay motivated the additional location-evidence fix.
- The prior masked ComfyUI repair smoke preserved all pixels outside mask,
  but a new full end-to-end post-release repair+publish has not been run.
- Backups: /opt/mcp-vn-backups/20261029-p0p1 and desktop worker
  backup-20261029-p0p1; previous container tagged before-20261029-p0p1.

## Remaining open gates (not to be disguised as complete)

- **P0-01 #2:** 30 independent human-labeled images and measured false
  accepts/rejects, including cast-in-crowd and cross-genre location.
- **P0-02 #3:** principal identity remains unproved by global CLIP score
  alone; Florence is a shadow-only regional occupancy diagnostic.
- **P0-04 #5:** visual A/B for local CG 3–4 person regional identity and
  reference failure cases (no silent degradation).
- **P0-05 #6:** temporary disposable game with the entire GPU/QA/retry/
  server publication loop and simulated crashes.
- **P1-01 #7:** accurate real image-level face occlusion and hand-object
  contact requires a labeled benchmark; pose proximity is insufficient.
- **P1-02 #8:** CI workflow is authored, but remote GitHub check must run.
- **P1-04 #10:** restart during POST-before-manifest-fsync still risks
  duplicate GPU work; server lease reclaim is not immediate.
- **P1-05 #11:** imported story profiles and environment prompt ontology
  still need a fully data-driven path, not only configurable CLIP labels.
- **P1-06 #12:** complete turn TTFT and stage p90 targets not yet proven.

## Human test checklist

Use a test save or explicit disposable playthrough, not an irreplaceable
run. Try: familiar room/background, repeated conversation without
rendering, wardrobe/pose change, two people with bystanders, contact
near a wall, rear-facing sprite, new location, then one retry. Note
image arrival latency, incorrect figures, false rejections and
whether the old accepted image is preserved during a failed retry.
Do not assume a passing static or QA status proves visual correctness.

The decision to continue the Kagesekai importer (#17/#18) remains
deferred. Streaming text (#13) is an explicit future workstream, with
atomic canon and recovery requirements documented in the roadmap.

Additional after-deployment regression: a saved image with strong indoor CLIP evidence (0.661) for outdoor_market_square now returns failed with a location conflict, while the prior build returned passed; no private image is committed.

## Disposable live GPU canary, post-release

A new isolated Ash Gate test session was created only for validation.
- Background: completed/applied on first attempt in 8.08 s, QA passed.
- First sprite: completed/applied on first attempt in 40.67 s, of which
  18.71 s postprocessing and 10.87 s semantic QA.
- First neural CG: completed in 51.04 s after two attempts, but
  visually WRONG despite qa.passed=true: a studio-gray portrait with a
  clipped duplicate person, missing market environment; location evidence
  marked unobservable and strongest CLIP category was underground cave.
- Immediate P0 fix: known environment on neural CG must explicitly verify
  scene_location_verified or reject. Generation now uses the accepted
  background as a bounded SDXL img2img seed instead of EmptyLatentImage.
- Second neural CG: completed in 25.21 s, correct outdoor market and
  location+principal count evidence verified. However visual inspection
  found a second small similar-looking green-cloaked figure — potential
  duplicated principal among extras, not reliably detectable by current QA.
- Follow-up: solo principal face IPAdapter is now region masked rather
  than applied globally; quality improvement pending the final third canary.

The image bytes and the test playthrough are not published in GitHub.
This audit explicitly blocks any claim that duplicate principals are solved.

## Final disposable canary and remaining visual defects

- Third CG with bounded solo IPAdapter face region: **done/applied** first attempt,
  total **25.16 s**, both count and outdoor market location evidence verified.
  Visually the duplicated same-looking background character disappeared in
  this **one example**; this does not establish general duplicate detection.
- Remaining significant error: the green cloak was depicted partly open,
  exposing a larger portion of the body than the established character
  wardrobe; QA still passed. New P0-07 issue #23 requires grounded garment
  state and visual-continuity checks, with explicit controls for unclothed
  scenes rather than arbitrary censorship.
- The entire disposable playthrough was removed after confirming every
  job was terminal and its assets were not referenced by any other game:
  exactly 1 temporary game, 5 jobs, 6 isolated assets; private manifests
  for the five jobs were also removed. Existing saves were not changed.

**Conclusion:** subsystem regression and complete smoke are demonstrably
working, but render-v1 is not certified. The project is suitable for human
exploratory playtesting, where new image flaws should be recorded against
#2, #3, #21, #22 and #23.

Final post-canary regression suite: Node 141/141, PC Python test files 35/35, VN Web Python tests 14/14; API/worker/vision/comfy/model-lab active and no queued GPU jobs. GitHub Actions CI status was not independently confirmed.
