"""Disposable, synthetic crash/retry/rollback rehearsal; no live saves or GPU."""
import importlib.util
import pathlib
import tempfile
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "render_e2e_rehearsal.py"
SPEC = importlib.util.spec_from_file_location("render_e2e_rehearsal", MODULE)
REHEARSAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REHEARSAL)


class RehearsalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="web-vn-e2e-synthetic-")
        self.root = pathlib.Path(self.tmp.name)
        self.store = REHEARSAL.Rehearsal.create(self.root,
            game_id="synthetic-game", version=12, scene_fingerprint="a"*64,
            action_id="synthetic-action", accepted_asset=b"old-accepted-image")
        self.original_save = (self.root/"save.json").read_bytes()
        self.original_asset = (self.root/"assets/accepted.bin").read_bytes()
        self.store.prepare("job-new", b"synthetic-candidate", expected_version=12,
                           expected_scene_fingerprint="a"*64,
                           expected_action_id="synthetic-action")

    def tearDown(self):
        self.tmp.cleanup()

    def assert_old_intact(self):
        self.assertEqual((self.root/"save.json").read_bytes(), self.original_save)
        self.assertEqual((self.root/"assets/accepted.bin").read_bytes(), self.original_asset)

    def test_qa_rejection_does_not_publish(self):
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.publish("job-new", qa_accepted=False)
        self.assert_old_intact()

    def test_crash_after_asset_does_not_change_save_or_old_asset(self):
        with self.assertRaises(REHEARSAL.CrashInjected):
            self.store.publish("job-new", qa_accepted=True, crash_at="after_asset")
        self.assert_old_intact()
        self.assertTrue((self.root/"assets/job-new.bin").exists())

    def test_recovery_rolls_back_orphan_and_never_auto_publishes(self):
        with self.assertRaises(REHEARSAL.CrashInjected):
            self.store.publish("job-new", qa_accepted=True, crash_at="after_asset")
        restarted = REHEARSAL.Rehearsal(self.root)
        self.assertEqual(restarted.recover()["job-new"], "needs_review")
        self.assertFalse((self.root/"assets/job-new.bin").exists())
        self.assert_old_intact()
        with self.assertRaises(REHEARSAL.FenceRejected):
            restarted.publish("job-new", qa_accepted=True)
        restarted.reauthorize("job-new", approved=True)
        self.assertEqual(restarted.publish("job-new", qa_accepted=True), "applied")

    def test_crash_after_save_recovery_is_idempotent(self):
        with self.assertRaises(REHEARSAL.CrashInjected):
            self.store.publish("job-new", qa_accepted=True, crash_at="after_save")
        before = self.store.state()
        self.assertEqual(before["version"], 13)
        restarted = REHEARSAL.Rehearsal(self.root)
        self.assertEqual(restarted.recover()["job-new"], "committed")
        self.assertEqual(restarted.publish("job-new", qa_accepted=True), "already_applied")
        self.assertEqual(restarted.state(), before)
        self.assertEqual((self.root/"assets/accepted.bin").read_bytes(), self.original_asset)

    def test_same_scene_but_changed_version_rejected(self):
        current = self.store.state()
        current["version"] = 14
        self.store._write_json(self.root/"save.json", current)
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.publish("job-new", qa_accepted=True)

    def test_same_version_but_changed_scene_rejected(self):
        current = self.store.state()
        current["scene_fingerprint"] = "b"*64
        self.store._write_json(self.root/"save.json", current)
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.publish("job-new", qa_accepted=True)

    def test_changed_action_rejected(self):
        current = self.store.state()
        current["action_id"] = "later-action"
        self.store._write_json(self.root/"save.json", current)
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.publish("job-new", qa_accepted=True)

    def test_candidate_tampering_rejected(self):
        (self.root/"candidates/job-new.bin").write_bytes(b"tampered")
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.publish("job-new", qa_accepted=True)
        self.assert_old_intact()

    def test_publish_retry_does_not_duplicate_version(self):
        self.assertEqual(self.store.publish("job-new", qa_accepted=True), "applied")
        self.assertEqual(self.store.publish("job-new", qa_accepted=True), "already_applied")
        self.assertEqual(self.store.state()["version"], 13)

    def test_rollback_restores_previous_asset_and_monotonic_version(self):
        self.store.publish("job-new", qa_accepted=True)
        self.assertEqual(self.store.rollback("job-new"), "rolled_back")
        game = self.store.state()
        self.assertEqual(game["version"], 14)
        self.assertEqual(game["published_job_id"], "previous")
        self.assertEqual(game["asset_name"], "accepted.bin")
        self.assertEqual((self.root/"assets/accepted.bin").read_bytes(), self.original_asset)
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.publish("job-new", qa_accepted=True)

    def test_recovery_keeps_prior_committed_asset_for_newer_rollback(self):
        self.store.publish("job-new", qa_accepted=True)
        self.store.prepare("job-next", b"next-candidate", expected_version=13,
                           expected_scene_fingerprint="a"*64,
                           expected_action_id="synthetic-action")
        self.store.publish("job-next", qa_accepted=True)
        restarted = REHEARSAL.Rehearsal(self.root)
        statuses = restarted.recover()
        self.assertEqual(statuses["job-new"], "committed")
        self.assertEqual(statuses["job-next"], "committed")
        self.assertTrue((self.root/"assets/job-new.bin").exists())
        self.assertEqual(restarted.rollback("job-next"), "rolled_back")
        self.assertEqual(restarted.state()["asset_name"], "job-new.bin")

    def test_rollback_refuses_to_overwrite_newer_save(self):
        self.store.publish("job-new", qa_accepted=True)
        current = self.store.state()
        current["version"] = 14
        current["action_id"] = "newer-action"
        self.store._write_json(self.root/"save.json", current)
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.rollback("job-new")
        self.assertEqual(self.store.state(), current)

    def test_duplicate_job_id_and_path_traversal_rejected(self):
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.prepare("job-new", b"different", expected_version=12,
                               expected_scene_fingerprint="a"*64,
                               expected_action_id="synthetic-action")
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.prepare("../escape", b"x", expected_version=12,
                               expected_scene_fingerprint="a"*64,
                               expected_action_id="synthetic-action")

    def test_unapproved_recovery_cannot_restart_publish(self):
        with self.assertRaises(REHEARSAL.CrashInjected):
            self.store.publish("job-new", qa_accepted=True, crash_at="after_asset")
        self.store.recover()
        with self.assertRaises(REHEARSAL.FenceRejected):
            self.store.reauthorize("job-new", approved=False)
        self.assert_old_intact()


if __name__ == "__main__":
    unittest.main()
