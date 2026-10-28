#!/usr/bin/env python3
"""Private OAuth device-flow runner for CLIProxyAPI (no localhost callback).

Only a logged-in, same-origin VN Web client can trigger these actions.
Never return CLI logs, authorization codes from callback URLs, bearer tokens,
refresh tokens, or proxy configuration to the browser.
"""
from __future__ import annotations

import os
import re
import secrets
import signal
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path

ROOT = Path.home() / ".local/share/mcp-vn-universal-proxy"
BINARY = ROOT / "bin/unpacked/cli-proxy-api"
CONFIG = ROOT / "config.yaml"
FLAGS = {"openai": "-codex-device-login", "grok": "-xai-login"}
LABELS = {"openai": "ChatGPT / Codex", "grok": "Grok / xAI"}
VALID_DOMAINS = ("openai.com", "chatgpt.com", "x.ai", "grok.com")
LOCK = threading.RLock()
CURRENT = None

class OAuthError(Exception):
    pass

def valid_device_url(value: str) -> str:
    """Strict HTTPS allowlist; never return query parameters to the web UI."""
    try:
        u = urllib.parse.urlsplit(value.strip().strip('"\'<>'))
        host = (u.hostname or "").lower().rstrip(".")
        if (u.scheme != "https" or u.username or u.password or
            u.port not in (None, 443) or not any(
                host == domain or host.endswith("." + domain)
                for domain in VALID_DOMAINS
            )):
            return ""
        return urllib.parse.urlunsplit(("https", u.netloc, u.path or "/", "", ""))
    except ValueError:
        return ""

def parse_device_instructions(log: str, provider: str):
    """Extract only a link and a short device code from vendor CLI output."""
    if provider == "openai":
        link = re.search(r"(?im)^\s*Codex device URL:\s*(https://[^\s]+)", log)
        code = re.search(r"(?im)^\s*Codex device code:\s*([A-Za-z0-9-]{4,32})", log)
    else:
        link = re.search(r"(?im)^\s*To authenticate,\s*please visit:\s*\n\s*(https://[^\s]+)", log)
        code = re.search(r"(?im)^\s*Then enter this code:\s*([A-Za-z0-9-]{4,32})", log)
    url = valid_device_url(link.group(1)) if link else ""
    device_code = code.group(1).upper() if code and url else ""
    return url, device_code

def _terminate(job):
    p = job["process"]
    if p.poll() is None:
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try: os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            p.wait(timeout=3)
    job["cancelled"] = True

def _state(job):
    if not job:
        return {
            "provider": None, "active": False, "phase": "idle",
            "url": "", "device_code": "", "message": "Выбери провайдера для входа."
        }
    p = job["process"]
    done = p.poll() is not None
    try:
        # Read local private logs only to find approved device-code fields.
        # No sensitive raw stdout is ever returned to an HTTP client.
        raw = job["log"].read_bytes()[:100_000].decode("utf-8", "replace")
    except (OSError, UnicodeError):
        raw = ""
    url, code = parse_device_instructions(raw, job["provider"])
    if job.get("cancelled"):
        phase, message = "cancelled", "Предыдущий вход отменён."
    elif not done and url and code:
        phase, message = "waiting", "Открой страницу входа и введи код. Подтверждение будет обнаружено автоматически."
    elif not done:
        phase, message = "starting", "Подготавливается вход через код устройства…"
    elif p.returncode == 0:
        phase, message = "success", "Вход завершён. Проверяем, какие модели разрешены аккаунту."
    elif re.search(r"(?i)(timed out|timeout|expired)", raw):
        phase, message = "expired", "Время подтверждения истекло. Нажми «Войти» ещё раз."
    elif re.search(r"(?i)(not enabled|not allowed|forbidden|permission|denied|unsupported)", raw):
        phase, message = "unavailable", "Этот способ входа недоступен для аккаунта или провайдера."
    else:
        phase, message = "error", "Вход не завершился. Проверь авторизацию и попробуй снова."
    return {
        "provider": job["provider"], "label": LABELS[job["provider"]],
        "active": not done, "phase": phase,
        "url": url if not done else "",
        "device_code": code if not done else "",
        "message": message, "started_at": job["started_at"],
    }

def start_login(provider: str):
    global CURRENT
    if provider not in FLAGS:
        raise OAuthError("Неизвестный провайдер")
    with LOCK:
        if CURRENT and CURRENT["process"].poll() is None:
            if CURRENT["provider"] == provider:
                return _state(CURRENT)
            _terminate(CURRENT)
        if not BINARY.is_file() or not CONFIG.is_file():
            raise OAuthError("Прокси не установлен или не настроен")
        session_id = secrets.token_hex(8)
        log = ROOT / ("oauth-device-" + provider + "-" + session_id + ".log")
        # Both config and log reside in a private 0700 directory.
        fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as output:
                process = subprocess.Popen(
                    [str(BINARY), "-config", str(CONFIG), FLAGS[provider], "-no-browser"],
                    stdin=subprocess.DEVNULL,
                    stdout=output, stderr=subprocess.STDOUT,
                    cwd=ROOT, start_new_session=True,
                    close_fds=True,
                )
        except Exception as e:
            log.unlink(missing_ok=True)
            raise OAuthError("Не удалось запустить вход: " + type(e).__name__) from None
        CURRENT = {
            "provider": provider, "process": process, "log": log,
            "started_at": int(time.time()), "cancelled": False,
        }
        # Old device-code logs are not reusable; clear stale files.
        for old in ROOT.glob("oauth-device-*.log"):
            if old != log:
                try: old.unlink()
                except OSError: pass
        return _state(CURRENT)

def login_status():
    with LOCK:
        return _state(CURRENT)

def cancel_login():
    with LOCK:
        if CURRENT and CURRENT["process"].poll() is None:
            _terminate(CURRENT)
        return _state(CURRENT)
