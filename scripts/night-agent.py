#!/usr/bin/env python3
"""Bounded unattended source-development runner for Riannoni/web-vn.

All paths are under ~/.local/share/web-vn-night-runner, except installed CLI.
Never changes production services, games, image assets or existing worktrees.
"""
import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path.home() / ".local/share/web-vn-night-runner"
RUNS = ROOT / "runs"
WORK = ROOT / "work/web-vn"
CODEX = ROOT / "bin/proxy-codex"
QUOTA = Path.home() / ".local/bin/vn-proxy-quota"
UNIT_PREFIX = "vn-night-"
MODEL_DEFAULT = "gpt-6-astra"
STOP = False

DEFAULT_TASK = (
    "web-vn render-v1 P0 source-only: read current AGENTS.md, "
    "docs/DEVELOPMENT-AND-TESTING.md and newest docs/RENDER-HANDOFF-2026-10-31.md, "
    "docs/ROADMAP.md and issue #20. Prioritize the current #49 atomic required-prop / "
    "actor-contact evidence integration as a non-publishing read-only SHADOW validator, "
    "plus tests on neutral fixtures. Distinguish required object evidence from "
    "unobservable, and retain fail-closed behavior. No production, no game saves, "
    "no GPU queue, no model downloads. If this is blocked, investigate the next "
    "P0 source-level issue and document evidence rather than guessing."
)

def utcnow():
    return dt.datetime.now(dt.timezone.utc)

def stamp():
    return utcnow().isoformat(timespec="seconds")

def write_json(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)

def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

def command(args, timeout=15, cwd=None):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, cwd=cwd)

def current():
    return read_json(RUNS / "current.json")

def quota_check():
    try:
        p = command([str(QUOTA), "--provider", "codex", "--json"], timeout=35)
        if p.returncode:
            return False, {"status": "unavailable", "reason": "quota command returned error"}
        d = json.loads(p.stdout)
        rows = [x for x in d.get("accounts", []) if x.get("provider") == "codex"]
        if not rows or any(x.get("status") != "ok" for x in rows):
            return False, {"status": "unavailable", "reason": "no verified Codex quota"}
        for item in rows:
            if item.get("allowed") is False or item.get("limit_reached") is True:
                return False, {"status": "exhausted", "reason": "provider marked limit reached"}
            windows = item.get("windows", {})
            for name, threshold in (("5h_or_primary", 85), ("7d_or_secondary", 85)):
                w = windows.get(name, {})
                used = w.get("used_percent")
                if not isinstance(used, (int, float)):
                    return False, {"status": "unavailable", "reason": "missing " + name}
                if used >= threshold:
                    return False, {"status": "guarded", "reason": name + " used >= " + str(threshold) + "%"}
        return True, {
            "status": "ok",
            "primary_used_percent": rows[0]["windows"]["5h_or_primary"]["used_percent"],
            "weekly_used_percent": rows[0]["windows"]["7d_or_secondary"]["used_percent"],
        }
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False, {"status": "unavailable", "reason": "quota collection failed"}

def tool_event_verdict(jsonl_path):
    """Treat a tool-less/failed code-mode run as failure even if Codex exits 0."""
    try:
        completed_commands = 0
        fatal_errors = []
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            try:
                event_data = json.loads(line)
            except ValueError:
                continue
            typ = event_data.get("type")
            item = event_data.get("item") or {}
            if typ == "item.completed" and item.get("type") == "command_execution":
                completed_commands += 1
            message = str(item.get("message") or event_data.get("message") or "")
            if typ == "turn.failed" or (
                typ in ("error", "item.completed") and
                ("Code Mode is unavailable" in message or
                 "unexpected status 413" in message or
                 "request body too large" in message)
            ):
                fatal_errors.append(message[:120])
        if fatal_errors:
            return "tool_failure"
        if completed_commands == 0:
            return "no_tool_execution"
        return "ok"
    except OSError:
        return "tool_events_missing"


def git_snapshot():
    try:
        h = command(["git", "rev-parse", "--short=12", "HEAD"], cwd=WORK)
        p = command(["git", "status", "--porcelain=v1"], cwd=WORK)
        return {"head": h.stdout.strip(), "changed_files": len(p.stdout.splitlines())}
    except (OSError, subprocess.TimeoutExpired):
        return {"head": "unknown", "changed_files": None}

def unit_state(unit):
    try:
        p = command(["systemctl", "--user", "is-active", unit], timeout=5)
        return p.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"

def event(run_dir, message, **info):
    with (run_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": stamp(), "event": message, **info}, ensure_ascii=False) + "\n")
        f.flush()

def latest_agent_message(run_dir):
    p = run_dir / "last-message.txt"
    try:
        return p.read_text(encoding="utf-8")[-1200:].strip() or "No completed agent message"
    except OSError:
        return "No completed agent message"

def report(run_dir, status, hourly=False):
    status["updated_at"] = stamp()
    status["git"] = git_snapshot()
    status["agent_summary"] = latest_agent_message(run_dir)
    write_json(run_dir / "status.json", status)
    if hourly:
        status["hourly_reports"] = status.get("hourly_reports", 0) + 1
        write_json(run_dir / "status.json", status)
        lines = [
            "# web-vn night agent | " + stamp(),
            "- Run ID: " + status["run_id"],
            "- State: " + status["state"],
            "- Model: " + status["model"],
            "- Elapsed hours: " + str(round(status.get("elapsed_hours", 0), 2)),
            "- Deadline: " + status["deadline"],
            "- Iteration: " + str(status.get("iteration", 0)),
            "- Mission: " + json.dumps(status.get("mission"), ensure_ascii=False),
            "- Codex quota: " + json.dumps(status.get("quota", {}), ensure_ascii=False),
            "- Git: " + json.dumps(status["git"], ensure_ascii=False),
            "- Last outcome: " + str(status.get("last_outcome", "pending")),
            "- Evidence note: " + status["agent_summary"],
            "- Safety: production writes, merges, pushes and unsupervised GPU work forbidden.",
        ]
        text = "\n".join(lines) + "\n"
        (run_dir / "latest-hourly.md").write_text(text, encoding="utf-8")
        with (run_dir / "hourly.md").open("a", encoding="utf-8") as f:
            f.write("\n---\n" + text)
        event(run_dir, "hourly_report", sequence=status["hourly_reports"])

def on_signal(_sig, _frame):
    global STOP
    STOP = True

def daemon(run_id):
    global STOP
    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    run_dir = RUNS / run_id
    meta = read_json(run_dir / "meta.json")
    if not meta:
        raise RuntimeError("run metadata missing")
    with (RUNS / "exclusive.lock").open("a+") as lk:
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            event(run_dir, "blocked_by_other_run")
            return 20

        deadline_ts = float(meta["deadline_epoch"])
        started_ts = float(meta["start_epoch"])
        model = meta["model"]
        task = (run_dir / "task.txt").read_text(encoding="utf-8")
        status = {
            "run_id": run_id, "model": model, "state": "starting",
            "started_at": meta["started_at"], "deadline": meta["deadline"],
            "iteration": 0, "hourly_reports": 0, "quota": {},
            "last_outcome": "starting",
        }
        last_hour = 0
        failure_streak = 0
        try:
            while not STOP and time.time() < deadline_ts:
                now = time.time()
                status["elapsed_hours"] = round((now - started_ts) / 3600, 3)
                hour = int((now - started_ts) // 3600)
                if hour > last_hour:
                    report(run_dir, status, hourly=True)
                    last_hour = hour
                allowed, quota = quota_check()
                status["quota"] = quota
                if not allowed:
                    status["state"] = "paused_quota"
                    status["last_outcome"] = quota.get("reason", "quota unavailable")
                    report(run_dir, status)
                    event(run_dir, "quota_guard", detail=quota)
                    if quota.get("status") in ("exhausted", "guarded"):
                        break
                    # A transient missing quota should not be treated as 100% available.
                    if failure_streak >= 2:
                        break
                    failure_streak += 1
                    for _ in range(20):
                        if STOP or time.time() >= deadline_ts:
                            break
                        time.sleep(15)
                    continue
                # Select the next render-v1 task from a bounded, evidence-gated mission.
                mission_script = ROOT / "bin/night-mission.py"
                try:
                    mission_output = command([sys.executable, str(mission_script),
                                              "next", str(run_dir)], timeout=10)
                    mission = json.loads(mission_output.stdout) if mission_output.returncode == 0 else {}
                except (OSError, ValueError, subprocess.TimeoutExpired):
                    mission = {}
                if mission.get("status") == "requires_human":
                    status["state"] = "blocked_human_gate"
                    status["last_outcome"] = mission.get("reason", "source stages exhausted")
                    report(run_dir, status, hourly=True)
                    event(run_dir, "mission_requires_human")
                    break
                if mission.get("status") != "ready":
                    status["state"] = "blocked_mission_controller"
                    status["last_outcome"] = "Mission controller unavailable"
                    report(run_dir, status, hourly=True)
                    event(run_dir, "mission_controller_error")
                    break
                status["mission"] = {k: mission.get(k) for k in ("stage_id", "issue", "attempt", "history_size")}
                status["iteration"] += 1
                iteration = status["iteration"]
                status["state"] = "working"
                status["last_outcome"] = "iteration " + str(iteration) + " started"
                report(run_dir, status)
                event(run_dir, "iteration_started", iteration=iteration)
                prompt = (
                    "You are a supervised-quality but UNATTENDED night coding agent for web-vn. "
                    "First read the ROOT AGENTS.md completely and docs/DEVELOPMENT-AND-TESTING.md, "
                    "then the latest handoff, roadmap, and exact implicated source files. "
                    "You work ONLY inside this isolated git checkout, on a local night branch. "
                    "DO NOT access/modify production game services, saves, private photos, OAuth credentials, "
                    "the PC ComfyUI API or GPU queue, home server, systemd, network admin or other worktrees. "
                    "Do not run destructive commands, install models, use git push, merge, or force push. "
                    "Investigate one root cause at a time; add negative regression tests first, "
                    "implement a bounded source-only improvement, run relevant local tests, "
                    "and review diff. No invented visual acceptance. "
                    "If an actual PNG is not independently reviewed, state G2 UNVERIFIED. "
                    "After 2 failed attempts, stop that hypothesis. "
                    "Use only neutral synthetic fixtures; never print secrets or private prompts. "
                    "Read and update NIGHT_HANDOFF.md in this checkout with: hypothesis, evidence, "
                    "tests, files, remaining failures and ONE next step. Do NOT attempt git commit: "
                    "the sandbox makes .git read-only. Leave verified source files and handoff "
                    "in the isolated worktree for independent post-run review and local commit. "
                    "Do not ask questions; when blocked, document blockers and choose another "
                    "safe read-only/source-only improvement.\n"
                    "NIGHT GOAL: " + task + "\n"
                    "CURRENT AUTONOMOUS MISSION: " + mission["instruction"] + "\n"
                    "REFERENCE: PR #49 fetched read-only as refs/remotes/origin/pr-49. "
                    "Use git show for reference, never merge or replace uncommitted files.\n"
                    "ITERATION: " + str(iteration) + ". Limit scope to one focused improvement.\n"
                )
                last_path = run_dir / "last-message.txt"
                jsonl = run_dir / ("codex-" + f"{iteration:02d}" + ".jsonl")
                stderr_path = run_dir / ("codex-" + f"{iteration:02d}" + ".stderr.log")
                cmd = [
                    str(CODEX), "exec", "-C", str(WORK), "--sandbox", "workspace-write",
                    "--json", "--output-last-message", str(last_path),
                    "-m", model, "-",
                ]
                proc = None
                outcome = "not_started"
                max_iter_sec = min(45 * 60, max(60, int(deadline_ts - time.time())))
                with jsonl.open("w", encoding="utf-8") as out, stderr_path.open("w", encoding="utf-8") as err:
                    proc = subprocess.Popen(cmd, cwd=WORK, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                            start_new_session=True, text=True)
                    proc.stdin.write(prompt)
                    proc.stdin.close()
                    iter_start = time.monotonic()
                    while proc.poll() is None:
                        if STOP or time.time() >= deadline_ts or time.monotonic() - iter_start >= max_iter_sec:
                            os.killpg(proc.pid, signal.SIGTERM)
                            try:
                                proc.wait(timeout=12)
                            except subprocess.TimeoutExpired:
                                os.killpg(proc.pid, signal.SIGKILL)
                                proc.wait()
                            outcome = "stopped_or_timeout"
                            break
                        # Independent heartbeat even during a long model call.
                        status["elapsed_hours"] = round((time.time() - started_ts) / 3600, 3)
                        hour = int((time.time() - started_ts) // 3600)
                        if hour > last_hour:
                            report(run_dir, status, hourly=True)
                            last_hour = hour
                        else:
                            report(run_dir, status)
                        time.sleep(15)
                    if outcome == "not_started":
                        outcome = (tool_event_verdict(jsonl) if proc.returncode == 0
                                   else "codex_error_" + str(proc.returncode))
                status["last_outcome"] = outcome
                event(run_dir, "iteration_completed", iteration=iteration, outcome=outcome)
                report(run_dir, status)
                if outcome != "ok":
                    failure_streak += 1
                    if failure_streak >= 2:
                        status["state"] = "blocked_repeated_error"
                        break
                    time.sleep(15)
                else:
                    failure_streak = 0
                    # Control cadence and allow other agents' source changes to remain isolated.
                    time.sleep(10)
            if status["state"] not in ("paused_quota", "blocked_repeated_error",
                                     "blocked_mission_controller", "blocked_human_gate"):
                status["state"] = "stopped" if STOP else "completed_time_limit"
            status["elapsed_hours"] = round((time.time() - started_ts) / 3600, 3)
            report(run_dir, status, hourly=True)
            event(run_dir, "finished", state=status["state"])
            return 0
        except Exception as exc:
            status["state"] = "failed"
            status["last_outcome"] = type(exc).__name__
            report(run_dir, status, hourly=True)
            event(run_dir, "failed", error_type=type(exc).__name__)
            return 1

def start(hours, model, task):
    if not 0.1 <= hours <= 72:
        raise ValueError("hours must be between 0.1 and 72")
    if model not in ("gpt-6-astra", "gpt-6.1-sol", "gpt-6.1-terra"):
        raise ValueError("model is not an allowed explicit provider")
    RUNS.mkdir(parents=True, exist_ok=True, mode=0o700)
    old = current()
    if old and unit_state(old.get("unit", "")) == "active":
        print("Already running:", old.get("run_id"))
        return 2
    if not WORK.joinpath("AGENTS.md").exists():
        raise RuntimeError("isolated project checkout missing AGENTS.md")
    if not CODEX.exists():
        raise RuntimeError("Codex launcher missing")
    allowed, quota = quota_check()
    if not allowed:
        print("Cannot start; quota guard:", quota)
        return 3
    when = time.time()
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir(mode=0o700)
    deadline = when + 3600 * hours
    unit = UNIT_PREFIX + run_id
    metadata = {
        "run_id": run_id, "unit": unit, "model": model, "hours": hours,
        "started_at": dt.datetime.fromtimestamp(when, dt.timezone.utc).isoformat(),
        "deadline": dt.datetime.fromtimestamp(deadline, dt.timezone.utc).isoformat(),
        "start_epoch": when, "deadline_epoch": deadline,
        "quota_start": quota, "isolated_workspace": str(WORK),
    }
    write_json(run_dir / "meta.json", metadata)
    (run_dir / "task.txt").write_text(task, encoding="utf-8")
    os.chmod(run_dir / "task.txt", 0o600)
    r = command([
        "systemd-run", "--user", "--unit=" + unit,
        "--property=RuntimeMaxSec=" + str(int(3600 * hours) + 180),
        "--property=KillMode=control-group", "--property=WorkingDirectory=" + str(WORK),
        sys.executable, str(Path(__file__).resolve()), "_daemon", run_id
    ], timeout=20)
    if r.returncode:
        print("Unable to start systemd unit:", r.stderr[:300], file=sys.stderr)
        return 4
    write_json(RUNS / "current.json", metadata)
    print("Started", run_id, "model", model, "hours", hours, "unit", unit)
    print("Deadline", metadata["deadline"], "(UTC)")
    return 0

def status(json_output=False):
    meta = current()
    if not meta:
        print("No night agent has been started")
        return 1
    state = read_json(RUNS / meta["run_id"] / "status.json")
    unit = unit_state(meta["unit"])
    state.update({
        "unit_state": unit,
        "run_id": meta["run_id"], "deadline": meta["deadline"],
        "model": meta["model"], "hours": meta["hours"],
    })
    update = state.get("updated_at")
    if unit != "active" and state.get("state") in ("starting", "working"):
        state["state"] = "ended_unexpectedly"
    elif unit == "active" and update:
        try:
            age = (utcnow() - dt.datetime.fromisoformat(update)).total_seconds()
            if age > 180:
                state["state"] = "stale_heartbeat"
        except ValueError:
            pass
    if json_output:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print("Night run", meta["run_id"], "state", state.get("state", "starting"), "unit", unit)
        print("Model", meta["model"], "deadline", meta["deadline"])
        print("Iteration", state.get("iteration"), "quota", state.get("quota"))
        print("Git", state.get("git"))
        print("Last", state.get("last_outcome"), "updated", state.get("updated_at"))
        print("Summary:", str(state.get("agent_summary", ""))[:650])
        print("Hourly report:", RUNS / meta["run_id"] / "latest-hourly.md")
    return 0

def stop():
    meta = current()
    if not meta:
        print("No run")
        return 1
    p = command(["systemctl", "--user", "stop", meta["unit"]], timeout=20)
    print("Stopping", meta["run_id"], "return", p.returncode)
    return p.returncode

def main():
    parser = argparse.ArgumentParser(description="Bounded web-vn night AI agent, ChatGPT OAuth through local proxy")
    sub = parser.add_subparsers(dest="action", required=True)
    st = sub.add_parser("start")
    st.add_argument("--hours", type=float, required=True)
    st.add_argument("--model", default=MODEL_DEFAULT)
    st.add_argument("--task", default=DEFAULT_TASK)
    ss = sub.add_parser("status")
    ss.add_argument("--json", action="store_true")
    sub.add_parser("stop")
    sd = sub.add_parser("_daemon")
    sd.add_argument("run_id")
    args = parser.parse_args()
    if args.action == "start":
        return start(args.hours, args.model, args.task)
    if args.action == "status":
        return status(args.json)
    if args.action == "stop":
        return stop()
    if args.action == "_daemon":
        return daemon(args.run_id)
    return 2

if __name__ == "__main__":
    sys.exit(main())
