# Safe render helper rollout — 2026-10-31

Scope: **source and PC-runtime helper deployment**, NOT activation of experimental CG rendering.

This changes only importable, side-effect-free helpers under `worker/`: source-hand coverage, actor-edit strict policy, thigh/lower-body pixel protection, preflight staged inpaint validation, source-attributed bimanual spatial planner, projected object-scale evidence, and the explicit Z-Image graph builder.

**Why not switch the default generator?** The latest wooden-box and map experiments completed technically and looked substantially better, but mandatory independent G2 size checks still failed. The generic post-hoc palm/prop compositor also produced dangling sleeves on held-out input and is intentionally **NOT** in this release. Source code for experimental candidate is preserved in [PR #47](https://github.com/Riannoni/web-vn/pull/47). There is no blanket `accept anyway`.

Release validation (real Bazzite PC, clean candidate directory): **46/46 Python tests PASS**: actor edit 10, thigh 6, staged 6, bimanual planner 7, source-hands 4, Z-Image graph 5, projected-scale 8. A packaging-only test import error was fixed before this release. Test suite does not claim G2/G3.

PC rollout: copy **only** these helper source modules from pinned release commit to the runtime module folder, after backing up existing files. No worker/ComfyUI/vision/model-lab service restarts; no env/model/checkpoint/default graph changes; no game save, accepted CG or source-job modifications. Because existing `worker.py` does not import or call these new helpers, active browser render behavior is unchanged and existing in-flight/new jobs can proceed normally.

Rollback: remove only these newly added module files after confirming baseline directory state (or restore any backed-up files). Do not roll back game saves or alter Comfy output. Release state **PC helper files installed** != `production generator switched`; a later independently tested, feature-flagged integration is necessary before using the new path in the game.

Operational reminder: user may be generating live images concurrently. GPU queue is USER-owned; do not submit GPU jobs or restart any service during that session. Check current ownership before a later engine-switch rollout. Human visual inspection remains mandatory for any experimental candidate.

Sources: [AGENTS.md](../AGENTS.md), [DEVELOPMENT-AND-TESTING.md](DEVELOPMENT-AND-TESTING.md), [latest handoff](RENDER-HANDOFF-2026-10-31.md), issues [#20](https://github.com/Riannoni/web-vn/issues/20), [#44](https://github.com/Riannoni/web-vn/issues/44).
