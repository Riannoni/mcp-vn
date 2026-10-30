#!/usr/bin/env python3
"""Bounded offline health/recovery for web-vn night agent.

Does not touch production, git state, model configuration or GPU. Never repairs
unknown causes; resumes an unexpectedly dead supervisor only with evidence.
"""
import datetime as dt
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path.home() / ".local/share/web-vn-night-runner"
RUNS = ROOT / "runs"
RUNNER = Path.home() / ".local/bin/vn-night"
RESTART_BUDGET = 2
MIN_SECONDS_BETWEEN_RESTARTS = 900
HEARTBEAT_STALE_SECONDS = 300


def load(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    tmp.chmod(0o600)
    tmp.replace(path)


def active(unit):
    try:
        p = subprocess.run(["systemctl", "--user", "is-active", unit],
                           capture_output=True, text=True, timeout=5)
        return p.returncode == 0 and p.stdout.strip() == "active"
    except (OSError, subprocess.TimeoutExpired):
        return False


def heartbeat_age(st, now):
    try:
        return now - dt.datetime.fromisoformat(st["updated_at"]).timestamp()
    except (KeyError, TypeError, ValueError):
        return float("inf")


def classify(meta, st, is_active, now, recovery):
    if not meta or not st:
        return "no_state"
    if now >= meta.get("deadline_epoch", 0):
        return "finished"
    state = st.get("state")
    if is_active:
        return "stale_running" if heartbeat_age(st, now) > HEARTBEAT_STALE_SECONDS else "healthy"
    if state in ("completed_time_limit", "blocked_human_gate",
                 "blocked_mission_controller", "stopped", "paused_quota"):
        return "not_recoverable"
    if state == "blocked_repeated_error":
        return "needs_diagnosis"
    if state not in ("starting", "working", "ended_unexpectedly", "failed"):
        return "needs_diagnosis"
    if recovery.get("restart_count", 0) >= RESTART_BUDGET:
        return "restart_budget_exhausted"
    if now - recovery.get("last_restart_epoch", 0) < MIN_SECONDS_BETWEEN_RESTARTS:
        return "restart_cooldown"
    return "safe_to_restart"


def main():
    RUNS.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_path = RUNS / "resume-exclusive.lock"  # same lock as quota resumer
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        meta = load(RUNS / "current.json")
        if not meta:
            return 0
        run_dir = RUNS / meta["run_id"]
        status = load(run_dir / "status.json")
        recovery_path = run_dir / "recovery-state.json"
        recovery = load(recovery_path)
        now = time.time()
        diagnosis = classify(meta, status, active(meta.get("unit", "")), now, recovery)
        if diagnosis in ("healthy", "finished", "not_recoverable", "no_state"):
            return 0
        previous = recovery.get("diagnosis")
        recovery["diagnosis"] = diagnosis
        recovery["last_check_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        if diagnosis != "safe_to_restart":
            save(recovery_path, recovery)
            if diagnosis != previous:
                print("web-vn night watchdog:", diagnosis)
            return 0
        # Only restart with genuine evidence of a dead unit and a fresh quota check.
        if active(meta.get("unit", "")) or now >= meta["deadline_epoch"]:
            return 0
        quota = subprocess.run([str(Path.home() / ".local/bin/vn-proxy-quota"),
                                "--provider", "codex", "--json"], capture_output=True,
                               text=True, timeout=30)
        if quota.returncode:
            recovery["diagnosis"] = "quota_unavailable"
            save(recovery_path, recovery)
            return 0
        try:
            accounts = json.loads(quota.stdout)["accounts"]
            codex = next(a for a in accounts if a.get("provider") == "codex" and a.get("status") == "ok")
            if codex.get("allowed") is False or codex.get("limit_reached") is True:
                return 0
            if any((codex["windows"][k]["used_percent"] is None or
                    codex["windows"][k]["used_percent"] >= 85)
                   for k in ("5h_or_primary", "7d_or_secondary")):
                return 0
        except (ValueError, KeyError, StopIteration, TypeError):
            return 0
        count = recovery.get("restart_count", 0) + 1
        unit = "vn-night-" + meta["run_id"] + "-recover-" + str(count)
        remain = int(meta["deadline_epoch"] - now)
        if remain < 60:
            return 0
        # Keep evidence logs of the former run; do not reset source changes.
        archived = run_dir / ("watchdog-pre-restart-" + str(count))
        archived.mkdir(mode=0o700, exist_ok=True)
        for pattern in ("codex-*.jsonl", "codex-*.stderr.log"):
            for file in run_dir.glob(pattern):
                file.replace(archived / file.name)
        p = subprocess.run([
            "systemd-run", "--user", "--unit=" + unit,
            "--property=RuntimeMaxSec=" + str(remain + 180),
            "--property=KillMode=control-group",
            "--property=WorkingDirectory=" + str(ROOT / "work/web-vn"),
            sys.executable, str(RUNNER), "_daemon", meta["run_id"]
        ], capture_output=True, text=True, timeout=20)
        if p.returncode:
            recovery["diagnosis"] = "systemd_run_failed"
            save(recovery_path, recovery)
            return 1
        meta["unit"] = unit
        meta["last_watchdog_recovery_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        save(RUNS / "current.json", meta)
        save(run_dir / "meta.json", meta)
        recovery.update({
            "restart_count": count,
            "last_restart_epoch": now,
            "diagnosis": "recovered",
        })
        save(recovery_path, recovery)
        print("web-vn night watchdog: restarted", unit, "before original deadline")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print("web-vn night watchdog error: " + type(error).__name__, file=sys.stderr)
        sys.exit(1)
