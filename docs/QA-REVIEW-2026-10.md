# Visual QA research and alternatives (29 October 2026)

Historical research baseline. See [QA-IMPLEMENTATION-2026-10-29.md](QA-IMPLEMENTATION-2026-10-29.md) for deployed optimizations, shadow-model measurements, verification and remaining work. Production models remain unchanged.

## Actual baseline

The local workstation runs a warm CPU-only QA process with CLIP ViT-B/32 and SmolVLM2-500M. Hardware inspection: 8 CPU cores (Ryzen 7 9850X3D), 30 GiB RAM, one Radeon RX 9070 XT. The current QA process held approximately 2.4 GiB resident memory.

Historical job QA duration samples (seconds):

| Kind | Samples | Median | P90 |
| --- | ---: | ---: | ---: |
| Background | 11 | 0.1 | 0.1 |
| Sprite | 150 | 0.1 | 13.2 |
| Scene CG | 92 | 13.5 | 39.9 |
| Local CG | 37 | 10.2 | 31.1 |

Not a controlled A/B benchmark. A short reported QA duration is not evidence all semantic checks were executed.

## Implementation findings

1. The current visual daemon executes up to several sequential SmolVLM requests per complex scene (generic caption, retry of incomplete caption, physical-contact query). These calls amplify CG QA latency.
2. CLIP image features are recomputed for environment scores, principal-count guesses and scene/action contrast. Cache the embedding once per image and reuse it for the label banks.
3. CLIP total human-count labels do not identify story protagonists separately from background extras. This directly confounds principal-count verification in busy scenes; do not weaken the threshold.
4. QA location labels use medieval European market/street descriptions. The market environment prompt includes the fixed instruction "pedestrians absent". Both contradict a correctly rendered, populated street/market and do not generalize to other games.
5. DWPose joints alone do not prove physical contact with walls or objects; SmolVLM2 captions can also miss/guess contact. Use detection/segmentation of the contacted object and explicit contact geometry, and distinguish verified / violated / unobservable.
6. CLIP ViT-B/32 face similarity is not a specialized identity verifier. The 0.80 cutoff was not calibrated on the target data. Treat rear or heavily occluded faces as unobservable rather than as proven matches/mismatches.
7. The game server currently persists a limited set of scalar QA metrics (first 32 scalar fields). Structured evidence and pose/contact reports are not retained in full. Add a bounded, versioned QA evidence artifact.
8. Entire CG re-generation discards correctly generated regions. Prefer a masked, context-aware local repair pass followed by the same strict final QA.
9. Keep story-state constraints and physically observable facts separate from narrator artistic direction. A typed scene plan needs actor positions, intended contacts, surfaces/objects, camera, wardrobe, crowd policy and identity anchors.

## Open-source implementations and concrete lessons

- TaleWeaver (https://github.com/TaleWeaverAdmin/TaleWeaver): its source in backend/narrative.py and backend/prompts.py separates per-asset prompt generation, active appearance and story context. It explicitly permits only small ambient extras in public markets; compare with our hardcoded empty markets. backend/comfy_client.py supports modular API workflows.
- Krita AI Diffusion (https://github.com/Acly/krita-ai-diffusion): region prompts, control layers, selective inpainting, incremental refinement and masking rather than full-frame re-rolls. See docs/src/content/docs/regions.mdx and ai_diffusion/model/model.py.
- ComfyUI Impact Pack (https://github.com/ltdrdata/ComfyUI-Impact-Pack): bbox/object segmentation and FaceDetailer/MaskDetailer local repairs.
- SillyTavern image generation (https://docs.sillytavern.app/extensions/stable-diffusion/): separate image modes and mode-specific prompt templates (background, scene, character, last message).

## Model candidates (not benchmarked on our hardware)

| Model | Potential advantage | Key limitation |
| --- | --- | --- |
| Florence-2-base, 0.23B | phrase grounding, object boxes, region descriptions | box proximity alone does not prove physical contact |
| Qwen3.5-0.8B | newer compact multimodal judge | CPU speed and factual errors unknown; runtime dependencies need testing |
| InternVL3.5-1B | small more capable candidate VLM | CPU latency remains unknown |
| Qwen3-VL-2B | stronger occasional visual judge | resource cost and possible GPU competition with ComfyUI |
| Moondream2 | detect/point/caption/segment interface | 2B large for always-on CPU; 0.5B intended for task-specific distillation |
| Current SmolVLM2-500M | installed, warmed baseline | poor multi-step physical reasoning and repeated question latency |

Sources: https://huggingface.co/microsoft/Florence-2-base ;
https://huggingface.co/Qwen/Qwen3.5-0.8B ;
https://huggingface.co/OpenGVLab/InternVL3_5-1B ;
https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct ;
https://moondream.ai/models .

A third-party comparison on unrelated CUDA hardware found Qwen3-VL-2B faster for some fixed tasks but slower in long-answer tails; this CANNOT be extrapolated to our CPU. https://github.com/AlbertXXuu/OpenMultimodalLab/blob/main/docs/reports/2026-07-31-qwen3-vl-vs-smolvlm2.md

## Recommended path

1. Freeze a private, human-labeled, reusable benchmark of backgrounds, sprites, CG with single/multiple principals and background extras, correct/incorrect clothing, and explicit/occluded physical contacts.
2. Measure false acceptance, false rejection and unknown separately from latency. Report P50/P90 of QA and full turnaround.
3. Optimize existing CLIP embedding reuse and remove redundant caption prompts without changing acceptance policy.
4. Experiment with CPU Florence-2-base for object grounding and with compact Qwen3.5-0.8B or InternVL3.5-1B for one-shot structured semantics in isolated shadow mode. Keep current QA in production.
5. Introduce explicit actor-vs-extras attribution and contact-surface geometry. Use a stronger VLM as escalation only when the cheap specialists cannot decide.
6. For localized failures, add bounded mask-aware repair and revalidate the final composite. Preserve all rejected candidates and evidence for diagnosis.
7. Promote only if serious false accepts do not increase, false rejects improve, and measured turnaround P50/P90 is no worse than baseline. No threshold weakening to manufacture success.

No new model should be installed or deployed based solely on parameter count or external marketing benchmarks.
