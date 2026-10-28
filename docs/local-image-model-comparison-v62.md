> **ИСТОРИЧЕСКИЙ ТЕСТ v6.2 (не текущая конфигурация).** В таблице фигурируют модели, которые позднее были заменены или удалены. Актуальные модели и пользовательские выводы — в [MODELS.md](MODELS.md), технические ограничения — в [ARCHITECTURE.md](ARCHITECTURE.md).

# mcp-vn v6.2 — local image model comparison (2026-10-28)

## Environment

- PC: AMD Radeon RX 9070 XT (16 GB VRAM), Bazzite, ROCm 7.2, ComfyUI 0.18.1.
- Generated images are local and have not been published or attached to saved games.
- Benchmark location: `/home/Xavok/.local/share/mcp-vn/benchmark-models/`.
- Identical fixed seed: 20261028; output resolution: 1024×768.
- Common neutral scene: two different adult travelers in an outdoor medieval
  market, woman kneeling while handing a map to a man seated on a bench.
  Prompts have style-specific photography/anime prefixes.
- The CPU CLIP score is **advisory only**; it is not evidence that the actual
  physical actions, count of people, or garment state are correct.

## Results (one sample per model, not an accuracy benchmark)

| Model / rendering | Seconds | CLIP action contrast | Manual inspection |
|---|---:|---:|---|
| CyberRealistic Pony v18 / SDXL | 7.52 | 0.7611 | Three people instead of two; no map hand-off |
| Illustrious XL 2.0 / SDXL | 15.02 | 0.6698 | Two people, incorrect postures and no actual hand-off |
| Anima Base v1.0 / Anima | 19.53 | 0.9339 | Four-pane comic collage, not one continuous frame |
| Z-Image Turbo / community FP8 scaled | 13.52 | 0.8373 | Two people, correct kneeling/seated poses and shared map; hand-off direction reversed |
| FLUX.2 Klein 4B / flow transformer | Not tested | — | Files installed and recognized; no generation result established |

All four generated images above were marked `passed` by the existing
count/location CLIP heuristic, even when the image was obviously incorrect.
This demonstrates the need for independent object detection and stronger
pose/action grounding. The highest action contrast (Anima, 0.9339) occurred on
an incorrect four-panel output; **do not rank models by that score**.

## Compatibility and safety of deployment

- Pony v18 and Illustrious 2.0 are SDXL-compatible.
- Anima uses `UNETLoader`, Qwen3 0.6B CLIPLoader, and Qwen Image VAE.
- Z-Image uses a Lumina2 Qwen3 4B text encoder, AuraFlow model sampling,
  and an SD3 latent. The original Comfy-Org INT8 ConvRot checkpoint failed
  to load on this machine: `KeyError: int8_tensorwise`. This format requires
  ComfyUI >=0.27 and optimized NVIDIA kernels; the machine runs 0.18.1 with
  ROCm. A community FP8-scaled checkpoint did load and render successfully.
  FP8 file SHA-256: `7ca63396607ef00904f3bd33e8ec3d4e362f225424f8c2e36b1aeb2d7c6390ee`.
- FLUX.2 Klein 4B uses the FLUX.2 latent/scheduler, a Qwen3 4B text encoder,
  and its own VAE; it must not be supplied to the SDXL CheckpointLoaderSimple.
- Anima is non-commercially licensed, Klein 4B is Apache-2.0.
- Z-Image and Klein in particular need a **different** graph and a distinct
  continuity strategy from SDXL IPAdapter before integration into active play.
- Saved games and the active production CG model are unchanged. Pony is still
  the production engine of the v6.2 local preview lane.

## Sources

- https://huggingface.co/circlestone-labs/Anima
- https://huggingface.co/OnomaAIResearch/Illustrious-XL-v2.0
- https://huggingface.co/Comfy-Org/Z-Image-Turbo
- https://huggingface.co/tsqn/Z-Image-Turbo_fp8_comfyui
- https://huggingface.co/Comfy-Org/Flux-2-Klein-4B
- https://github.com/Comfy-Org/workflow_templates

## Findings and next integration steps

1. Z-Image's single neutral text-to-image test was most spatially faithful.
   Keep its checkpoint installed as an experimental optional renderer, but do
   not replace Pony blindly: exact fictional identity preservation and more
   difficult interactions still require A/B evidence.
2. Preserve independent per-character identity, and implement a separate
   transformer-based ComfyUI graph for Z-Image/Klein; never treat them as SDXL.
3. Replace the misleading `scene_count_verified` claim based solely on CLIP
   with a calibrated detection/grounding method; detect multiframe collages.
4. Benchmark several seeds, outfit transitions and revisits before enabling
   a new engine automatically, reporting actual screenshots alongside scores.
