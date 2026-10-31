"""Fail-closed CPU matte for an isolated near-neutral-background first-shot RGB sprite.

This does NOT certify face, outfit, hair, boot fidelity, or visual G2.
No GPU, network, model calls, or game/published asset writes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time

from PIL import Image, ImageChops, ImageDraw, ImageFilter


class MatteUnsafe(ValueError):
    """The matte cannot be trusted without manual/independent inspection."""


def _max_rgb_distance(image: Image.Image, reference: tuple[int, int, int]) -> Image.Image:
    diff = ImageChops.difference(image, Image.new("RGB", image.size, reference))
    r, g, b = diff.split()
    return ImageChops.lighter(ImageChops.lighter(r, g), b)


def extract_matte(
    source: Image.Image, *, threshold: int = 28
) -> tuple[Image.Image, dict]:
    """Return an RGBA *candidate* and a fail-closed, non-G2 QA report.

    Stage 0 checks background/color/edge assumptions; Stage 1 extracts the
    center-connected silhouette from edge-connected near-neutral background.
    Stage 2 canonical face, garment, hair, boot and exact-pixel review remain
    mandatory and UNVERIFIED. This deliberately is not a generic segmenter.
    """
    started = time.perf_counter()
    if source.mode == "RGBA":
        if source.getchannel("A").getextrema() != (255, 255):
            raise MatteUnsafe("input already has nonopaque alpha; source must be frozen RGB")
        source = source.convert("RGB")
    if source.mode != "RGB":
        raise MatteUnsafe("expected opaque RGB image")
    width, height = source.size
    if width < 64 or height < 64 or width * height > 12_000_000:
        raise MatteUnsafe("unsupported dimensions")
    if not 8 <= threshold <= 35:
        raise MatteUnsafe("threshold outside prevalidated range")
    corners = [
        source.getpixel((0, 0)), source.getpixel((width - 1, 0)),
        source.getpixel((0, height - 1)), source.getpixel((width - 1, height - 1)),
    ]
    if any(max(abs(a - b) for a, b in zip(corners[0], c)) > 28 for c in corners):
        raise MatteUnsafe("nonuniform/contaminated corner background")
    reference = tuple(sorted(c[i] for c in corners)[len(corners) // 2] for i in range(3))
    if min(reference) < 170 or max(reference) - min(reference) > 25:
        raise MatteUnsafe("background is not bright near-neutral")
    distance = _max_rgb_distance(source, reference)
    candidate = distance.point(lambda v: 0 if v <= threshold else 255)
    # A near-neutral cast shadow can be darker than the flat backdrop and
    # physically touch a boot. Treat bright low-chroma floor as backdrop
    # before exterior flood fill, never remove brown boots or colored skin.
    r, g, b = source.split()
    chroma = ImageChops.lighter(
        ImageChops.lighter(ImageChops.difference(r, g), ImageChops.difference(g, b)),
        ImageChops.difference(r, b),
    )
    minimum = ImageChops.darker(ImageChops.darker(r, g), b)
    neutral = chroma.point(lambda v: 255 if v <= 18 else 0)
    bright = minimum.point(lambda v: 255 if v >= 115 else 0)
    candidate = ImageChops.subtract(candidate, ImageChops.multiply(neutral, bright))
    # Any foreground pixel on an outer edge means an unsafe crop or backdrop.
    edge = [
        candidate.crop((0, 0, width, 1)),
        candidate.crop((0, height - 1, width, height)),
        candidate.crop((0, 0, 1, height)),
        candidate.crop((width - 1, 0, width, height)),
    ]
    if any(im.getextrema()[1] for im in edge):
        raise MatteUnsafe("foreground touches image edge / background not separable")
    stage0_seconds = time.perf_counter() - started

    # Mark only the connected exterior background; internal bright areas
    # (e.g. pale skin/highlights) cannot become transparent holes.
    for seed in ((0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)):
        if candidate.getpixel(seed) == 0:
            ImageDraw.floodfill(candidate, seed, 128, thresh=0)
    foreground = candidate.point(lambda v: 0 if v == 128 else 255)

    # Keep the central connected principal, discard detached floor shadows
    # and stray background marks. Off-center subjects fail closed.
    seed = (width // 2, height // 3)
    if foreground.getpixel(seed) != 255:
        raise MatteUnsafe("center principal not identifiable")
    ImageDraw.floodfill(foreground, seed, 128, thresh=0)
    silhouette = foreground.point(lambda v: 255 if v == 128 else 0)
    bbox = silhouette.getbbox()
    if bbox is None or bbox[0] <= 0 or bbox[1] <= 0 or bbox[2] >= width or bbox[3] >= height:
        raise MatteUnsafe("principal silhouette clipped or absent")
    pixels = silhouette.histogram()[255]
    fraction = pixels / (width * height)
    if not 0.05 <= fraction <= 0.75:
        raise MatteUnsafe("implausible foreground coverage")
    alpha = silhouette.filter(ImageFilter.GaussianBlur(0.65))
    result = source.copy()
    result.putalpha(alpha)
    total = time.perf_counter() - started
    report = {
        "schema": "web-vn.firstshot.cpu-matte.v1",
        "stage0": "PASS", "stage1": "PASS",
        "stage2": "REQUIRED_FOR_CANONICAL_IDENTITY_WARDROBE",
        "g2": "UNVERIFIED", "g3": "NO_GO",
        "canonical_identity_verified": False, "wardrobe_verified": False,
        "hair_verified": False, "boots_verified": False,
        "human_labeled": False, "publishable": False,
        "method": "connected-neutral-background-plus-central-principal",
        "threshold": threshold, "size": [width, height],
        "foreground_fraction": round(fraction, 6), "bbox": list(bbox),
        "stage0_seconds": round(stage0_seconds, 6),
        "stage1_seconds": round(total - stage0_seconds, 6),
        "cpu_seconds": round(total, 6),
        "caveat": "No identity/outfit proof; matte boundaries require independent original-pixel review.",
    }
    return result, report


def extract_matte_file(
    source_path: str | Path,
    output_path: str | Path,
    *, expected_sha256: str,
    threshold: int = 28,
) -> dict:
    """Immutable SHA-bound source -> exclusive derived PNG, never overwrite."""
    source_path, output_path = Path(source_path), Path(output_path)
    if source_path.resolve() == output_path.resolve() or output_path.exists():
        raise MatteUnsafe("output exists or aliases immutable input")
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise MatteUnsafe("expected source SHA256 required")
    original = source_path.read_bytes()
    source_sha = hashlib.sha256(original).hexdigest()
    if source_sha != expected_sha256:
        raise MatteUnsafe("frozen source SHA256 mismatch")
    from io import BytesIO
    with Image.open(BytesIO(original)) as im:
        if im.format != "PNG":
            raise MatteUnsafe("input must be exact original PNG")
        rgba, report = extract_matte(im, threshold=threshold)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".matte-", suffix=".png", dir=output_path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            rgba.save(f, format="PNG")
            f.flush()
            os.fsync(f.fileno())
        # Exclusive creation: never overwrite a published/accepted artifact.
        os.link(temp_name, output_path)
    except FileExistsError as exc:
        raise MatteUnsafe("derived output already exists") from exc
    finally:
        os.unlink(temp_name)
    report["source_sha256"] = source_sha
    report["derived_sha256"] = hashlib.sha256(output_path.read_bytes()).hexdigest()
    return report


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--threshold", type=int, default=28)
    a = p.parse_args()
    report = extract_matte_file(
        a.input, a.output, expected_sha256=a.expected_sha256, threshold=a.threshold
    )
    with open(a.report, "x", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
