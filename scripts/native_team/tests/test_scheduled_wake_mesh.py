"""Local reservation tests never make network/model/GPU calls."""
import concurrent.futures
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ops"))
import scheduled_wake_mesh as m

S1="1"*40
S2="2"*40
S3="3"*40
S4="4"*40

class NativeWakeMeshTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        (self.root/"state").mkdir()
    def call(self,sha=S1,now=100,reserve=True,who="golden",target="chief"):
        return m.check(self.root,target,"visual_candidate_ready",sha,who,reserve,now)
    def test_preview_is_not_a_model_call(self):
        a=self.call(reserve=False)
        self.assertTrue(a["eligible"])
        self.assertFalse(a.get("reserved",False))
        self.assertTrue(self.call(reserve=True)["reserved"])
    def test_exact_event_one_wake_only(self):
        self.assertTrue(self.call()["reserved"])
        self.assertEqual(self.call(now=500)["reason"],"already_requested_for_exact_evidence")
    def test_rate_cooldown(self):
        self.assertTrue(self.call()["eligible"])
        self.assertEqual(self.call(sha=S2,now=101)["reason"],"target_wake_cooldown")
        self.assertTrue(self.call(sha=S2,now=340)["eligible"])
    def test_target_budget(self):
        for i,sha in enumerate((S1,S2,S3)):
            self.assertTrue(self.call(sha=sha,now=100+300*i)["reserved"])
        self.assertEqual(self.call(sha=S4,now=1100)["reason"],"per_target_hourly_budget")
    def test_renew_after_window(self):
        self.assertTrue(self.call()["reserved"])
        self.assertTrue(self.call(sha=S2,now=4000)["reserved"])
    def test_invalid_event_cannot_invoke(self):
        with self.assertRaises(ValueError):
            m.check(self.root,"chief","visual_candidate_ready","bad_sha","golden",True,100)
        with self.assertRaises(ValueError):
            m.check(self.root,"chief","paid_api",S1,"golden",True,100)
    def test_unknown_target_refused(self):
        with self.assertRaises(ValueError):
            m.check(self.root,"invalid","review_accepted",S1,"golden",True,100)
    def test_self_wake_refused(self):
        self.assertFalse(self.call(target="golden")["eligible"])
    def test_concurrent_reservations_one_winner(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
            x=list(ex.map(lambda _: self.call(),range(4)))
        self.assertEqual(sum(bool(z.get("reserved")) for z in x),1)
    def test_missing_native_state_is_error(self):
        with self.assertRaises(FileNotFoundError):
            self.call()

if __name__=="__main__":
    unittest.main()
