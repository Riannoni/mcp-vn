"""Zero-GPU SDXL face-adapter graph integrity check; NEVER a G2 decision.

This is a structural check, not trusted source/byte attestation. The caller
must independently hash original private face files, Comfy inputs, garments
and masks. Not wired to production before independent producer integration.
"""
from __future__ import annotations

import re

SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_IMAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,239}\.(?:png|webp|jpe?g)$", re.I)
FACE_IPADAPTER = "ip-adapter-plus-face_sdxl_vit-h.safetensors"
CLIP_VISION = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
PINNED_PONY_CHECKPOINT = "CyberRealisticPony_V18.0_F16.safetensors"


class IdentityGraphBlocked(ValueError):
    """Untrusted or missing source-to-graph identity binding."""


def _node(graph, node_id, kind):
    value = graph.get(str(node_id))
    if not isinstance(value, dict) or value.get("class_type") != kind or not isinstance(value.get("inputs"), dict):
        raise IdentityGraphBlocked(f"Required {kind} node {node_id} missing")
    return value["inputs"]


def _edge(value, node_id, output=0):
    return value == [str(node_id), output]


def _receipt(receipt, original_sha, label):
    if not isinstance(receipt, dict):
        raise IdentityGraphBlocked(f"{label} source/upload receipt missing")
    name, source_sha, upload_sha = (receipt.get(k) for k in ("image", "source_sha256", "upload_sha256"))
    if not isinstance(name, str) or not SAFE_IMAGE.fullmatch(name) or "/" in name or "\\" in name:
        raise IdentityGraphBlocked(f"{label} unsafe or absent Comfy input image")
    if (not isinstance(source_sha, str) or not SHA256.fullmatch(source_sha) or
        not isinstance(original_sha, str) or not SHA256.fullmatch(original_sha) or
        source_sha.lower() != original_sha.lower()):
        raise IdentityGraphBlocked(f"{label} wrong original source SHA")
    if not isinstance(upload_sha, str) or not SHA256.fullmatch(upload_sha):
        raise IdentityGraphBlocked(f"{label} Comfy upload byte SHA missing")
    return name


def _check_exact_render_output(graph):
    """The submitted graph must save the same face-conditioned sampler output.

    Checking only the canonical sampler's model is insufficient: another
    KSampler/SaveImage can produce the PNG while the checked branch is dead.
    This contract intentionally permits a single narrow SDXL Lab output graph.
    """
    samplers = {"KSampler", "KSamplerAdvanced", "SamplerCustom", "SamplerCustomAdvanced"}
    outputs = {"SaveImage", "PreviewImage", "SaveImageWebsocket",
               "SaveAnimatedWEBP", "SaveAnimatedPNG"}
    for key, value in graph.items():
        if not isinstance(value, dict):
            raise IdentityGraphBlocked("Malformed render node")
        kind = value.get("class_type")
        if kind in samplers and str(key) != "5":
            raise IdentityGraphBlocked("Unexpected independent sampler bypass")
        if kind in outputs and str(key) != "7":
            raise IdentityGraphBlocked("Unexpected second image output")
    decoder = _node(graph, "6", "VAEDecode")
    output = _node(graph, "7", "SaveImage")
    if (not _edge(decoder.get("samples"), "5") or
        not _edge(decoder.get("vae"), "1", 2) or
        not _edge(output.get("images"), "6")):
        raise IdentityGraphBlocked("Final SaveImage output bypasses canonical sampler/decoder")


def validate_sdxl_identity_graph(job, graph, intent, *, checkpoint, face_uploads,
                                 mask_uploads=None, body_source=None):
    """Check intended IPAdapter wiring; never attest rendered pixels or actual bytes.

    intent: output of identity_wardrobe_preflight.preflight for the SAME job.
    face_uploads: actor name -> {image, source_sha256, upload_sha256}
    supplied by an independent trusted hash producer; no file access here.
    mask_uploads similarly provide mask source/upload SHA and actor_region.
    body_source optionally records same-outfit sprite img2img source and bytes.
    """
    if not isinstance(job, dict) or job.get("kind") not in ("scene", "sprite"):
        raise IdentityGraphBlocked("Only canonical sprites and neural CG are in scope")
    spec = job.get("spec")
    if not isinstance(spec, dict):
        raise IdentityGraphBlocked("Immutable source job spec missing")
    if job.get("kind") == "scene" and spec.get("composition") != "neural_story":
        raise IdentityGraphBlocked("Not a neural CG")
    if not isinstance(intent, dict) or intent.get("status") != "SOURCE_INTENT_CONSISTENT_NOT_G2":
        raise IdentityGraphBlocked("Source-intent preflight missing")
    actors = intent.get("actors")
    if not isinstance(actors, list) or not 1 <= len(actors) <= 4:
        raise IdentityGraphBlocked("No valid canonical cast")
    if not isinstance(graph, dict) or not isinstance(face_uploads, dict):
        raise IdentityGraphBlocked("Missing graph or face receipts")
    if job["kind"] == "sprite":
        source_actors = [{"name": spec.get("character") or job.get("character"),
                          "outfit": (spec.get("variant") or {}).get("outfit"),
                          "face_asset": spec.get("face_asset")}]
    else:
        source_actors = spec.get("characters")
    if not isinstance(source_actors, list) or len(source_actors) != len(actors):
        raise IdentityGraphBlocked("Stale source-intent actor list")
    for source, actor in zip(source_actors, actors):
        if not isinstance(source, dict) or (
            source.get("name") != actor.get("name") or
            source.get("outfit") != actor.get("outfit") or
            (source.get("face_asset") if job["kind"] == "sprite" else source.get("anchor_face_asset")) != actor.get("face_asset")
        ):
            raise IdentityGraphBlocked("Stale source-intent face/outfit/actor binding")
    if not isinstance(checkpoint, str) or not checkpoint.endswith(".safetensors") or "/" in checkpoint:
        raise IdentityGraphBlocked("Expected pinned SDXL checkpoint missing")
    # The expected checkpoint filename must not be freely selected by the
    # caller: matching two arbitrary names cannot establish SDXL compatibility.
    # This is still only a filename fence. The trusted upstream producer must
    # independently attest the actual installed model/adapter/CLIP bytes.
    if checkpoint != PINNED_PONY_CHECKPOINT:
        raise IdentityGraphBlocked("Only pinned Pony SDXL checkpoint family supported")
    if _node(graph, "1", "CheckpointLoaderSimple").get("ckpt_name") != checkpoint:
        raise IdentityGraphBlocked("Checkpoint/model family changed")
    sampler = _node(graph, "5", "KSampler")
    _check_exact_render_output(graph)
    is_sprite = job["kind"] == "sprite"
    vision_id, loader_id = ("15", "16") if is_sprite else ("60", "61")
    if _node(graph, vision_id, "CLIPVisionLoader").get("clip_name") != CLIP_VISION:
        raise IdentityGraphBlocked("Unsupported or missing SDXL CLIPVision")
    if _node(graph, loader_id, "IPAdapterModelLoader").get("ipadapter_file") != FACE_IPADAPTER:
        raise IdentityGraphBlocked("Unsupported SDXL face adapter")
    expected_count = 1 if is_sprite else len(actors)
    if sum(n.get("class_type") == "IPAdapterAdvanced" for n in graph.values() if isinstance(n, dict)) != expected_count:
        raise IdentityGraphBlocked("Extra, removed or bypassing IPAdapter nodes")
    previous = ["1", 0]
    for i, actor in enumerate(actors):
        if not isinstance(actor, dict) or not isinstance(actor.get("name"), str):
            raise IdentityGraphBlocked("Malformed source actor")
        name = actor["name"]
        upload = _receipt(face_uploads.get(name), actor.get("face_sha256"), f"{name} face")
        image_id = "17" if is_sprite else str(62 + 3 * i)
        apply_id = "18" if is_sprite else str(64 + 3 * i)
        if _node(graph, image_id, "LoadImage").get("image") != upload:
            raise IdentityGraphBlocked(f"{name} face image swapped or disconnected")
        adapter = _node(graph, apply_id, "IPAdapterAdvanced")
        for field, value in (("model", previous), ("image", [image_id, 0]),
                             ("ipadapter", [loader_id, 0]), ("clip_vision", [vision_id, 0])):
            if adapter.get(field) != value:
                raise IdentityGraphBlocked(f"{name} IPAdapter {field} is disconnected")
        if any(adapter.get(field) != required for field, required in (
            ("weight_type", "linear"), ("combine_embeds", "concat"),
            ("embeds_scaling", "V only")
        )):
            raise IdentityGraphBlocked(f"{name} IPAdapter embedding semantics changed")
        weight = adapter.get("weight")
        start, end = adapter.get("start_at"), adapter.get("end_at")
        if (type(weight) not in (float, int) or not 0 < weight <= 1.2 or
            type(start) not in (float, int) or type(end) not in (float, int) or
            not 0 <= start < end <= 1 or end < 0.5):
            raise IdentityGraphBlocked(f"{name} ineffective or malformed face attention")
        if not is_sprite:
            region_id = str(63 + 3 * i)
            if not isinstance(mask_uploads, dict):
                raise IdentityGraphBlocked("Source-grounded face attention masks missing")
            mask = mask_uploads.get(name)
            mask_name = _receipt(mask, mask.get("source_sha256") if isinstance(mask, dict) else None,
                                 f"{name} region")
            if mask.get("actor_region") != source_actors[i].get("actor_region"):
                raise IdentityGraphBlocked(f"{name} face region not source-bound")
            if _node(graph, region_id, "LoadImage").get("image") != mask_name or \
               not _edge(adapter.get("attn_mask"), region_id, 1):
                raise IdentityGraphBlocked(f"{name} face region swapped or disconnected")
        previous = [apply_id, 0]
    if sampler.get("model") != previous:
        raise IdentityGraphBlocked("Sampler bypasses canonical face adapter chain")
    if is_sprite:
        latent = sampler.get("latent_image")
        if _edge(latent, "2"):
            _node(graph, "2", "EmptyLatentImage")
            if body_source is not None:
                raise IdentityGraphBlocked("Unexpected unused body-seed receipt")
        elif _edge(latent, "11"):
            enc = _node(graph, "11", "VAEEncode")
            if not _edge(enc.get("pixels"), "10"):
                raise IdentityGraphBlocked("Body latent source disconnected")
            if not isinstance(body_source, dict) or body_source.get("outfit") != actors[0].get("outfit"):
                raise IdentityGraphBlocked("Unattested or stale full-body wardrobe seed")
            body_img = _receipt(body_source, body_source.get("source_sha256"), "full-body seed")
            if _node(graph, "10", "LoadImage").get("image") != body_img:
                raise IdentityGraphBlocked("Full-body seed upload swapped")
        else:
            raise IdentityGraphBlocked("Unknown sprite latent source")
    return {"status": "GRAPH_IDENTITY_WIRED_NOT_G2", "actor_count": len(actors),
            "backend": "sdxl", "pixel_reviewed": False}
