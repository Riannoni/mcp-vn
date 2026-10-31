#!/usr/bin/env python3
"""Private, single-request local LLM gateway. Never persists dialogue.

KoboldCpp (Vulkan) launches on-demand and is killed after EVERY request,
releasing the Radeon for ComfyUI. Bind localhost only; remote access uses
a restricted home-server SSH local forward.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
import hmac
import os
import signal
import stat
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


def http_json(url: str, body=None, timeout=4.0, headers=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    request_headers = {"Content-Type": "application/json",
                       "User-Agent": "mcp-vn-local-llm/1"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(
        url, data=data, headers=request_headers,
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(1024 * 512).decode("utf-8"))


class GPUBusy(RuntimeError):
    """Broker has an active Comfy job, foreign owner or queued work."""


def broker_lease_token():
    name = os.environ.get("VN_BROKER_LEASE_TOKEN_FILE")
    if not name:
        raise RuntimeError("GPU broker credential not configured")
    path = Path(name)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
        raise RuntimeError("GPU broker credential permissions invalid")
    if info.st_uid != os.geteuid():
        raise RuntimeError("GPU broker credential owner invalid")
    token = path.read_text(encoding="ascii").strip()
    if not (32 <= len(token) <= 128) or any(c.isspace() for c in token):
        raise RuntimeError("GPU broker credential invalid")
    return token


@contextmanager
def gpu_lease():
    credential = broker_lease_token()
    headers = {"Authorization": "Bearer " + credential}
    try:
        receipt = http_json("http://127.0.0.1:8188/broker/external/acquire",
                            {"client": "kobold-gateway"}, timeout=6,
                            headers=headers)
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            raise GPUBusy("GPU broker has an active owner") from exc
        raise
    lease_id = receipt.get("lease_id")
    if not isinstance(lease_id, str) or len(lease_id) < 16:
        raise RuntimeError("GPU broker returned invalid lease")
    try:
        yield lease_id
    finally:
        # Only after run_single_inference's process-cleanup finally has finished.
        released = http_json("http://127.0.0.1:8188/broker/external/release",
                             {"lease_id": lease_id}, timeout=6,
                             headers=headers)
        if released.get("released") is not True:
            raise RuntimeError("GPU broker lease release unconfirmed")


def free_comfy(lease_id):
    # Other GPU work is already prevented by the main server's coordinator.
    # Free only idle cached models and leave the ComfyUI service running.
    req = urllib.request.Request(
        "http://127.0.0.1:8188/free",
        data=b'{"unload_models":true,"free_memory":true}',
        headers={"Content-Type": "application/json", "X-GPU-Lease-ID": lease_id},
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
                         clean, params, max_tokens, mode, lease_id=None):
    """Always terminate the transient LLM process and release the GPU."""
    started = time.monotonic()
    if mode == "rocm":
        # ComfyUI may have cached Pony/WAI/Anima weights after the queue
        # becomes empty. Free those buffers before allocating LLM tensors.
        if not lease_id:
            raise RuntimeError("ROCm inference requires durable GPU broker lease")
        free_comfy(lease_id)
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
    gpu_busy = bool(current_jobs.get("queue_running") or current_jobs.get("queue_pending"))
    # Keep local narration available on CPU while the sole Radeon is owned.
    mode = "cpu" if gpu_busy else backend_for(chosen)
    try:
        if mode == "rocm":
            with gpu_lease() as lease_id:
                return run_single_inference(
                    chosen, model_path, ctx_size, gpu_layers, clean,
                    params, max_tokens, mode, lease_id=lease_id)
        return run_single_inference(
            chosen, model_path, ctx_size, gpu_layers, clean,
            params, max_tokens, mode)
    except GPUBusy:
        # Ordinary contention is NOT a ROCm failure and must not trip circuit breaker.
        return run_single_inference(
            chosen, model_path, ctx_size, gpu_layers, clean,
            params, max_tokens, "cpu")
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


# Only OpenAI/Codex and xAI/Grok subscription model identifiers may be
# forwarded to the one local universal proxy. Local model aliases must
# never round-trip back here, which would create a recursive proxy loop.
CLOUD_PREFIXES=("gpt","codex","grok","xai/","o1","o3","o4")
UNIVERSAL_PROXY="http://127.0.0.1:8317"
UNIVERSAL_KEY=ROOT.parent/"mcp-vn-universal-proxy/client-key"


def generate_cloud(payload:dict):
    model=payload.get("model")
    if not isinstance(model,str) or len(model)>95 or not model.startswith(CLOUD_PREFIXES):
        raise ValueError("Unsupported cloud model")
    if not UNIVERSAL_KEY.is_file():
        raise RuntimeError("Universal subscription gateway is not installed")
    key=UNIVERSAL_KEY.read_text().strip()
    if len(key)<25:raise RuntimeError("Universal gateway client key unavailable")
    headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"}
    catalog=urllib.request.Request(UNIVERSAL_PROXY+"/v1/models",headers=headers)
    try:
        with urllib.request.urlopen(catalog,timeout=8) as r:
            models=json.loads(r.read(160000)).get("data",[])
    except Exception as e:
        raise RuntimeError("Universal gateway model catalog unavailable") from e
    if model not in {m.get("id") for m in models}:
        raise ValueError("Cloud model is not connected. Sign in via VN Web")
    messages=payload.get("messages")
    if not isinstance(messages,list) or not 1<=len(messages)<=24:
        raise ValueError("Expected 1-24 cloud messages")
    clean=[]
    for m in messages:
        if not isinstance(m,dict) or m.get("role") not in ("system","user","assistant"):
            raise ValueError("Invalid role")
        value=m.get("content")
        if not isinstance(value,str):raise ValueError("Invalid cloud message")
        clean.append({"role":m["role"],"content":value[:20000]})
    options=payload.get("options") or {}
    tokens=max(64,min(512,int(options.get("num_predict",320))))
    request=urllib.request.Request(UNIVERSAL_PROXY+"/v1/chat/completions",
        data=json.dumps({
            "model":model,"messages":clean,"temperature":float(options.get("temperature",0.7)),
            "top_p":float(options.get("top_p",0.9)),
            "max_tokens":tokens,"stream":False
        }).encode(),headers=headers,method="POST")
    started=time.monotonic()
    try:
        with urllib.request.urlopen(request,timeout=155) as r:
            body=json.loads(r.read(150000))
    except urllib.error.HTTPError as e:
        # Report only a status, never dump credentials or private upstream
        # response text into logs.
        raise RuntimeError("Subscription model HTTP "+str(e.code)) from None
    except Exception as e:
        raise RuntimeError("Subscription model request failed") from e
    content=((body.get("choices") or [{}])[0].get("message") or {}).get("content")
    if not isinstance(content,str) or not content.strip():
        raise RuntimeError("Subscription model returned no text")
    duration=int((time.monotonic()-started)*1e9)
    usage=body.get("usage") or {}
    return {"message":{"role":"assistant","content":content},
        "model":model,"backend":"cliproxyapi-subscription",
        "total_duration":duration,"load_duration":0,
        "eval_count":int(usage.get("completion_tokens") or 0),
        "prompt_eval_count":int(usage.get("prompt_tokens") or 0),
        "eval_duration":duration}



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
        elif self.path == "/v1/models":
            self.reply(200, {"object": "list", "data": [
                {"id": model, "object": "model", "created": 0,
                 "owned_by": "mcp-vn-local"}
                for model,(path,size,_,__) in OPTIONS.items()
                if path.is_file() and path.stat().st_size == size
            ]})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        if not self.authenticated():
            return self.reply(401, {"error": "Authentication required"})
        is_chat=self.path=="/api/chat"
        is_openai=self.path=="/v1/chat/completions"
        if not (is_chat or is_openai):
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
                if is_openai:
                    if payload.get("stream"):
                        raise ValueError("Local compatibility endpoint requires stream=false")
                    model=payload.get("model")
                    if model not in OPTIONS:
                        raise ValueError("Unknown local LLM model")
                    tokens=payload.get("max_completion_tokens",
                                       payload.get("max_tokens",320))
                    limit=max(64,min(512,int(tokens)))
                    result=generate({
                        "model":model,"messages":payload.get("messages"),
                        "options":{
                            "num_predict":limit,
                            "temperature":payload.get("temperature",0.75),
                            "top_p":payload.get("top_p",0.9)
                        }})
                    created=int(time.time())
                    self.reply(200,{
                        "id":"chatcmpl-local-"+str(created),
                        "object":"chat.completion","created":created,
                        "model":model,
                        "choices":[{"index":0,"finish_reason":"stop",
                           "message":{"role":"assistant",
                                      "content":result["message"]["content"]}}],
                        "usage":{
                           "prompt_tokens":result.get("prompt_eval_count",0),
                           "completion_tokens":result.get("eval_count",0),
                           "total_tokens":result.get("prompt_eval_count",0)+
                                result.get("eval_count",0)},
                        "vn_backend":result.get("backend","unknown"),
                        "vn_total_duration_ns":result.get("total_duration",0)
                    })
                else:
                    model=payload.get("model")
                    result=(generate_cloud(payload) if isinstance(model,str)
                            and model not in OPTIONS else generate(payload))
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
