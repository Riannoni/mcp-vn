import datetime
import json
import tempfile
import time
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ops'))
from quota_gate import permit

class QuotaGateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/"state").mkdir()
    def tearDown(self):
        self.temp.cleanup()
    def write(self, five=0, week=36, delta=0, ok=True):
        at=datetime.datetime.fromtimestamp(time.time()-delta,datetime.timezone.utc).isoformat()
        (self.root/"state"/"quota-latest.json").write_text(json.dumps({"utc":at,"ok":ok,"5h_used":five,"7d_used":week}))
    def test_native_chatgpt_does_not_depend_on_codex_oauth_meter(self):
        x=permit(self.root,provider="chatgpt_scheduled")
        self.assertTrue(x["eligible"])
        self.assertEqual(x["quota_meter"],"not_available_locally")
        self.write(five=100,week=100)
        self.assertTrue(permit(self.root,provider="chatgpt_scheduled")["eligible"])
        self.assertFalse(permit(self.root)["eligible"])

    def test_reject_unknown_quota_surface(self):
        with self.assertRaises(ValueError):
            permit(self.root,provider="paid_api")

    def test_healthy_meter_allows_wake(self):
        self.write()
        self.assertTrue(permit(self.root)["eligible"])
    def test_soft_five_hour_cap(self):
        self.write(five=75)
        self.assertEqual(permit(self.root)["reason"],"quota_5h_soft_limit")
    def test_soft_weekly_cap(self):
        self.write(week=75)
        self.assertEqual(permit(self.root)["reason"],"quota_7d_soft_limit")
    def test_unknown_meter_fail_closed(self):
        self.assertFalse(permit(self.root)["eligible"])
    def test_stale_meter_fail_closed(self):
        self.write(delta=190)
        self.assertEqual(permit(self.root)["reason"],"quota_stale")
    def test_bad_meter_fail_closed(self):
        self.write(five=-3)
        self.assertEqual(permit(self.root)["reason"],"quota_invalid")
if __name__=="__main__":
    unittest.main()
