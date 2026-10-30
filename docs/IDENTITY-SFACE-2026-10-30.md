# Independent face-identity QA — shadow experiment, 2026-10-30

**STATUS: experimental / no rollout / no acceptance authority.** Read
`AGENTS.md` and `docs/DEVELOPMENT-AND-TESTING.md` on `main` before changes.

## Reproduced problem

Generic CLIP image embeddings are not sufficiently selective to act as a
face-identity verifier. Seven previously curated, superficially similar
portrait examples scored 0.8439–0.9408 by generic CLIP but only
0.26565–0.41613 against the immutable canonical facial reference with
OpenCV SFace. Treat those seven as **identity-unverified, not a LoRA training
ground truth**. A successful facial score is not established by art style,
hair color or visual appeal.

At original sizes, the two first-attempt, wardrobe-correct masked sprites
scored 0.81484 and 0.80028 with SFace. An authored story CG with a map
scored 0.30851 (Klein) and a separate SDXL+IPAdapter attempt scored 0.32499;
a local generative facial repair fell to 0.20684. Canonical-to-canonical
control was 1.0, a brightness edit 0.9938 and horizontal flip 0.87967.
After resizing to game resolution, that same Klein CG scored 0.24465:
resize/ROI can change the score and all measurements must disclose it.

**These values are uncalibrated synthetic-character observations, NOT a
face-identification threshold or a substitute for independent visual review.**

## Implementation

`worker/identity_sface_shadow.py` provides opt-in, no-publish observation
via `VN_SFACE_SHADOW_DIR`. Only single unambiguous, visibly detectable faces
are measured; no face, multiple faces, corrupt/unlicensed model artifact,
missing reference or inconsistent output -> `unobservable`. It never sets
`qa.passed`, and cannot turn `unobservable` into `verified`.

The two ONNX files must be installed into an **isolated** private path, not
GitHub or a production container. Their SHA-256 values are pinned in code.
No dependency is installed into the production worker: tests use a private
`opencv-python-headless` target path and existing NumPy. Evaluation on one
CG took about 0.5 s including process setup with generative QA disabled.

OpenCV Zoo SFace and YuNet code directories have Apache-2.0 / MIT licenses,
respectively. Commercial provenance and redistribution rights of the specific
pretrained SFace weights have open upstream clarification requests (#313,
#318 at opencv/opencv_zoo). **Not approved for shipping** until resolved.

## Required next gate

Create independently human-labeled, multi-angle canonical references,
nonmatches, lighting and cropping negatives; avoid distilling drifted faces
into LoRA. Calibrate a semantic identity gate and false acceptance/rejection
before enabling it. Re-test first-attempt sprite and 3CG isolated gameplay,
with full visual review and timing. Do not merge/deploy based on these scores.

All input images, detailed per-frame measurements and actual saved story state
remain private on the PC. There was no canonical save or published asset write.
