# Visual QA implementation and shadow-model measurements — 29 October 2026

## Deployment status

Production home game server and PC worker/vision services were updated after
backing up existing code. No active job or story save was modified. The currently
published service remains **CLIP ViT-B/32 + SmolVLM2-500M on CPU**; candidate
models remain **shadow-only**, not live acceptance gates.

### Production changes

1. A scene's CLIP image representation is computed once per image and shared
   by environment, count and action-contrast tests. Image classifiers,
   candidate thresholds, score normalization and acceptance logic are otherwise
   unchanged.
2. Fixed a false-rejection bug: sentences like "A man ... with a woman" must
   **not** be interpreted as an assertion of one person. A caption now rejects
   an expected pair for cardinality only when it clearly asserts "only one",
   "a single" or "a lone" person. Existing independent CLIP count gates
   remain in place. Regression tests cover both cases.
3. The job service preserves priority QA scalar metrics even if unrelated
   metrics overflow the 32-scalar limit.
4. QA reports now persist a bounded versioned `qa.evidence` object for count,
   location, identity and physical action. Verdicts distinguish verified,
   violated and unobservable. This is descriptive telemetry, **not** a new
   permission to publish: existing fail-closed rejection rules remain intact.
   Images, raw prompts, and arbitrary model-provided fields are not stored
   in the evidence object.

### CPU model experiments

On the actual workstation (Ryzen 7 9850X3D, 30 GiB RAM, RX 9070 XT)
using four prior private, neutral CG model-comparison PNGs:

| CPU candidate | Median (4 images) | Work measured | Production |
|---|---:|---|---|
| Current SmolVLM2-500M | 13.47 s | Full local `/judge` call, including CLIP, VLM and postprocessing | Yes |
| Qwen3.5-0.8B | 8.69 s | One brief caption, 100-token cap | No |
| Florence-2-base-ft (native community port) | 2.33 s | One `MORE_DETAILED_CAPTION`, 100-token cap | No |

**These are not like-for-like QA benchmarks.** Model-only captions are not
complete quality verification; no human-labeled accuracy set has been scored.
Both new models miscounted or misdescribed parts of some frames. Do not infer
that lower caption time means lower total render time or superior accuracy.
None are suitable as an automated replacement without an A/B accuracy study.

- Model cache on workstation: `Qwen/Qwen3.5-0.8B`,
  `florence-community/Florence-2-base-ft`, and the original
  `microsoft/Florence-2-base-ft` download.
- The original Microsoft Florence weights currently produce an incompatible
  tokenizer/processor pairing under our Transformers versions. The community
  native conversion loads using Transformers 5.22.0.
- Shadow environment: `~/.local/share/mcp-vn/qa-shadow-venv/`;
  production environment remains `~/.local/share/mcp-vn/venv/`.
- Repeat neutral local comparison:
  `HF_HUB_OFFLINE=1 ~/.local/share/mcp-vn/qa-shadow-venv/bin/python
  ~/.local/share/mcp-vn/qa-shadow-benchmark.py qwen
  ~/.local/share/mcp-vn/benchmark-models/pony.png`
  (substitute `florence`; CPU-only, read-only images).
- Setup is reproducible from `scripts/setup-shadow-qa.sh` and
  `scripts/qa-shadow-benchmark.py`. The shell script is specific to the
  existing PC Python 3.14 layout and should be generalized before public use.

### Reproducible false-rejection regression

Baseline on two existing CGs (same image bytes and scene spec):
- `illustrious.png`: SmolVLM description mentions a man kneeling next to a
  woman. Before: **failed** (false "only one"). After: **passed**.
- `zimage.png`: SmolVLM description mentions a man with a woman near a
  market. Before: **failed**. After: **passed**.

CLIP verified two figures in both before and after. The change does not
alter thresholds or let a genuinely explicit solo caption pass.

### Verification and rollback

- Docker build executed the full Node suite: **135/135 tests passed**.
- Python caption and CLIP reuse regressions passed.
- Read-only live PC QA on the two prior false-reject images passed after
  deployment; game HTTP health and CPU QA health were good.
- Home code backup:
  `/opt/mcp-vn-backups/20261029-qa-v2/`
- Previous game image:
  `mcp-vn-game:before-qa-20261029-qa-v2`
- PC code backup:
  `~/.local/share/mcp-vn/backup-20261029-qa-v2/`

Restore PC files from the backup and restart only the worker and vision
user services, and restore the old game image if a rollback is required;
never overwrite `/opt/mcp-vn/data` from an older backup.

### Not complete, not claimed complete

The remaining hard problems require image-ground-truth evaluation:
- Named principal figures vs background extras in a crowded scene;
- Occluded/rear-facing identity anchors;
- Physical contact attribution between an exact hand and a real object;
- Tested masked region inpainting instead of full-frame retry;
- Story-agnostic scene blocking graph (actors/objects/surfaces) suitable
  for future multiple independent games.

Do not use a low CLIP value alone to publish a character mismatch, nor
promote Florence or Qwen to acceptance automatically. Build a private
human-labeled evaluation set and measure false accepts, false rejects,
unknowns, latency P50/P90 and whole-turn latency before modifying the
production decision policy.
