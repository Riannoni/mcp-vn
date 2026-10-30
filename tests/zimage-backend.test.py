"""Z-Image graph compatibility and strict identity/release safeguards."""
import io,sys,unittest
from pathlib import Path
from PIL import Image,ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
from zimage_backend import (create_graph,prepare_game_canvas,CG_CANVAS,
                            SPRITE_CANVAS,GAME_CG_CANVAS,GAME_SPRITE_CANVAS)
PROMPT='Exactly one adult adventurer studying a detailed paper map.'
KW=dict(prompt=PROMPT,seed=2026103001,prefix='vn_zimage_probe_test_abc',
        width=CG_CANVAS[0],height=CG_CANVAS[1])

def sample_image(size=(512,320)):
    b=io.BytesIO();Image.new('RGB',size,'gray').save(b,format='PNG')
    return b.getvalue()

class ZImageGraphTest(unittest.TestCase):
    def test_private_graph_uses_native_transformer_not_sdxl(self):
        g=create_graph(**KW,private_unanchored=True)
        self.assertEqual(g['2']['inputs']['type'],'lumina2')
        self.assertEqual(g['7']['inputs']['width'],1024)
        self.assertEqual(g['8']['inputs']['steps'],8)
        self.assertEqual(g['8']['inputs']['cfg'],1.0)
        self.assertEqual(g['8']['inputs']['seed'],2026103001)
        self.assertEqual(g['8']['inputs']['latent_image'],['7',0])
        self.assertFalse(any('IPAdapter' in x['class_type'] for x in g.values()))
        self.assertEqual(g['10']['inputs']['filename_prefix'],KW['prefix'])

    def test_no_inadvertent_production_or_canonical_identity_drop(self):
        with self.assertRaisesRegex(ValueError,'not authorized'):
            create_graph(**KW)
        with self.assertRaisesRegex(ValueError,'cannot preserve canonical'):
            create_graph(**KW,private_unanchored=True,
                         canonical_face_asset='game-face-reference.png')

    def test_unsafe_size_model_seed_and_output_are_rejected(self):
        bad=[dict(width=1216),dict(height=1104),dict(seed=-1),
             dict(seed=1<<50),dict(prefix='../escape'),
             dict(model='CyberRealisticPony_V18.0_F16.safetensors')]
        for change in bad:
            with self.subTest(**change),self.assertRaises(ValueError):
                create_graph(**(KW|change),private_unanchored=True)

    def test_native_cg_canvas_resizes_without_implicit_scene_verification(self):
        rendered=prepare_game_canvas(sample_image(),'cg')
        with Image.open(io.BytesIO(rendered)) as img:
            self.assertEqual(img.size,GAME_CG_CANVAS)
            self.assertEqual(img.mode,'RGB')

    def test_sprite_requires_alpha_and_rejects_empty_cutout(self):
        raw=sample_image()
        with self.assertRaisesRegex(ValueError,'alpha removal required'):
            prepare_game_canvas(raw,'sprite')
        with self.assertRaisesRegex(ValueError,'insufficient transparent'):
            prepare_game_canvas(raw,'sprite',sprite_cutout=lambda x:x.convert('RGBA'))
        def cutout(image):
            rgba=Image.new('RGBA',image.size,(0,0,0,0))
            ImageDraw.Draw(rgba).rectangle((270,140,500,1060),fill=(40,70,110,255))
            return rgba
        with Image.open(io.BytesIO(prepare_game_canvas(raw,'sprite',sprite_cutout=cutout))) as image:
            self.assertEqual(image.mode,'RGBA')
            self.assertEqual(image.size,GAME_SPRITE_CANVAS)
            self.assertIsNotNone(image.getchannel('A').getbbox())

if __name__=='__main__':unittest.main()
