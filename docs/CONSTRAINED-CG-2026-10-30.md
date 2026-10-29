# Constrained CG regression: live wall-contact failure (2026-10-30)

## Actual baseline / reproducible failure

Pilot Ash Gate scene: a named adult principal in the outdoor market, standing with both hands pressed against a vertical stone wall. The canonical save must not be changed during regression tests; clone the current game JSON and give the clone a distinct UUID; share immutable assets by reference. The old published job `8adb5e7b-b66a-46c4-902c-9e1cc9e786d1` reported `wall_touch=false`, `both_hands=false`, `forward_lean=false`, but `qa.passed=true`, because the worker downgraded missing contact evidence to a warning. The job took 54.2 seconds.

The initial disposable E2E replay `7216e406-0275-4c9c-92da-6607b750ea10` (game clone `206b7c02-529a-4864-b06f-5500ada2d28e`) failed as expected, with independent wardrobe/pose issues and **no publication**, after 2 attempts / 92.8s. These measurements demonstrate blocking, NOT a correct final image. The main save was unchanged at the time of comparison.

## Shipped hotfix and limits

- In `worker/worker.py`, mandatory explicit wall contact cannot be published if `scene_action_verified` is not `True`. A matching DWPose skeleton alone is not contact evidence.
- In `worker/vision_daemon.py`, positive, sufficiently specific captions can be reused; otherwise a dedicated pose/contact question is asked. Distinguishes unknown from confirmed.
- A regression test `tests/qa-stage-order.test.py` now expects rejection when contact is unverified, rather than incorrectly expecting success.
- Status remains **NOT solved** until an image both visually matches action, wardrobe and location, and passes independent QA with recorded latency.

## Compared OSS patterns — do not add gratuitous dependencies

1. [Krita AI Diffusion](https://github.com/Acly/krita-ai-diffusion): selection and editable regional masks; scene-preserving inpaint. The worker already has `local_repair.py` for targeted retry, but the current physical-contact `visual_contract.contacts` has no `target_region`, so the repair cannot isolate the wall and hands. **Next**: validated explicit actor/contact ROIs before using the existing SDXL inpaint path, not guessed coordinates.
2. [IPAdapter Plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus): image identity guidance with `attn_mask` spatial localization. The neural CG worker **already** applies regional face identity and lowers face weight for rear views; do not install a duplicate implementation or assume identity guidance enforces action.
3. [ControlNet / DWPose](https://github.com/Mikubill/sd-webui-controlnet) and [Diffusers documentation](https://huggingface.co/docs/diffusers/main/using-diffusers/controlnet): structural pose conditioning and skeleton verification. The existing approval manifest correctly requires an **exact** action/view match, an approved guide, hashes and reviewed A/B. The requested `palms_on_wall` + `rear` lacks an approved guide; available drafts are not production qualified. `palms_on_wall_hip_hinge` + `rear` is approved but physically different. Do not silently substitute one for the other.
4. [ComfyUI Impact Pack](https://github.com/ltdrdata/ComfyUI-Impact-Pack): SAM and regional/SEGS refinement are candidates only if the existing bounded inpaint proves insufficient; measure dependency, GPU and security costs first.
5. [GenEval2](https://github.com/facebookresearch/GenEval2): atomic object/count/attribute/relation checks. For mandatory contact, `verified` must be a positive assertion, `unobservable` must not be promoted to passed. Single small caption model is not reliable enough to infer actual physical touch.

## P0 implementation and validation backlog

- Generate and human-review matching `palms_on_wall` + `rear` guide from authorized reference; paired same-seed A/B with/without ControlNet and visual inspection, then approve local manifest only with recorded QA/evidence.
- Parse an explicit actor ROI and wall-contact ROI in the Scene Contract; associate both wrists to named principal, not background crowd. Do not infer target wall from a vague image caption.
- For constrained actions, seed with the accepted canonical location, mask and inpaint the actor/contact area when bounded valid ROI exists. Current background-grounded neural CG and per-face masks are already implemented; benchmark incremental change rather than rebuilding it.
- Detect whether the image is action-correct and wardrobe-correct before publish, not just aesthetic/CLIP setting similarity. Keep failed candidates private; retry based on failure class, with bounded budget.
- Run an isolated same-save replay; capture redacted timings and QA for each attempt, inspect output, compare P50/P90 across golden set. Preserve canonical save and immutable assets. Record rollout SHA, rollback, and remaining uncertainty in [#20](https://github.com/Riannoni/web-vn/issues/20).
