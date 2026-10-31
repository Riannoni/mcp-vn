"""Local reservation tests never make network/model/GPU calls."""
import concurrent.futures
from pathlib import Path
import tempfile
import unittest
import sys
import sqlite3
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"ops"))
import scheduled_wake_mesh as m

S1="1"*40
S2="2"*40
S3="3"*40
S4="4"*40
RECEIPT="a"*64
RUN_ID="01234567-89ab-4cde-8fab-0123456789ab"

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
    def test_all_fifteen_native_cloud_roles_are_explicitly_mapped(self):
        self.assertEqual(len(m.TARGETS), 15)
        self.assertEqual(m.TARGETS["dispatcher"], "6ae5e8ac2e58819188b5f87aa17d0f97")
        self.assertEqual(m.TARGETS["decision"], "6ae5e8a59f2c8191a29d40c1c12712f0")
        self.assertEqual(m.TARGETS["gpu_lab"], "6ae5e8a91cfc8191bb938957f214f8c3")

    def test_dispatcher_cross_wake_new_roles_is_fenced(self):
        a=m.check(self.root,"gpu_lab","review_accepted",S1,"dispatcher",True,100)
        self.assertTrue(a["reserved"])
        self.assertEqual(a["automation_id"],m.TARGETS["gpu_lab"])
        b=m.check(self.root,"gpu_lab","review_accepted",S1,"decision",True,400)
        self.assertEqual(b["reason"],"already_requested_for_exact_evidence")
        c=m.check(self.root,"decision","source_pr_ready",S2,"dispatcher",True,100)
        self.assertTrue(c["reserved"])
        self.assertEqual(c["automation_id"],m.TARGETS["decision"])
        d=m.check(self.root,"dispatcher","source_pr_ready",S3,"dispatcher",True,100)
        self.assertEqual(d["reason"],"self_wake_not_needed")

    def test_missing_native_state_is_error(self):
        (self.root/"state").rmdir()
        with self.assertRaises(FileNotFoundError):
            self.call()

    def outcome(self, reservation, status, who="golden", run_id=None, now=110):
        return m.record_outcome(self.root, "chief", "visual_candidate_ready", S1,
                                who, reservation["reservation_id"], status,
                                RECEIPT, run_id=run_id, now=now)

    def test_explicit_no_call_can_retry_but_unknown_submission_cannot(self):
        first=self.call()
        self.outcome(first,"not_dispatched")
        self.assertEqual(self.call(now=111)["reason"],"target_wake_cooldown")
        second=self.call(now=500)
        self.assertTrue(second["reserved"])
        self.assertNotEqual(first["reservation_id"],second["reservation_id"])
        self.outcome(second,"unknown",now=510)
        self.assertFalse(self.call(now=100000)["eligible"])

    def test_request_is_not_start_and_policy_block_is_not_retryable(self):
        first=self.call()
        self.outcome(first,"requested")
        self.assertFalse(self.call(now=500)["eligible"])
        with self.assertRaises(ValueError):
            self.outcome(first,"not_dispatched")
        with self.assertRaises(ValueError):
            self.outcome(first,"started")
        self.outcome(first,"started",run_id=RUN_ID)
        self.outcome(first,"blocked",run_id=RUN_ID)
        self.assertFalse(self.call(now=100000)["eligible"])

    def test_stale_token_and_unrelated_role_cannot_release_reservation(self):
        first=self.call()
        with self.assertRaises(ValueError):
            self.outcome(first,"not_dispatched",who="identity")
        with self.assertRaises(ValueError):
            self.outcome(first,"not_dispatched",who="dispatcher")
        self.outcome(first,"not_dispatched")
        second=self.call(now=500)
        with self.assertRaises(ValueError):
            self.outcome(first,"requested",now=501)
        self.assertFalse(self.call(now=900)["eligible"])
        self.outcome(second,"requested",now=510)
        self.outcome(second,"started",who="dispatcher",run_id=RUN_ID,now=520)

    def test_recovered_attempts_still_consume_hourly_budget(self):
        for instant in (100,400,700):
            reservation=self.call(now=instant)
            self.outcome(reservation,"not_dispatched",now=instant+1)
        self.assertEqual(self.call(now=1000)["reason"],"per_target_hourly_budget")

    def test_legacy_reservation_is_unknown_and_never_silently_retried(self):
        path=self.root/"state/scheduled-wake-history.sqlite3"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE wake_signal(target TEXT,event_kind TEXT,evidence_sha TEXT,"
                       "requestor TEXT,requested_at REAL,PRIMARY KEY(target,event_kind,evidence_sha))")
            db.execute("INSERT INTO wake_signal VALUES(?,?,?,?,?)",
                       ("chief","visual_candidate_ready",S1,"golden",100))
        result=self.call(now=100000)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["delivery_status"],"unknown")

    def test_busy_target_handoff_persists_until_recipient_acknowledges(self):
        for _ in range(2):
            m.defer(self.root,"chief","visual_candidate_ready",S1,"golden",
                    reason="target_busy",now=100)
        pending=m.status(self.root)["pending"]
        self.assertEqual(len(pending),1)
        with self.assertRaises(ValueError):
            m.acknowledge(self.root,"chief","visual_candidate_ready",S1,
                          "golden",RECEIPT,RUN_ID,now=200)
        m.acknowledge(self.root,"chief","visual_candidate_ready",S1,
                      "chief",RECEIPT,RUN_ID,now=201)
        self.assertEqual(m.status(self.root)["pending"],[])
        self.assertEqual(self.call(now=500)["reason"],"already_consumed_exact_evidence")

    def test_reservation_keeps_outbox_pending_until_actual_consumption(self):
        first=self.call()
        self.outcome(first,"requested")
        self.outcome(first,"completed",run_id=RUN_ID)
        self.assertEqual(len(m.status(self.root)["pending"]),1)
        m.acknowledge(self.root,"chief","visual_candidate_ready",S1,
                      "chief",RECEIPT,RUN_ID,now=201)
        self.assertEqual(m.status(self.root)["pending"],[])

    def test_negative_visual_review_is_a_real_handoff_event(self):
        result=m.check(self.root,"chief","visual_review_completed",S1,"golden",True,100)
        self.assertTrue(result["reserved"])
        other=m.defer(self.root,"decision","operation_blocked",S2,"renderer",
                      reason="approval_rejected_no_retry",now=101)
        self.assertTrue(other["deferred"])

    def test_verified_start_recovers_crash_after_run_now_before_request_receipt(self):
        first=self.call()
        self.outcome(first,"started",who="dispatcher",run_id=RUN_ID,now=500)
        self.assertEqual(self.call(now=501)["delivery_status"],"started")
        self.assertFalse(self.call(now=100000)["eligible"])

    def test_budget_denial_keeps_new_event_pending(self):
        self.call()
        denied=self.call(sha=S2,now=101)
        self.assertEqual(denied["reason"],"target_wake_cooldown")
        pending={x["evidence_sha"]:x for x in m.status(self.root)["pending"]}
        self.assertIn(S2,pending)
        self.assertIsNone(pending[S2]["delivery"])
        self.assertTrue(self.call(sha=S2,now=340)["reserved"])

    def test_authorized_setup_operator_is_not_a_fictitious_scheduled_worker(self):
        result=m.check(self.root,"identity","source_pr_ready",S1,"operator",True,100)
        self.assertTrue(result["reserved"])
        self.assertNotIn("operator",m.TARGETS)
        m.record_outcome(self.root,"identity","source_pr_ready",S1,"operator",
                         result["reservation_id"],"requested",RECEIPT,now=101)
        with self.assertRaises(ValueError):
            m.acknowledge(self.root,"identity","source_pr_ready",S1,"operator",
                          RECEIPT,RUN_ID,now=102)

if __name__=="__main__":
    unittest.main()
