#!/usr/bin/env python3
"""Resumes a quota-paused web-vn night run after the short window resets.

Idempotent, non-inference, no production touch. Never extends the original deadline.
Run every five minutes via user systemd timer.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path.home() / ".local/share/web-vn-night-runner"
RUNS = ROOT / "runs"
RUNNER = Path.home() / ".local/bin/vn-night"


def load_runner():
    spec = importlib.util.spec_from_loader("night_agent", SourceFileLoader("night_agent", str(RUNNER)))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def can_resume(meta, state, systemd_active, now):
    if not meta or not state or systemd_active:
        return False, "not_idle"
    if now >= meta.get("deadline_epoch", 0):
        return False, "past_deadline"
    if state.get("state") != "paused_quota":
        return False, "not_quota_paused"
    if "5h_or_primary" not in str(state.get("last_outcome", "")):
        return False, "not_short_window"
    return True, "eligible"


def service_active(unit):
    p = subprocess.run(["systemctl", "--user", "is-active", unit], capture_output=True, text=True, timeout=6)
    return p.returncode == 0 and p.stdout.strip() == "active"


def main():
    RUNS.mkdir(exist_ok=True, parents=True, mode=0o700)
    with (RUNS / "resume-exclusive.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        runner = load_runner()
        meta = runner.current()
        if not meta:
            return 0
        path = RUNS / meta["run_id"]
        status = runner.read_json(path / "status.json")
        eligible, why = can_resume(meta, status, service_active(meta.get("unit", "")), time.time())
        if not eligible:
            return 0
        available, quota = runner.quota_check()
        if not available:
            # If the weekly window is still consumed, fail closed and leave unit stopped.
            return 0
        now = time.time()
        remaining = int(meta["deadline_epoch"] - now)
        if remaining <= 30:
            return 0
        timestamp = dt.datetime.now(dt.timezone.utc).strftime("%H%M%S")
        unit = "vn-night-" + meta["run_id"] + "-quota-" + timestamp
        # Preserve previous cycles' private evidence before a same-id restart.
        archive = path / ("paused-before-" + timestamp)
        archive.mkdir(mode=0o700)
        for item in path.glob("codex-*.jsonl"):
            item.rename(archive / item.name)
        for item in path.glob("codex-*.stderr.log"):
            item.rename(archive / item.name)
        # Deliberately keep last-message, hourly.md, events and handoff.
        p = subprocess.run([
            "systemd-run", "--user", "--unit=" + unit,
            "--property=RuntimeMaxSec=" + str(remaining + 180),
            "--property=KillMode=control-group",
            "--property=WorkingDirectory=" + str(runner.WORK),
            sys.executable, str(RUNNER), "_daemon", meta["run_id"],
        ], capture_output=True, text=True, timeout=18)
        if p.returncode:
            runner.event(path, "quota_resume_failed", code=p.returncode)
            return 1
        meta["unit"] = unit
        meta["last_resume_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        meta["last_resume_reason"] = "5h quota reset"
        runner.write_json(path / "meta.json", meta)
        runner.write_json(RUNS / "current.json", meta)
        runner.event(path, "quota_resumed", unit=unit, quota=quota)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        # Avoid logging raw exception bodies that could disclose secret paths/data.
        print("quota resumer failed: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
