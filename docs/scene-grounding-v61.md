> **ТЕХНИЧЕСКИЙ РЕТРОСПЕКТИВНЫЙ ОТЧЁТ v6.1.** Основная проверка количества людей/локации остаётся актуальной, но маршрутизация арта и набор моделей изменились в v6.4. См. [RENDER-POLICY-v64.md](RENDER-POLICY-v64.md).

# mcp-vn v6.1 — verifying actual scene composition

This release repairs cases where a single-person forest portrait was accepted
for a two-person urban scene. Technical scene QA only: no content filters or
changes to the characters, story, clothing vocabulary or relationship rules.

## Root causes

The tiny vision model used to reply "Two." for both a correct two-person scene
and an incorrect solo portrait. Previously, CLIP identified the forest but
gave only a warning for the wrong location. Any completed PNG could become an
image-to-image reference or source for an optional animation.

## Technical fix

The existing CLIP model now independently scores principal-person count and
known environment categories. Contradictions fail QA, independently of
SmolVLM captions. The worker persists the measured count and location
verification fields in the job QA report. The frontend does not show a
technically complete but unverified frame as a correct current CG.

The next-frame seed and optional video source must be a completed neural
preview for the same episode whose independent count and location QA passed.
An old completed frame without these measurements is not a trusted source.
Location, cast, clothes and equipment changes disallow stale references.
Camera and pose changes start fresh from the current actor-state reference.
When moving to another place, never seed from the original market background.

A custom location without a supported classifier may still yield a viewable
preview when the character count is verified, with an honest note that its
location was not confirmed. It cannot seed further images or video until
grounded. No main-story assets or saved facts are changed by preview CGs.

## Calibrated samples from this installation

                       correct market     bad forest portrait
CLIP market            0.448              0.044
CLIP forest            0.011              0.468
two-person score       0.492              0.333
one-person score       0.209              0.397
result                 accepted           rejected

These values are model-dependent and do not prove accurate anatomy or exact
garments. The available CLIP model cannot reliably localize and identify
separate individual faces; IPAdapter identity anchors remain important.

Tests: python3 tests/scene-grounding.test.py and docker compose build game.
Before-change backup is in /opt/mcp-vn-backups under pre-semantic-qa-.
