"""CPU-only KoboldCpp external GPU lease integration tests."""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

p = Path(__file__).resolve().parents[1] / "deploy/kobold-gateway.py"
spec = importlib.util.spec_from_file_location("kobold_broker_gateway", p)
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


class File:
    def is_file(self):
        return True

    def stat(self):
        return types.SimpleNamespace(st_size=g.MODEL_SIZE)


class GatewayLeaseTests(unittest.TestCase):
    def setUp(self):
        g.ROCM_DISABLED.clear()

    def tearDown(self):
        g.ROCM_DISABLED.clear()

    def test_context_releases_even_on_exception(self):
        calls = []
        def api(path, body=None, timeout=4):
            calls.append((path, body))
            if path.endswith("/acquire"):
                return {"lease_id": "11111111-1111-4111-8111-111111111111"}
            return {"released": True}
        with patch.object(g, "http_json", side_effect=api):
            with self.assertRaisesRegex(RuntimeError, "test_failure"):
                with g.gpu_lease() as lease:
                    self.assertEqual(len(lease), 36)
                    raise RuntimeError("test_failure")
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][0].endswith("/acquire"))
        self.assertTrue(calls[1][0].endswith("/release"))

    def test_free_requires_and_sends_lease_header(self):
        seen = []
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b""
        def fake_open(request, timeout=10):
            seen.append(request.get_header("X-gpu-lease-id"))
            return Response()
        with patch.object(g.urllib.request, "urlopen", side_effect=fake_open):
            g.free_comfy("lease-token")
        self.assertEqual(seen, ["lease-token"])

    def test_rocm_lease_spans_entire_inference(self):
        events = []
        @contextmanager
        def lease():
            events.append("acquire")
            try: yield "lease-token"
            finally: events.append("release")
        def runner(*args, **kwargs):
            events.append("inference")
            self.assertEqual(args[-1], "rocm")
            self.assertEqual(kwargs["lease_id"], "lease-token")
            return {"backend": "rocm"}
        with patch.object(g, "MODEL", File()), patch.object(g, "BINARY", File()), \
             patch.dict(g.OPTIONS, {g.MODEL_ID: (File(), g.MODEL_SIZE, 4096, 10)}), \
             patch.object(g, "backend_for", return_value="rocm"), \
             patch.object(g, "http_json", return_value={"queue_running": [], "queue_pending": []}), \
             patch.object(g, "gpu_lease", side_effect=lease), \
             patch.object(g, "run_single_inference", side_effect=runner):
            result = g.generate({"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(result["backend"], "rocm")
        self.assertEqual(events, ["acquire", "inference", "release"])

    def test_preflight_comfy_queue_busy_uses_cpu(self):
        modes = []
        def runner(*args, **kwargs):
            modes.append(args[-1])
            return {"backend": "cpu"}
        with patch.object(g, "MODEL", File()), patch.object(g, "BINARY", File()), \
             patch.dict(g.OPTIONS, {g.MODEL_ID: (File(), g.MODEL_SIZE, 4096, 10)}), \
             patch.object(g, "backend_for", return_value="rocm"), \
             patch.object(g, "http_json", return_value={"queue_running": [["job"]], "queue_pending": []}), \
             patch.object(g, "gpu_lease", side_effect=AssertionError("GPU lease must not be acquired")), \
             patch.object(g, "run_single_inference", side_effect=runner):
            result = g.generate({"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(result["backend"], "cpu")
        self.assertEqual(modes, ["cpu"])

    def test_gpu_contention_uses_cpu_without_rocm_circuit_breaker(self):
        events = []
        @contextmanager
        def busy():
            raise g.GPUBusy("already owned")
            yield
        def runner(*args, **kwargs):
            events.append(args[-1])
            return {"backend": "cpu"}
        with patch.object(g, "MODEL", File()), patch.object(g, "BINARY", File()), \
             patch.dict(g.OPTIONS, {g.MODEL_ID: (File(), g.MODEL_SIZE, 4096, 10)}), \
             patch.object(g, "backend_for", return_value="rocm"), \
             patch.object(g, "http_json", return_value={"queue_running": [], "queue_pending": []}), \
             patch.object(g, "gpu_lease", side_effect=busy), \
             patch.object(g, "run_single_inference", side_effect=runner):
            result = g.generate({"messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(result["backend"], "cpu")
        self.assertEqual(events, ["cpu"])
        self.assertNotIn(g.MODEL_ID, g.ROCM_DISABLED)


if __name__ == "__main__":
    unittest.main()
