# Safe render helper rollout — 2026-10-31

## Deployment verification — 2026-10-31

- **GitHub merged:** PR #48 → `main` merge SHA `202af42b80f64a71793fb36e8fc10d119ea94880`.
- **PC installed:** seven exact source files to `~/.local/share/mcp-vn/` from PC-validated candidate v2 `3b10732ab1525071ea9ea82677a3acbe897eb174`; all seven were previously absent, so no preexisting module overwritten. Each matched candidate byte-for-byte; Python `py_compile` PASS after install.
- **Tests:** 46/46 clean candidate Python tests on the actual Bazzite Python runtime.
- **Live services:** `mcp-vn-worker`, `mcp-vn-comfy`, `mcp-vn-vision` each `active`. Last queue read `queue_running=[]`, `queue_pending=[]` (snapshot only).
- **No process restart, no runtime import/caller switch, no changed checkpoint, no user-save/canonical-asset mutation.** The active worker still uses the existing SDXL path; therefore this is **safe helper installation, not generator activation**.
- The home deployment worktree had divergent history (local main ahead one / behind five); deliberately **not pulled/reset/restarted**. The new GitHub main was merged through its own branch, not by changing that production checkout.
- Rollback for this release alone: remove these exact seven added modules from `~/.local/share/mcp-vn/` after verifying no process has begun importing them. Do not restart anything merely for rollback if they remain unused.



Scope: **source and PC-runtime helper deployment**, NOT activation of experimental CG rendering.

This changes only importable, side-effect-free helpers under `worker/`: source-hand coverage, actor-edit strict policy, thigh/lower-body pixel protection, preflight staged inpaint validation, source-attributed bimanual spatial planner, projected object-scale evidence, and the explicit Z-Image graph builder.

**Why not switch the default generator?** The latest wooden-box and map experiments completed technically and looked substantially better, but mandatory independent G2 size checks still failed. The generic post-hoc palm/prop compositor also produced dangling sleeves on held-out input and is intentionally **NOT** in this release. Source code for experimental candidate is preserved in [PR #47](https://github.com/Riannoni/web-vn/pull/47). There is no blanket `accept anyway`.

Release validation (real Bazzite PC, clean candidate directory): **46/46 Python tests PASS**: actor edit 10, thigh 6, staged 6, bimanual planner 7, source-hands 4, Z-Image graph 5, projected-scale 8. A packaging-only test import error was fixed before this release. Test suite does not claim G2/G3.

PC rollout: copy **only** these helper source modules from pinned release commit to the runtime module folder, after backing up existing files. No worker/ComfyUI/vision/model-lab service restarts; no env/model/checkpoint/default graph changes; no game save, accepted CG or source-job modifications. Because existing `worker.py` does not import or call these new helpers, active browser render behavior is unchanged and existing in-flight/new jobs can proceed normally.

Rollback: remove only these newly added module files after confirming baseline directory state (or restore any backed-up files). Do not roll back game saves or alter Comfy output. Release state **PC helper files installed** != `production generator switched`; a later independently tested, feature-flagged integration is necessary before using the new path in the game.

Operational reminder: user may be generating live images concurrently. GPU queue is USER-owned; do not submit GPU jobs or restart any service during that session. Check current ownership before a later engine-switch rollout. Human visual inspection remains mandatory for any experimental candidate.

Sources: [AGENTS.md](../AGENTS.md), [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md), [latest handoff](RENDER-HANDOFF-2026-10-31.md), issues [#20](https://github.com/Riannoni/web-vn/issues/20), [#44](https://github.com/Riannoni/web-vn/issues/44).
