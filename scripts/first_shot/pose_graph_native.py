"""Experimental *source-only* native Z-Image-Turbo Union pose graph construction.

A graph is only preflighted, never submitted here. The single frozen CG-03
scene receives one additional MODEL_PATCH conditioning path. No SDXL/IPAdapter
fallback, prompt changes, identity pass claims or automatic model installs.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re

from PIL import Image

import json

# Immutable CPU-only trust anchors. Updating the frozen pack or model backend
# requires an explicit independently reviewed hash revision, not mutable
# case metadata passed by a dispatcher or an arbitrary locally edited graph.
_PACK_PATH = Path(__file__).resolve().with_name("pack-v1.json")
_BACKEND_PATH = Path(__file__).resolve().parents[2] / "worker" / "zimage_backend.py"
_PACK_SHA256 = "aa5a8f94859ff6b5e8c99386757cc9fccd1fa5e88a2fdd3e6970e556f8438910"
_BACKEND_SHA256 = "610a616a1c2d90fe00b4ec747d173c7f324d5e5e6b6b28d9c62153d82186c990"


def _pinned_bytes(path, expected_sha, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise NativePoseUnavailable("frozen_" + label + "_missing_or_symlink")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise NativePoseUnavailable("frozen_" + label + "_bytes_mismatch")
    return raw


def _serialized(value):
    # JSON encoding distinguishes bool from int, and floats from integers.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _canonical_baseline(graph, case):
    """Reconstruct the *complete* baseline; no caller-supplied trusted fields."""
    raw_pack = _pinned_bytes(_PACK_PATH, _PACK_SHA256, "pack")
    try:
        pack = json.loads(raw_pack)
        matches = [entry for entry in pack["cases"] if entry["id"] == "CG-03"]
        if len(matches) != 1 or _serialized(case) != _serialized(matches[0]):
            raise NativePoseUnavailable("frozen_case_provenance_mismatch")
        expected_case = matches[0]
    except (TypeError, KeyError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, NativePoseUnavailable):
            raise
        raise NativePoseUnavailable("frozen_pack_or_case_invalid") from exc

    if not isinstance(graph, dict) or not isinstance(graph.get("10"), dict):
        raise NativePoseUnavailable("not_native_unconditioned_base_graph")
    node10_inputs = graph["10"].get("inputs")
    if not isinstance(node10_inputs, dict):
        raise NativePoseUnavailable("not_native_unconditioned_base_graph")
    prefix = node10_inputs.get("filename_prefix")
    # Compile the already-verified source bytes to close a verify/load TOCTOU
    # gap. No arbitrary user-supplied code or network is ever evaluated.
    backend_raw = _pinned_bytes(_BACKEND_PATH, _BACKEND_SHA256, "backend")
    ns = {"__name__": "_webvn_pinned_zimage_backend"}
    exec(compile(backend_raw, str(_BACKEND_PATH), "exec"), ns)
    try:
        return ns["create_graph"](
            expected_case["prompt"], seed=expected_case["seed"],
            prefix=prefix,
            width=expected_case["canvas"][0],
            height=expected_case["canvas"][1],
            private_unanchored=True,
            canonical_face_asset=None,
            model=ns["DEFAULT_MODEL"],
            encoder=ns["DEFAULT_ENCODER"],
            vae=ns["DEFAULT_VAE"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise NativePoseUnavailable("frozen_baseline_reconstruction_invalid") from exc




POSE_REFERENCE_ID = "wall_push_rear_oblique_01"
POSE_GUIDE_SHA256 = "7391e30022bc83c89a4d5105c1efd5ce939d9cd460648a0ff7aa6121109793a2"
POSE_REFERENCE_SHA256 = "730b51efb109b5c6834ada6699d43141f17111f8731f05ea5416bcd9d71bc631"
POSE_EXTRACT_SHA256 = "d506a43e308cc8f9a30885f74223a35689d5b95101d289ad4b898edb10e1018b"
POSE_PATCH_NAME = "Z-Image-Turbo-Fun-Controlnet-Union.safetensors"
_EXPECTED_CASE_SEED = 202610310105
_EXPECTED_CANVAS = (1024, 592)
_FILENAME = re.compile(r"^vn_pose_probe_[a-z0-9_-]{4,80}\.png$")


class NativePoseUnavailable(ValueError):
    """A strict unmet preflight requirement, not permission to use another graph."""


def _required_inputs(info, name):
    node = info.get(name) if isinstance(info, dict) else None
    required = (node.get("input", {}).get("required") if isinstance(node, dict) else None)
    if not isinstance(required, dict):
        raise NativePoseUnavailable("missing_native_comfy_node:" + name)
    return required


def validate_native_nodes(info):
    """Check actual Comfy /object_info, including the installed Union patch.

    This cannot prove ROCm/VRAM or guarantee patch-model compatibility;
    those require a single isolated GPU execution after external submitters
    are quiesced and the graph has been independently examined.
    """
    for cls, fields in {
        "LoadImage": ("image",),
        "ImageScale": ("image", "width", "height", "crop", "upscale_method"),
        "ModelPatchLoader": ("name",),
        "ZImageFunControlnet": ("model", "model_patch", "vae", "strength"),
    }.items():
        required = _required_inputs(info, cls)
        if not set(fields).issubset(required):
            raise NativePoseUnavailable("incompatible_native_node_signature:" + cls)
    patch_options = _required_inputs(info, "ModelPatchLoader")["name"]
    if (not isinstance(patch_options, (tuple, list)) or not patch_options
            or not isinstance(patch_options[0], list)
            or POSE_PATCH_NAME not in patch_options[0]):
        raise NativePoseUnavailable("native_union_2_1_patch_not_installed")
    return True


def verify_private_guide(path, expected_sha=POSE_GUIDE_SHA256):
    """Verify frozen original pose-guide bytes without altering them."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise NativePoseUnavailable("pose_guide_missing_or_symlink")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise NativePoseUnavailable("pose_guide_source_sha_mismatch")
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise NativePoseUnavailable("pose_guide_not_png")
    try:
        with Image.open(path) as im:
            if im.size != (1216, 704):
                raise NativePoseUnavailable("pose_guide_wrong_canvas")
            im.verify()
    except OSError as exc:
        raise NativePoseUnavailable("pose_guide_corrupt") from exc
    return hashlib.sha256(raw).hexdigest()


def add_native_pose_to_frozen_cg03(graph, case, *, staged_guide_name, object_info):
    """Return a fresh graph with ONLY native Union pose conditioning enabled.

    Accepts a strict 8-step pinned Z-Image T2I graph generated by
    zimage_backend.create_graph(private_unanchored=True). Never submits GPU
    work, marks guide approved, or infers canonical identity/contact.
    """
    validate_native_nodes(object_info)
    if not isinstance(case, dict) or case.get("id") != "CG-03":
        raise NativePoseUnavailable("not_frozen_cg03_scene")
    if not isinstance(staged_guide_name, str) or not _FILENAME.fullmatch(staged_guide_name):
        raise NativePoseUnavailable("staged_guide_invalid_filename")
    expected_baseline = _canonical_baseline(graph, case)
    try:
        if _serialized(graph) != _serialized(expected_baseline):
            raise NativePoseUnavailable("frozen_baseline_graph_mismatch")
    except (TypeError, ValueError) as exc:
        if isinstance(exc, NativePoseUnavailable):
            raise
        raise NativePoseUnavailable("frozen_baseline_graph_unserializable") from exc
    output = deepcopy(graph)
    output.update({
        "11": {"class_type": "LoadImage", "inputs": {"image": staged_guide_name}},
        "12": {"class_type": "ImageScale", "inputs": {
            "image": ["11", 0], "upscale_method": "lanczos",
            "width": _EXPECTED_CANVAS[0], "height": _EXPECTED_CANVAS[1], "crop": "disabled"}},
        "13": {"class_type": "ModelPatchLoader", "inputs": {"name": POSE_PATCH_NAME}},
        "14": {"class_type": "ZImageFunControlnet", "inputs": {
            "model": ["6", 0], "model_patch": ["13", 0], "vae": ["3", 0],
            "image": ["12", 0], "strength": 1.0,
        }},
    })
    output["8"]["inputs"]["model"] = ["14", 0]
    return output
