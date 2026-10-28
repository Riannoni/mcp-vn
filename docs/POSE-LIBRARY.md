# OpenPose v2 — catalogue of 33 editable poses

The canonical pose coordinates and renderer live in `worker/pose_library.py`.
Run `python3 worker/pose_library.py --output ~/.local/share/mcp-vn/pose-guides-v2`
on the gaming PC (Pillow required). This generates:

- `cg/<pose>.png` at 1216×704 for story CGs, with a black background and standard coloured COCO-18 OpenPose limbs.
- `sprite/<pose>.png` at 832×1216 for full-height sprites.
- Matching `.json` editor files with `people[0].pose_keypoints_2d` for all 18 joints and confidence values.
- `manifest.json` (names, view directions and draft validation status), `pose-contact-sheet.png` for visual inspection.

The catalogue covers standing (including rear/side/three-quarter), gestures, walking, running, kneeling, crouching, chair/floor sitting, contact with a wall, bending forward, looking over the shoulder, and two floor poses. The templates use anatomical joint coordinates rather than filename-only stick figures. The generated images are *draft* ControlNet hints, not validated photographs or guaranteed pose matches.

**Safety gate:** old approved `running.png` and `kneeling.png` in `pose-guides` are untouched. The v2 catalogue lives in a separate directory and is **off by default**. To opt in after A/B evaluation, set `VN_POSE_LIBRARY_V2=1` on the GPU worker only. The runtime selector matches strictly: explicit rear or side camera **and** forward lean **and** both palms braced on a stone/brick wall. All other prompts keep using the previous approved guide selection or text-only direction. Do not automatically map the full catalogue to arbitrary narrator prose.

Each new pose should be A/B-tested against a text-only generation with the same neutral reference identity, camera, and surroundings; validate physical action, identity, and scene consistency with QA. Mark accepted entries in a future reviewed allowlist rather than enabling all 33 simply because PNGs exist. OpenPose controls skeleton geometry; it does **not** control garments, facial identity, anatomy or exact contact with environmental surfaces.

**Debugging:** a `POSE_CONTROL_ACTIVE` entry in the worker logs is evidence that the guide was actually applied to ComfyUI. Its absence means ControlNet had no effect even if the PNG is present on disk. Generated PNGs are reproducible from source; binary output is intentionally not committed to Git.

References: [COCO-18 pose editor](https://github.com/hisashi-ito/bonepose) and [ControlNet OpenPose palette reference](https://github.com/lllyasviel/ControlNet/discussions/266).
