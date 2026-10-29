# Render-v1 stabilization audit — 2026-10-29

**Decision:** safe to begin controlled human playtesting, **NOT** certified
render-v1. This file links to [the permanent roadmap](ROADMAP.md) and [GitHub
Issue #20](https://github.com/Riannoni/mcp-vn/issues/20).

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
