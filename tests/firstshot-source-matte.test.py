"""CPU-only negative/positive controls for frozen first-shot RGB sprite matte."""
import hashlib
import importlib.util
import io
import pathlib
import tempfile
import unittest
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "firstshot_source_matte", ROOT / "worker" / "firstshot_source_matte.py"
)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def fixture():
    im = Image.new("RGB", (160, 240), (226, 222, 216))
    d = ImageDraw.Draw(im)
    d.ellipse((55, 18, 105, 94), fill=(118, 54, 30))  # hair
    d.line([(57, 50), (48, 90), (45, 118)], fill=(125, 57, 30), width=3)
    d.ellipse((65, 32, 95, 83), fill=(231, 174, 143))  # face
    d.rectangle((45, 82, 115, 157), fill=(23, 35, 59))  # jacket
    d.rectangle((36, 94, 48, 151), fill=(24, 37, 59))
    d.rectangle((112, 94, 124, 151), fill=(24, 37, 59))
    d.rectangle((51, 157, 74, 207), fill=(38, 41, 47))
    d.rectangle((86, 157, 109, 207), fill=(38, 41, 47))
    d.rectangle((49, 203, 76, 222), fill=(72, 43, 28))  # left boot
    d.rectangle((84, 203, 111, 222), fill=(72, 43, 28))  # right boot
    return im


class MatteTests(unittest.TestCase):
    def test_face_hair_strand_both_boots_and_gap(self):
        rgba, report = mod.extract_matte(fixture())
        self.assertEqual(rgba.mode, "RGBA")
        a = rgba.getchannel("A")
        for xy in [(80, 55), (60, 50), (47, 106), (61, 215), (99, 215)]:
            self.assertGreaterEqual(a.getpixel(xy), 245, xy)
        self.assertGreaterEqual(a.getpixel((58, 37)), 150)  # antialiased hair boundary
        for xy in [(0, 0), (159, 239), (80, 185), (10, 100)]:
            self.assertLessEqual(a.getpixel(xy), 10, xy)
        self.assertEqual(report["stage0"], "PASS")
        self.assertEqual(report["stage1"], "PASS")
        self.assertEqual(report["g2"], "UNVERIFIED")
        self.assertEqual(report["stage2"], "REQUIRED_FOR_CANONICAL_IDENTITY_WARDROBE")

    def test_attached_neutral_floor_shadow_removed_without_boot_loss(self):
        im = fixture()
        ImageDraw.Draw(im).ellipse((5, 210, 91, 232), fill=(165, 160, 154))
        # Restore boot on top of the shadow, as in the actual frozen image.
        ImageDraw.Draw(im).rectangle((49, 203, 76, 222), fill=(72, 43, 28))
        rgba, _ = mod.extract_matte(im)
        alpha = rgba.getchannel("A")
        self.assertLessEqual(alpha.getpixel((20, 220)), 10)
        self.assertGreaterEqual(alpha.getpixel((61, 215)), 245)

    def test_face_hair_boot_rgb_unchanged(self):
        original = fixture()
        rgba, _ = mod.extract_matte(original)
        for xy in [(80, 55), (60, 50), (61, 215), (99, 215)]:
            self.assertEqual(rgba.getpixel(xy)[:3], original.getpixel(xy))

    def test_missing_boot_never_becomes_verified(self):
        im = fixture()
        ImageDraw.Draw(im).rectangle((84, 203, 111, 222), fill=(226, 222, 216))
        _, report = mod.extract_matte(im)
        self.assertFalse(report["boots_verified"])
        self.assertFalse(report["publishable"])

    def test_missing_hair_never_becomes_verified(self):
        im = fixture()
        ImageDraw.Draw(im).ellipse((55, 18, 105, 94), fill=(226, 222, 216))
        ImageDraw.Draw(im).ellipse((65, 32, 95, 83), fill=(231, 174, 143))
        # The missing hair disconnects the face; a hard failure is preferable
        # to inventing a verified identity or quietly publishing.
        with self.assertRaises(mod.MatteUnsafe):
            mod.extract_matte(im)

    def test_corner_contamination_fails_closed(self):
        im = fixture()
        im.putpixel((0, 0), (0, 250, 0))
        with self.assertRaises(mod.MatteUnsafe):
            mod.extract_matte(im)

    def test_subject_at_border_fails_closed(self):
        im = fixture()
        ImageDraw.Draw(im).rectangle((0, 80, 50, 120), fill=(18, 25, 40))
        with self.assertRaises(mod.MatteUnsafe):
            mod.extract_matte(im)

    def test_no_subject_fails_closed(self):
        with self.assertRaises(mod.MatteUnsafe):
            mod.extract_matte(Image.new("RGB", (160, 240), (226, 222, 216)))

    def test_non_opaque_rgba_rejected(self):
        im = fixture().convert("RGBA")
        im.putpixel((10, 10), (226, 222, 216, 0))
        with self.assertRaises(mod.MatteUnsafe):
            mod.extract_matte(im)

    def test_sha_mismatch_does_not_write_output(self):
        with tempfile.TemporaryDirectory() as d:
            src = pathlib.Path(d) / "src.png"
            dst = pathlib.Path(d) / "derived.png"
            fixture().save(src)
            with self.assertRaises(mod.MatteUnsafe):
                mod.extract_matte_file(src, dst, expected_sha256="0" * 64)
            self.assertFalse(dst.exists())

    def test_source_to_derived_sha_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            src = pathlib.Path(d) / "src.png"
            dst = pathlib.Path(d) / "derived.png"
            fixture().save(src)
            original = hashlib.sha256(src.read_bytes()).hexdigest()
            report = mod.extract_matte_file(src, dst, expected_sha256=original)
            self.assertEqual(report["source_sha256"], original)
            self.assertEqual(report["derived_sha256"], hashlib.sha256(dst.read_bytes()).hexdigest())
            self.assertNotEqual(report["source_sha256"], report["derived_sha256"])
            self.assertEqual(report["g2"], "UNVERIFIED")
            with self.assertRaises(mod.MatteUnsafe):
                mod.extract_matte_file(src, dst, expected_sha256=original)

    def test_no_fabricated_human_label_or_qa_pass(self):
        _, report = mod.extract_matte(fixture())
        self.assertFalse(report["canonical_identity_verified"])
        self.assertFalse(report["wardrobe_verified"])
        self.assertFalse(report["human_labeled"])
        self.assertFalse(report["publishable"])


if __name__ == "__main__":
    unittest.main()
