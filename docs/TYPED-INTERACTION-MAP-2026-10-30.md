# Two-handed map interaction — isolated typed blocking test, 2026-10-30

**Status: SOURCE EXPERIMENT, NOT DEPLOYED, NOT FULL-GAME E2E.** Read `AGENTS.md`
then `docs/DEVELOPMENT-AND-TESTING.md` before acting on this report.

## Observed root causes

A generic text request to hold a map allowed a model to create a correctly
recognized map while leaving one hand below it. The first head-locked staged
image with a separate hand-target pose-reference rendered with *both new hands*
near the map edges, yet the two original down-hanging hands from the source
sprite remained: a four-hand CG. The prior inpaint mask covered only **48.08%**
and **39.62%** of the independently detected old hands. Neither generic
caption nor a two-hand DWPose report discovered this artifact reliably.

## Changed one factor per private experiment

Source: same canonical foreground character and approved market background,
with native Klein 4B, source plate bytes and seed 2026103062 fixed; no
live state/write/publish. Face pixels protected by the source mask.

| Variant | Changed factor | GPU once | Face SFace, native | Independent findings |
| --- | --- | --- | --- | --- |
| Existing explicit grip text | baseline upper-body mask, face ref | 4.01s | 0.8573 | one hand below map; fail |
| Draft pose reference | **one added ReferenceLatent** from explicit two-hand guide | 8.01s | 0.8580 | new hands grip map, but original two hands remain; fail |
| Expanded displaced-hand mask | only extend edit mask around previously hanging hands | 8.01s | 0.8580 (pre-resize) | old hands gone; coherent two-hand map image |

Mask coverage before/after on actual original source DWPose: left 0.4808 ->
1.0000, right 0.3962 -> 1.0000. Verified that **zero pixels** outside
strictly protected source mask were altered in the pose-reference test.

On final private candidate, DWPose found 21 hand joints on each of the two
map-gripping hands; independent Florence-2 localized the paper map and gave
a compatible description; `map_grip_evidence` classified both hands near
opposite map edges as **plausible**, not a 3-D physical-contact proof.

An isolated full-frame `worker.assess` using the existing strict gates and
an opt-in independent Florence verifier returned `qa_passed=true`, no reasons,
verified principal count/location/required map object; face SFace was 0.85176
after resizing to native game canvas. This is **one independently inspected
private G2 candidate**, not a sequential first-attempt game test and not a
calibrated identity metric. Skin/wardrobe/cartographic detail still need the
independently defined first-attempt release suite.

## Added pure, fail-closed preflight components

- `interaction_blocking.py`: typed actor + object ID, front-view camera, map
  rectangle, left/right anatomical wrist targets and validated geometric
  relations. Builds only a version-hashed DRAFT pose (no automatic approval).
- `source_hand_mask_guard.py`: accepts only independently observed source
  hand keypoints and an explicit edit mask; refuses a plan with old hands
  outside the editable region, preventing duplicate limbs before GPU.
- Four unit tests for each component, including missing actor/hand, misplaced
  wrist and one partially locked old hand. The mask guard is not a proof that
  new limbs are correct.

This patch does NOT wire draft guides into the production dispatcher and
never broadens the existing QA pass criteria. Do not promote `plausible` to
`verified`, disable scene action checks, or treat the previous sample search
as a genuine one-pass system acceptance test.

## Remaining requirements

A scene/actor-agnostic typed interaction planner, independent multi-person
attribution, accepted front/side/rear guides, negative set for extra limbs,
calibrated identity conditions, real one-shot disposable-save 1 sprite + 3 CG
end-to-end, integrity/version fence, speed and restart/rollback. This branch
remains NO-GO. Private images, person/canon/source references and prompt IDs
are stored solely on the PC.
