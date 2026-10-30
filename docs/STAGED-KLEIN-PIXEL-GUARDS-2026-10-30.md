# Guarded compositing for native FLUX.2 Klein (2026-10-30)

**Isolated, source-ready, not deployed.** Read `AGENTS.md`, then
`docs/DEVELOPMENT-AND-TESTING.md` from GitHub `main` first.

## Failure modes reproduced and now preflighted

- A first version of the two-handed map CG showed **four hands** because
  dangling original sprite hands had only 48.08% and 39.62% of their detected
  bounding regions inside the editable mask. Its visually plausible map and
  new pair of hands were not sufficient for acceptance.
- The corrected mask allowed 100% of both old hand regions to be replaced,
  kept the canonical detected face bbox fully locked and yielded a coherent
  two-handed map after one private GPU run. Independent grounded DWPose and
  Florence observations returned `plausible` grip, not verified 3D contact.
- A later composition added a stone arch **only in environment sectors**,
  leaving the same actor/map pixels protected. The arch exists visually but
  independent full-frame landmark QA remains unobservable and the movement
  contract is not proven.

## Reusable component

`worker/staged_klein_scene.py` is a generic, game-neutral module. It validates
Comfy inverse-alpha edit permissions, explicit immutable face/prop regions,
source DWPose stale-hand coverage when a pose changes and expected dimensions.
It connects VAEEncode -> SetLatentNoiseMask and an explicit postdecode
ImageCompositeMasked to an existing *native* Klein graph without changing the
caller model, seed, prompt, sampling or other reference nodes. A separate
post-run integrity function verifies all pixels whose edit permission is
exactly zero against the source; even a single changed fully locked pixel
is a hard failure. This is a preflight/integrity guard only, **not** scene QA.

Real output validation with production-sized original private PNGs:

| Frame | Fully locked source pixels checked | Changed locked pixels |
| --- | ---: | ---: |
| Two-handed paper map | 525,798 | 0 |
| Stone arch with unchanged actor/map | 402,607 | 0 |

The earlier incomplete hand mask fails the guard. The corrected hand mask
passes while preserving the actual detector-grounded face bbox. Six module
unit tests pass; no threshold was changed, no GPU generation was triggered
by testing this refactored module, and no working service was modified.

## Scope and release block

This module is **not yet wired into the worker's live scene dispatcher** and
has no automatic game/save writes. It does not validate outfit/identity,
contact, view, pose, environment landmarks, extra limbs or scene fingerprints
beyond the provided protected regions. A valid mask can still create bad art.
Full `worker.assess` and independent pixel review remain mandatory.

The accepted shadow **map** example met existing scene/location/object gates
and looked plausible on direct original-pixel inspection, but the staged arch
example still failed the unmodified landmark QA, and movement under it is not
verified. Do not claim the required first-attempt 1-sprite + 3-CG complete
sequence, golden set or production release succeeded.

Next: attach the staged plan to a **disposable game** with explicit typed
actor/item/view/pose, an approved reference, immutable source-state version
fence and no-publish dry-run; calibrate independent relation and landmark QA
on ground-truth cases before enabling any publishing. Source images, original
story references, detailed prompts and asset URLs stay private on the PC.
