import importlib.util
import pathlib
import unittest

MODULE = pathlib.Path(__file__).resolve().parents[1] / "cli-proxy-quota.py"
spec = importlib.util.spec_from_file_location("quota_cli", MODULE)
quota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quota)


class QuotaParsingTests(unittest.TestCase):
    def test_codex_real_shape(self):
        item = quota.parse_codex({"plan_type": "plus", "rate_limit": {
            "allowed": True, "limit_reached": False,
            "primary_window": {"used_percent": 2, "limit_window_seconds": 18000, "reset_at": 1793404154},
            "secondary_window": {"used_percent": 9, "limit_window_seconds": 604800, "reset_at": 1793801834},
        }})
        self.assertEqual(item["status"], "ok")
        self.assertEqual(item["windows"]["7d_or_secondary"]["remaining_percent"], 91)

    def test_grok_weekly_real_shape(self):
        item = quota.parse_xai({"config": {
            "creditUsagePercent": 81.0,
            "currentPeriod": {
                "type": "USAGE_PERIOD_TYPE_WEEKLY",
                "start": "2026-10-28T10:49:08.008+00:00",
                "end": "2026-11-04T10:49:08.008+00:00",
            },
        }})
        self.assertEqual(item["status"], "ok")
        self.assertEqual(item["remaining_percent"], 19)
        self.assertEqual(item["period"], "weekly")
        self.assertEqual(item["window_seconds"], 604800)

    def test_unknown_usage_does_not_claim_full_quota(self):
        item = quota.parse_xai({"config": {"currentPeriod": {
            "type": "USAGE_PERIOD_TYPE_WEEKLY", "end": "2026-11-04T10:49:08Z",
        }}})
        self.assertEqual(item["status"], "unavailable")
        self.assertIsNone(item["remaining_percent"])

    def test_untrusted_out_of_range_values(self):
        for value in (-1, 101, float("nan"), float("inf"), "81", True):
            with self.subTest(value=value):
                self.assertIsNone(quota.percentage(value))

    def test_date_required_timezone(self):
        self.assertIsNone(quota.iso_time("2026-11-04T10:49:08"))
        self.assertEqual(quota.iso_time("2026-11-04T10:49:08Z"), "2026-11-04T10:49:08+00:00")

    def test_bad_period(self):
        item = quota.parse_xai({"config": {"creditUsagePercent": 40,
            "currentPeriod": {"type": "mystery", "start": "2026-11-05T00:00:00Z",
                              "end": "2026-11-04T00:00:00Z"}}})
        self.assertEqual(item["status"], "ok")
        self.assertIsNone(item["window_seconds"])
        self.assertEqual(item["period"], "unknown")

    def test_invalid_shapes(self):
        self.assertEqual(quota.parse_xai({})["status"], "unavailable")
        self.assertEqual(quota.parse_codex({})["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
