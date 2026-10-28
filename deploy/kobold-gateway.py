#!/usr/bin/env python3
"""Private, single-request local LLM gateway. Never persists dialogue.

KoboldCpp (Vulkan) launches on-demand and is killed after EVERY request,
releasing the Radeon for ComfyUI. Bind localhost only; remote access uses
a restricted home-server SSH local forward.
"""
from __future__ import annotations

import json
import hmac
import os
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path.home() / ".local" / "share" / "mcp-vn-kobold"
BINARY = ROOT / "bin" / "koboldcpp"
MODEL = ROOT / "models" / "Qwen3.5-9B-Q4_K_M.gguf"
MODEL_SIZE = 5680522464
MODEL_ID = "qwen3.5:9b-q4_K_M"
CYDONIA_ID = "cydonia:24b-v4.3-iq4_xs"
CYDONIA_MODEL = ROOT / "models" / "TheDrummer_Cydonia-24B-v4.3-IQ4_XS.gguf"
CYDONIA_SIZE = 12758916512
# Dedicated official ROCm 7 build. The existing KoboldCpp executable stays
# untouched and is used for CPU fallback if the ROCm backend fails.
BINARY_ROCM = ROOT / "bin" / "koboldcpp-rocm"
ROCM_BINARY_SIZE = 661999280
ROCM_DISABLED = set()
# Qwen remains the default for the existing visual novel.
OPTIONS = {
    MODEL_ID: (MODEL, MODEL_SIZE, 8192, 99),
    CYDONIA_ID: (CYDONIA_MODEL, CYDONIA_SIZE, 4096, 30),
}
LOCK = threading.Lock()
HOST = os.environ.get("VN_KOBOLD_BIND_HOST", "127.0.0.1")
SECRET = os.environ.get("VN_LOCAL_ROUTER_TOKEN") or os.environ.get("VN_WORKER_TOKEN", "")
PORT = 11434
BACKEND = f"http://127.0.0.1:11435"


def http_json(url: str, body=None, timeout=4.0):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "mcp-vn-local-llm/1"},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(1024 * 512).decode("utf-8"))


def free_comfy():
    # Other GPU work is already prevented by the main server's coordinator.
    # Free only idle cached models and leave the ComfyUI service running.
    req = urllib.request.Request(
        "http://127.0.0.1:8188/free",
        data=b'{"unload_models":true,"free_memory":true}',
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        if r.status != 200:
            raise RuntimeError(f"ComfyUI GPU memory release failed: {r.status}")
        r.read()


def wait_for_backend(process, timeout=65.0):
    until = time.monotonic() + timeout
    while time.monotonic() < until:
        if process.poll() is not None:
            raise RuntimeError(f"KoboldCpp process exited ({process.returncode})")
        try:
            info = http_json(BACKEND + "/api/v1/model", timeout=1)
            if isinstance(info, dict):
                return
        except Exception:
            pass
        time.sleep(0.35)
    raise TimeoutError("KoboldCpp model did not become ready")


def backend_for(model: str) -> str:
    """ROCm is opt-in by service environment; CPU is a persistent fallback."""
    if os.environ.get("VN_KOBOLD_CPU_ONLY", "0") == "1":
        return "cpu"
    if os.environ.get("VN_KOBOLD_BACKEND", "cpu").lower() != "rocm":
        return "cpu"
    if model in ROCM_DISABLED:
        return "cpu"
    if (not BINARY_ROCM.is_file() or
            BINARY_ROCM.stat().st_size != ROCM_BINARY_SIZE):
        return "cpu"
    return "rocm"


def run_single_inference(chosen, model_path, ctx_size, gpu_layers,
                         clean, params, max_tokens, mode):
    """Always terminate the transient LLM process and release the GPU."""
    started = time.monotonic()
    if mode == "rocm":
        # ComfyUI may have cached Pony/WAI/Anima weights after the queue
        # becomes empty. Free those buffers before allocating LLM tensors.
        free_comfy()
    os.makedirs(ROOT / "logs", mode=0o700, exist_ok=True)
    logfile = ROOT / "logs" / "kobold-last.log"
    binary = BINARY_ROCM if mode == "rocm" else BINARY
    cmd = [
        str(binary),
        "--model", str(model_path),
        "--host", "127.0.0.1", "--port", "11435",
        "--contextsize", str(ctx_size), "--threads", "7",
        "--reasoningeffort", "none",
        "--skiplauncher", "--quiet",
    ]
    if chosen == MODEL_ID:
        # Qwen3.5 can emit lengthy <think> traces even with
        # --reasoningeffort none. Set the model chat-template switch too.
        cmd += ["--jinjathink", "false"]
    if mode == "rocm":
        cmd += ["--usecuda", "--gpulayers", str(gpu_layers)]
    else:
        cmd += ["--usecpu"]
    process = None
    with open(logfile, "wb") as logs:
        try:
            process = subprocess.Popen(
                cmd, stdin=subprocess.DEVNULL, stdout=logs,
                stderr=subprocess.STDOUT, start_new_session=True,
            )
            wait_for_backend(process, timeout=75)
            loaded = time.monotonic()
            request = {
                "model": chosen, "messages": clean,
                "max_tokens": max_tokens,
                "temperature": float(params.get("temperature", 0.75)),
                "top_p": float(params.get("top_p", 0.9)),
                "stream": False,
            }
            response = http_json(
                BACKEND + "/v1/chat/completions", request, timeout=125)
            result = (response.get("choices") or [{}])[0].get("message") or {}
            output = result.get("content")
            if not isinstance(output, str) or not output.strip():
                raise RuntimeError("KoboldCpp returned no dialogue")
            finished = time.monotonic()
            usage = response.get("usage") or {}
            return {
                "message": {"role": "assistant", "content": output},
                "total_duration": int((finished - started) * 1e9),
                "load_duration": int((loaded - started) * 1e9),
                "prompt_eval_count": int(usage.get("prompt_tokens") or 0),
                "eval_count": int(usage.get("completion_tokens") or 0),
                "eval_duration": int((finished - loaded) * 1e9),
                "backend": "koboldcpp-" + mode,
                "model": chosen,
            }
        finally:
            if process is not None and process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=8)
                except (ProcessLookupError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=4)


def generate(payload: dict):
    if not MODEL.is_file() or MODEL.stat().st_size != MODEL_SIZE:
        raise RuntimeError("Qwen model is not fully installed")
    if not BINARY.is_file():
        raise RuntimeError("CPU fallback executable is missing")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not 1 <= len(messages) <= 24:
        raise ValueError("Expected 1-24 message objects")
    clean = []
    for m in messages:
        if not isinstance(m, dict):
            raise ValueError("Invalid message")
        role, value = m.get("role"), m.get("content")
        if role not in ("system", "user", "assistant") or not isinstance(value, str):
            raise ValueError("Invalid message role or content")
        clean.append({"role": role, "content": value[:20000]})
    params = payload.get("options") or {}
    max_tokens = max(64, min(512, int(params.get("num_predict", 320))))
    chosen = payload.get("model") or MODEL_ID
    if not isinstance(chosen, str) or chosen not in OPTIONS:
        raise ValueError("Unknown local LLM model")
    model_path, model_size, ctx_size, gpu_layers = OPTIONS[chosen]
    if not model_path.is_file() or model_path.stat().st_size != model_size:
        raise RuntimeError("Requested local LLM model is not installed completely")
    # Image generation and narrative inference share one Radeon. Respect
    # any in-progress ComfyUI task rather than evicting its model.
    current_jobs = http_json("http://127.0.0.1:8188/queue", timeout=5)
    if current_jobs.get("queue_running") or current_jobs.get("queue_pending"):
        raise RuntimeError("GPU busy with image-generation jobs; retry afterwards")

    mode = backend_for(chosen)
    try:
        return run_single_inference(
            chosen, model_path, ctx_size, gpu_layers, clean,
            params, max_tokens, mode)
    except Exception as error:
        if mode != "rocm":
            raise
        # Circuit breaker: never repeatedly stress a failing AMD GPU in
        # this service lifetime. CPU fallback is safe for existing stories.
        ROCM_DISABLED.add(chosen)
        print("ROCM_FALLBACK", chosen, type(error).__name__,
              str(error)[:160], flush=True)
        return run_single_inference(
            chosen, model_path, ctx_size, gpu_layers, clean,
            params, max_tokens, "cpu")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def authenticated(self):
        if not SECRET:
            return HOST == "127.0.0.1"
        supplied = self.headers.get("Authorization", "")
        return hmac.compare_digest(supplied, "Bearer " + SECRET)

    def log_message(self, fmt, *args):
        # No prompt, completion, user action or tokens in systemd journal.
        if args:
            print("REQUEST", str(args[0])[:130], flush=True)

    def reply(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.authenticated():
            return self.reply(401, {"error": "Authentication required"})
        if self.path == "/api/tags":
            installed = [
                {"name": key, "model": key,
                 "backend": "koboldcpp-" + backend_for(key)}
                for key,(path,size,_,__) in OPTIONS.items()
                if BINARY.exists() and path.is_file() and path.stat().st_size==size
            ]
            self.reply(200, {
                "models": installed,
                "backend": "koboldcpp", "busy": LOCK.locked(),
            })
        elif self.path == "/healthz":
            self.reply(200, {"ok": True, "name": "mcp-vn-local-kobold-router"})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        if not self.authenticated():
            return self.reply(401, {"error": "Authentication required"})
        if self.path != "/api/chat":
            return self.reply(404, {"error": "not found"})
        if not LOCK.acquire(blocking=False):
            return self.reply(409, {"error": "A local generation is already running"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 160000:
                return self.reply(413, {"error": "Invalid request size"})
            try:
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("Expected an object")
                result = generate(payload)
                self.reply(200, result)
            except (ValueError, TypeError) as e:
                self.reply(400, {"error": str(e)[:180]})
            except Exception as e:
                self.reply(503, {"error": str(e)[:180]})
        finally:
            LOCK.release()


if __name__ == "__main__":
    print("mcp-vn local Kobold gateway listening on "+HOST+":11434", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever(poll_interval=0.3)
