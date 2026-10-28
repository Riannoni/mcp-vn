# v6.4 — selective visual rendering and Cydonia episode narrator

Deployed to the home VN server and the Bazzite RX 9070 XT worker on 2026-10-28.

## Render policy

The pure module src/render-policy.mjs chooses a single lane after local narration and visual planning:

| Mode | Reason | Work |
| --- | --- | --- |
| none | Unchanged picture, speech-only change, or minor expression while an accepted CG remains visible | No GPU work |
| sprite | Face expression/small gesture changes in a layered scene | Only affected character sprite(s), unless cached |
| cg | Significant body contact, position/wardrobe/cast/location or explicit camera change | One whole-scene CG, NO extra new sprite generations |

The director sets physical continuity state but cannot directly force GPU jobs. Every decision is recorded with a human-readable cause, generated job IDs and cache flag, visible in local_episode_status and in the v6.4 player UI. Manual regenerate intentionally bypasses the cache.

The new CG uses existing canonical face assets (SDXL/Pony/WAI regional IPAdapter where available) and a persistent character/wardrobe state. It does not render two independent full-length sprite previews before every CG. For Anima, SDXL-only adapters do not apply; native Anima continuity remains a quality limitation.

## Cache

- SHA-256 signature for each visual scene: style, cast, physical action, pose, clothing, camera, location, lighting.
- Cached CG requires status done, correct session, a completed asset, and the existing independent QA checks (principal count and location). An identical accepted scene can reuse its original CG.
- Sprite signature includes name, style, clothing, expression, pose, equipment and location. Accepted independent sprite variants remain as private previews and can be reused. Small left/right positional adjustments reuse existing sprites and change only their DOM position, with no GPU work.
- Existing persistent location/time/weather background cache and canonical sprite variant cache remain active.
- The PC worker now has a bounded RAM LRU for immutable reference image bytes (VN_ASSET_CACHE_MIB defaults to 128 MiB, max 256 MiB, each admitted image below 12 MiB). Images are decoded afresh, so transformations cannot mutate the cached reference.
- The RAM cache reduces duplicate network fetch/decode work, but does not lower diffusion quality or keep big checkpoints hot. All GPU memory is shared with ComfyUI/ROCm LLM inference.

## Screen and GPU

Local CG defaults to portrait 896x1152; canonical backgrounds and traditional CG remain landscape. By default scene images use object-fit:contain to display the whole image, and the user can select fill (cropped) through the new stage toggle. Responsive letterboxing is expected.

Measured neutral Pony private CG at 896x1152: 13 seconds, correct dimensions, temporary output removed. No claim that all body poses or exact character interactions are independently verified — current QA is primarily count/location oriented.

## Narrator

Cydonia 24B v4.3 IQ4_XS is the primary model for PRIVATE local-episode narration, while Qwen3.5 9B remains the structured visual director and the fallback on model failure or textual quality retry. Main ChatGPT-hosted story narration is NOT switched.

Env settings (in compose.yaml):
VN_LOCAL_NARRATOR_MODEL=cydonia:24b-v4.3-iq4_xs
VN_LOCAL_NARRATOR_FALLBACK=qwen3.5:9b-q4_K_M
VN_LOCAL_MODEL_ID=qwen3.5:9b-q4_K_M

Existing shared GPU coordination remains enabled. Keeping the 24B checkpoint loaded all the time would crowd 16 GiB VRAM and was not enabled.

## Verification and rollback

- Build: 98/98 Node tests.
- Existing Python QA tests: 5 scene-grounding and 3 visual-contract tests.
- New renderer tests cover CG versus sprite versus reuse and unchanged canonical image state.
- Worker RAM reference cache test on PC: 2/2.
- Production healthz returned version 0.6.4.
- Existing local-episode save version 199 and its 56 transcript messages were left intact, last accepted CG displayed after upgrading.
- New UI resource key: visual-novel-v64.html; ChatGPT plugin may need refreshing to discover open_game_v64.

User's predeploy save and local-episode backup:
  /opt/mcp-vn-backups/pre-v64-deploy-20261028T110312Z/
Previous working source revision: 9b91a22
PC worker prior file: ~/.local/share/mcp-vn/worker.py.backup-v64-router
Source snapshots:
  /opt/mcp-vn-backups/visual-render-router-20261028T104931Z/
  /opt/mcp-vn-backups/visual-ui-router-20261028T105326Z/
  /opt/mcp-vn-backups/portrait-scene-routing-20261028T105217Z/
  /opt/mcp-vn-backups/cydonia-v64-switch-20261028T105924Z/
  /opt/mcp-vn-backups/ram-and-continuity-20261028T105712Z/

A source-code rollback must preserve current gameplay data. NEVER overwrite a user save with the old snapshot unless explicitly requested, as this would lose new turns.
