#!/usr/bin/env python3
"""Regression for bounded reference-byte cache without touching the game."""
import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("VN_WORKER_TOKEN","test-only-worker-token")
os.environ.setdefault("VN_ASSET_CACHE_MIB","128")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"worker"))
import worker
from PIL import Image

class ReferenceCacheTests(unittest.TestCase):
    def setUp(self):
        with worker._REF_LOCK:
            worker._REF_CACHE.clear()
            worker._REF_CACHE_BYTES=0

    def test_immutable_reference_downloaded_only_once(self):
        buffer=io.BytesIO()
        Image.new("RGBA",(8,8),(100,50,10,255)).save(buffer,"PNG")
        data=buffer.getvalue()
        with patch.object(worker,"request",return_value=data) as req:
            img1=worker.fetch_asset("12345678-1234-1234-1234-123456789abc.png")
            img1.putpixel((0,0),(4,3,2,255))
            img2=worker.fetch_asset("12345678-1234-1234-1234-123456789abc.png")
        self.assertEqual(req.call_count,1)
        self.assertEqual(img2.getpixel((0,0)),(100,50,10,255))
        self.assertLessEqual(worker._REF_CACHE_BYTES,worker.REF_CACHE_LIMIT)

    def test_invalid_path_rejected_before_network(self):
        with patch.object(worker,"request") as req:
            with self.assertRaises(ValueError):
                worker.fetch_asset("../private")
        req.assert_not_called()

if __name__=="__main__":
    unittest.main(verbosity=2)
