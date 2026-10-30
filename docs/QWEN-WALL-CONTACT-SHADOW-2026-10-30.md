# CPU VLM candidate for scene-action QA — 2026-10-30

**Status: experimental, uncalibrated, NOT DEPLOYED to working VN.**
Read `AGENTS.md` and `docs/DEVELOPMENT-AND-TESTING.md` first.

## Precise root cause

The old 500M SmolVLM caption can classify three independent incorrect hand
positions adjacent to masonry as hands touching a wall. It also misclassified
the correct wall brace as hands on the ground. Cropping the hands alone did
not fix the false positives. DWPose pose angles do not prove contact.

The original first-shot wall CG was independent-pixel reviewed: planted
feet, hip hinge, two outstretched palms against a vertical wall. The old
QA classified it as `ground-supported or kneeling pose` incorrectly.

## New independent test (no regeneration)

Installed **Qwen/Qwen3-VL-2B-Instruct**, Apache-2.0, locally in a private
4.255GB checkpoint on the PC; loaded on CPU, did not stop/replace existing
worker/vision/ComfyUI. Offline deterministic single-category hand-location
question, 768px maximum input dimension, 55 tokens maximum:

| Fixture | Expected | Qwen3-VL answer | Seconds |
| --- | --- | --- | ---: |
| Correct stone wall contact, original scene | WALL | WALL | 6.20 |
| Two further blue-outfit real wall-contact candidates | WALL | WALL, WALL | 6.18 / 6.21 |
| Real head-touch negative near wall | HEAD | HEAD | 5.89 |
| Real pavement-touch negative near wall | GROUND | GROUND | 5.56 |
| Real hands-at-sides negative near wall | SIDES | SIDES | 6.01 |
| Full CG holding map | PROP | PROP | 5.73 |
| Staged arch CG holding same map | PROP | PROP | 5.73 |

These are **8/8 human-viewed fixtures**, not eight independent game actions,
not the 30-scene release set, and not evidence of calibrated future accuracy.
Cold model load took 1.5s in the first test. One process peaked at ~9GB RAM.
Other models/providers are not touched.

## Full strict original-source QA test

A read-only worker-copy ran `assess` on the same actual original wall PNG
(with original live services untouched). With default vision-daemon
configuration, it correctly **rejected** the frame: location CLIP score
0.1766 was unobservable; no arbitrary Qwen rescue was attempted.

The independent Florence wall/market-stall detector then found a
non-occluded *left* region of the same image, covering 46.98% of width.
Unchanged `scene_location_evidence` and CLIP scores went from 0.1717
(full image) to **0.3936** (detector-grounded region), passing the existing
market threshold. There was no crop optimization/search for best CLIP.

With a second, disposable Florence-location-enabled vision daemon and opt-in
Qwen+DWPose+Florence arbitration, the same PNG returned:

- `qa_passed=true`, `semantic_status=passed`, 46.20s QA total
- `scene_location_verified=true`, location confidence 0.3851
- `scene_count_verified=true`, DWPose approved-rear pose verified
- Florence 2D hand/wall observation `plausible`; Qwen `WALL` in 6.50s
- Prior SmolVLM `ground_pose=true` / conflict preserved in redacted notes

This is **one experimental false-reject adjudication**, NOT production
verified contact. The 46.2s total is too slow for a desirable real-time turn.
It serially uses redundant models and needs profiling/optimization.

The 3 additional negative wall-action images all returned `reject` under the
full isolated worker, **but were rejected at earlier environment/semantic
checks**; this is NOT a decisive independent full-path false-accept test.

## Code boundaries and blockers

`worker/qwen_wall_shadow.py` is a local offline, lazy-loaded deterministic
categorical image observer. `worker/wall_action_arbitration.py` is a strict
pure predicate requiring: action mandatory, DWPose approved geometry,
independent Florence wall geometry `plausible`, exact Qwen `WALL`, both
count/location positive and exactly the single known Smol action error.
Unit tests check all negative categories and failure-closed conditions.

Do NOT merge a silent global SmolVLM bypass; `plausible` is not proof of 3D
contact. The full experimental worker patch is **local only** and not part of
this small model/arbiter helper commit. Before rollout: calibrate on a
human-labeled multiworld/action set, reconcile contradictory field-level
`scene_action_evidence` (never output QA pass and ground_pose=true together),
benchmark performance vs replacing SmolVLM rather than doubling passes,
check original game save fingerprint and version fence, run disposable
1 sprite + 3 CG first-try E2E and rollback test.

The original first-attempt milestone and render-v1 are **NO-GO**.
