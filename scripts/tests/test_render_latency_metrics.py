"""Offline synthetic regression tests only: no real PNG, GPU or network."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from render_latency_metrics import summarize_latency

STAGES = ("queue", "preflight", "comfy", "postprocess", "qa", "repair", "publish")


def sha(s):
    return hashlib.sha256(s.encode("ascii")).hexdigest()


def stamp(t):
    return t.isoformat().replace("+00:00", "Z")


def observation(n=1, *, repair=True, outcome="published", comfy_ms=300):
    t = datetime(2026, 10, 31, tzinfo=timezone.utc) + timedelta(seconds=n * 20)
    provenance = {
        "frame_id": f"frame-{n}", "job_id": f"job-{n}",
        "prompt_id": f"prompt-{n}", "png_sha256": sha(f"png-{n}"),
        "contract_sha256": sha(f"contract-{n}"),
        "source_sha256": sha(f"source-{n}"),
    }
    stages = {}
    beginning = t - timedelta(milliseconds=100)
    for stage in STAGES:
        if stage == "repair" and not repair:
            continue
        if stage == "publish" and outcome != "published":
            continue
        duration = comfy_ms if stage == "comfy" else 100
        start, end = t, t + timedelta(milliseconds=duration)
        stages[stage] = {
            "started_at": stamp(start), "ended_at": stamp(end),
            **{key: provenance[key] for key in ("frame_id", "job_id", "prompt_id", "png_sha256")},
        }
        t = end
    stages["full_turn"] = {
        "started_at": stamp(beginning),
        "ended_at": stamp(t + timedelta(milliseconds=100)),
        **{key: provenance[key] for key in ("frame_id", "job_id", "prompt_id", "png_sha256")},
    }
    return {"scene_id": f"scene-{n}", "provenance": provenance,
            "outcome": outcome, "stages": stages}


def document(*items):
    return {"schema_version": 1, "observations": list(items)}


def metric(result, name):
    return result["metrics"][name]


class LatencyMetricsTest(unittest.TestCase):
    def test_valid_p50_p90_from_real_timestamp_differences(self):
        result = summarize_latency(document(observation(1, comfy_ms=100),
                                            observation(2, comfy_ms=300)))
        self.assertEqual(result["valid_observations"], 2)
        self.assertEqual(result["invalid_observations"], 0)
        self.assertEqual(metric(result, "comfy")["p50_ms"], 100)
        self.assertEqual(metric(result, "comfy")["p90_ms"], 300)
        self.assertEqual(metric(result, "comfy")["n"], 2)
        self.assertEqual(metric(result, "full_turn")["n"], 2)
        self.assertEqual(result["g2_status"], "UNVERIFIED")
        self.assertEqual(result["g3_status"], "NO_GO")
        self.assertFalse(result["release_eligible"])

    def test_empty_denominator_never_zero(self):
        result = summarize_latency(document())
        self.assertEqual(result["valid_observations"], 0)
        for stage in (*STAGES, "full_turn"):
            self.assertEqual(metric(result, stage)["status"], "NOT_MEASURED")
            self.assertEqual(metric(result, stage)["n"], 0)
            self.assertIsNone(metric(result, stage)["p50_ms"])
            self.assertIsNone(metric(result, stage)["p90_ms"])

    def test_absent_stage_does_not_become_zero_or_full_turn(self):
        x = observation()
        del x["stages"]["preflight"]
        result = summarize_latency(document(x))
        self.assertEqual(result["valid_observations"], 1)
        self.assertEqual(metric(result, "preflight")["status"], "NOT_MEASURED")
        self.assertEqual(metric(result, "full_turn")["status"], "NOT_MEASURED")
        self.assertEqual(metric(result, "comfy")["n"], 1)

    def test_missing_timestamp_invalidates_whole_observation(self):
        x = observation()
        del x["stages"]["comfy"]["started_at"]
        result = summarize_latency(document(x))
        self.assertEqual(result["valid_observations"], 0)
        self.assertEqual(result["invalid_observations"], 1)
        self.assertEqual(metric(result, "queue")["n"], 0)
        self.assertTrue(any("comfy" in issue for issue in result["issues"]))

    def test_reversed_timestamps_fail_closed(self):
        x = observation()
        x["stages"]["comfy"]["ended_at"] = x["stages"]["comfy"]["started_at"]
        self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)

    def test_mixed_frame_job_prompt_or_png_fail_closed(self):
        for field in ("frame_id", "job_id", "prompt_id", "png_sha256"):
            with self.subTest(field=field):
                x = observation()
                x["stages"]["qa"][field] = sha("different") if field == "png_sha256" else "different"
                result = summarize_latency(document(x))
                self.assertEqual(result["invalid_observations"], 1)
                self.assertEqual(metric(result, "comfy")["n"], 0)

    def test_mixed_frame_full_turn_invalid(self):
        x = observation()
        x["stages"]["full_turn"]["frame_id"] = "other-frame"
        self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)

    def test_overlapping_or_out_of_order_stages_invalid(self):
        x = observation()
        x["stages"]["postprocess"]["started_at"] = x["stages"]["preflight"]["started_at"]
        self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)

    def test_full_turn_must_enclose_stages(self):
        x = observation()
        x["stages"]["full_turn"]["ended_at"] = x["stages"]["queue"]["ended_at"]
        self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)

    def test_naive_or_malformed_timestamps_invalid(self):
        for bad in ("2026-10-31T12:00:00", "not-time", True, None, 123):
            with self.subTest(bad=bad):
                x = observation()
                x["stages"]["qa"]["started_at"] = bad
                self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)

    def test_duplicates_not_counted_as_independent(self):
        for field in ("scene_id", "frame_id", "job_id", "prompt_id",
                      "png_sha256", "contract_sha256"):
            with self.subTest(field=field):
                a, b = observation(1), observation(2)
                if field == "scene_id":
                    b["scene_id"] = a["scene_id"]
                else:
                    b["provenance"][field] = a["provenance"][field]
                    if field in ("frame_id", "job_id", "prompt_id", "png_sha256"):
                        for stage in b["stages"].values():
                            stage[field] = a["provenance"][field]
                result = summarize_latency(document(a, b))
                self.assertEqual(result["valid_observations"], 1)
                self.assertEqual(result["invalid_observations"], 1)

    def test_invalid_provenance_or_missing_stage_mapping(self):
        for field in ("frame_id", "job_id", "prompt_id", "png_sha256", "contract_sha256", "source_sha256"):
            with self.subTest(field=field):
                x = observation()
                x["provenance"].pop(field)
                self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)
        x = observation()
        x["stages"] = {}
        self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)

    def test_unknown_stage_and_outcome_rejected(self):
        x = observation()
        x["stages"]["unknown_stage"] = x["stages"]["qa"]
        self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)
        x = observation()
        x["outcome"] = "unknown"
        self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)

    def test_rejected_turn_without_publish_is_measurable(self):
        x = observation(outcome="rejected")
        result = summarize_latency(document(x))
        self.assertEqual(metric(result, "publish")["status"], "NOT_MEASURED")
        self.assertEqual(metric(result, "full_turn")["n"], 1)
        self.assertEqual(result["by_outcome"]["rejected"]["full_turn"]["n"], 1)

    def test_rejected_turn_with_publish_is_invalid(self):
        x = observation(outcome="rejected")
        x["stages"]["publish"] = copy.deepcopy(observation()["stages"]["publish"])
        self.assertEqual(summarize_latency(document(x))["invalid_observations"], 1)

    def test_published_without_publish_cannot_claim_complete_turn(self):
        x = observation()
        del x["stages"]["publish"]
        result = summarize_latency(document(x))
        self.assertEqual(metric(result, "full_turn")["status"], "NOT_MEASURED")
        self.assertEqual(metric(result, "qa")["n"], 1)

    def test_no_repair_is_missing_not_zero_and_turn_can_complete(self):
        result = summarize_latency(document(observation(repair=False)))
        self.assertEqual(metric(result, "repair")["status"], "NOT_MEASURED")
        self.assertEqual(metric(result, "full_turn")["n"], 1)

    def test_mixed_outcomes_have_separate_metrics(self):
        result = summarize_latency(document(observation(1), observation(2, outcome="rejected")))
        self.assertEqual(result["by_outcome"]["published"]["full_turn"]["n"], 1)
        self.assertEqual(result["by_outcome"]["rejected"]["full_turn"]["n"], 1)

    def test_timezone_offsets_supported(self):
        x = observation()
        x["stages"]["qa"]["started_at"] = (
            datetime.fromisoformat(x["stages"]["qa"]["started_at"].replace("Z", "+00:00"))
            .astimezone(timezone(timedelta(hours=3))).isoformat())
        result = summarize_latency(document(x))
        self.assertEqual(result["valid_observations"], 1)

    def test_invalid_root_rejected_without_data_echo(self):
        for bad in ([], {}, {"schema_version": 2, "observations": []},
                    {"schema_version": 1, "observations": {}}):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    summarize_latency(bad)


if __name__ == "__main__":
    unittest.main()
