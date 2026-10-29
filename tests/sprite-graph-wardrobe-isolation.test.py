"""Graph-level regression: a face reference may not impose an old costume."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('VN_WORKER_TOKEN','test-only-not-production')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'worker'))
import worker
from PIL import Image


class SpriteWardrobeGraphTest(unittest.TestCase):
    def graph(self,outfit):
        spec={
            'quality':'standard','resolution':[832,1216],
            'anchor_asset':'old-body.png','anchor_style':'semireal',
            'face_asset':'face-anchor.png',
            'variant':{'outfit':outfit,'pose':'standing','emotion':'neutral'},
            'appearance':'An adult explorer with brown hair',
            'environment':{'id':'unclassified','positive':[],'negative':[]},
        }
        job={'id':'a4e99e58-1f09-46a9-a1e9-96d96cdcf874',
             'kind':'sprite','style':'semireal','character':'Ada','attempts':1,
             'prompt':'Full-length adult explorer sprite, neutral studio matte.',
             'spec':spec}
        with patch.object(worker,'fetch_asset',return_value=Image.new('RGBA',(832,1216),'gray')),\
             patch.object(worker,'upload_to_comfy',side_effect=lambda data,name:name),\
             patch.dict(os.environ,{'VN_IPADAPTER':'1','VN_POSE_CONTROL':'0',
                                    'VN_POSE_LIBRARY_V2':'0'}):
            return worker.image_graph(job)[0]

    def test_default_sprite_can_use_body_seed(self):
        graph=self.graph('default')
        self.assertEqual(graph['11']['class_type'],'VAEEncode')
        self.assertEqual(graph['5']['inputs']['latent_image'],['11',0])

    def test_new_outfit_uses_fresh_body_and_locked_face(self):
        graph=self.graph('blue travel jacket')
        self.assertNotIn('11',graph)
        self.assertEqual(graph['5']['inputs']['latent_image'],['2',0])
        self.assertEqual(graph['18']['class_type'],'IPAdapterAdvanced')
        self.assertEqual(graph['5']['inputs']['model'],['18',0])


if __name__=='__main__':
    unittest.main()
