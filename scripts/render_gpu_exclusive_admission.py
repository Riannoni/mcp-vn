"""DENY-only executable Comfy admission preflight (no GPU, POST, or live changes).

A deterministic negative oracle and read-only topology/source inventory, NOT
an admission service. Caller-provided evidence is not an OS attestation.
Even an all-green synthetic snapshot returns candidate_unverified and
can_submit_gpu=False. Production must remain disabled until independent
OS isolation, atomic broker submit and rollback are separately approved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
from collections.abc import Mapping

from scripts.render_gpu_os_isolation_plan import KNOWN_DIRECT_SINKS
from scripts.render_gpu_submission_path_audit import (
    scan_python_source, scan_text_source,
)

KNOWN_SINKS = tuple(sorted(KNOWN_DIRECT_SINKS))
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_FENCE = re.compile(r"[0-9a-f]{32,64}\Z")
_PID = re.compile(r"pid=(\d+)")
_MAX_BYTES = 1024 * 1024


def _sha(value: object) -> bool:
    return isinstance(value, str) and bool(_SHA.fullmatch(value))


def _uid(value: object) -> bool:
    return type(value) is int and value > 0


def _mapping(value: object) -> Mapping:
    return value if isinstance(value, Mapping) else {}


def evaluate_preflight(snapshot: object) -> dict[str, object]:
    """Pure, deterministic negative oracle; never issues live GPU authority."""
    if not isinstance(snapshot, Mapping):
        return {"status": "blocked", "can_submit_gpu": False,
                "blockers": ["invalid_snapshot", "source_only_not_live_authority"]}
    blockers: set[str] = set()
    sources = _mapping(snapshot.get("sources"))
    if set(sources) != set(KNOWN_SINKS):
        blockers.add("sink_inventory_incomplete")
    for path in KNOWN_SINKS:
        item = _mapping(sources.get(path))
        if not _sha(item.get("sha256")):
            blockers.add("sink_digest_missing")
        if item.get("direct_prompt") is not False:
            blockers.add("direct_prompt_bypass")
        if item.get("broker_only") is not True:
            blockers.add("sink_not_broker_only")
        if item.get("os_denied_direct") is not True:
            blockers.add("sink_os_bypass_not_denied")

    t = _mapping(snapshot.get("topology"))
    if (t.get("host_publish") is not False or
            t.get("host_listener") is not False or
            t.get("network_mode") != "private"):
        blockers.add("uncontrolled_host_comfy_listener")
    uids = (t.get("worker_uid"), t.get("comfy_uid"), t.get("broker_uid"))
    if (not all(_uid(x) for x in uids) or len(set(uids)) != 3 or
            t.get("podman_control_separated") is not True):
        blockers.add("os_uid_boundary_missing")
    if (t.get("broker_socket_acl") is not True or
            t.get("container_peer_denied") is not True or
            t.get("foreign_client_denied") is not True):
        blockers.add("uncontrolled_peer_or_broker_socket")

    a = _mapping(snapshot.get("attestation"))
    if (not isinstance(a.get("operator"), str) or not a.get("operator") or
            not isinstance(a.get("reviewer"), str) or not a.get("reviewer") or
            a.get("operator") == a.get("reviewer") or
            not _sha(a.get("evidence_sha256")) or
            any(a.get(key) is not True for key in (
                "host_bypass_denied", "worker_bypass_denied",
                "container_bypass_denied", "foreign_bypass_denied"))):
        blockers.add("independent_bypass_attestation_missing")

    d = _mapping(snapshot.get("admission"))
    if (not isinstance(d.get("owner"), str) or not d.get("owner") or
            not isinstance(d.get("fence"), str) or
            not _FENCE.fullmatch(d["fence"]) or
            d.get("owner") != d.get("current_owner") or
            d.get("fence") != d.get("current_fence")):
        blockers.add("stale_fence_or_owner")
    if (not isinstance(d.get("boot_id"), str) or not d.get("boot_id") or
            d.get("boot_id") != d.get("current_boot_id") or
            d.get("lease_valid") is not True):
        blockers.add("stale_boot_or_lease")
    if (d.get("atomic_fenced_submit") is not True or
            d.get("durable_intent") is not True):
        blockers.add("atomic_durable_admission_missing")
    if (d.get("disposable_save") is not True or
            not _sha(d.get("save_sha")) or
            not _sha(d.get("scene_sha")) or
            d.get("save_sha") != d.get("current_save_sha") or
            d.get("scene_sha") != d.get("current_scene_sha") or
            type(d.get("scene_version")) is not int or
            d.get("scene_version") <= 0 or
            d.get("scene_version") != d.get("current_scene_version")):
        blockers.add("disposable_scene_or_save_changed")
    generation = d.get("queue_generation")
    baseline = d.get("baseline_generation")
    if (type(generation) is not int or type(baseline) is not int or
            generation < 0 or baseline < 0 or generation != baseline):
        blockers.add("queue_aba_or_foreign_generation")
    if (not _sha(d.get("queue_history_sha")) or
            d.get("queue_history_sha") != d.get("baseline_history_sha") or
            d.get("history_complete") is not True):
        blockers.add("queue_history_changed")
    if (d.get("queue_running") != 0 or type(d.get("queue_running")) is not int or
            d.get("queue_pending") != 0 or type(d.get("queue_pending")) is not int or
            d.get("unknown_jobs") is not False or
            d.get("concurrent_game_submit") is not False):
        blockers.add("concurrent_game_or_unknown_job")
    if (d.get("game_protected") is not True or
            d.get("rollback_verified") is not True):
        blockers.add("rollback_or_game_protection_missing")

    return {
        "status": "blocked" if blockers else "candidate_unverified",
        "can_submit_gpu": False,
        "known_sinks": len(KNOWN_SINKS),
        "blockers": sorted(blockers | {"source_only_not_live_authority"}),
        "g2": "UNVERIFIED", "g3": "NO_GO",
    }


def _pid_uid(pid: int) -> int | None:
    """Owner of an observed Linux process, not a claimed container identity."""
    try:
        return os.stat(f"/proc/{pid}").st_uid
    except (OSError, ValueError):
        return None


def _run(argv: list[str]) -> str:
    try:
        result = subprocess.run(argv, capture_output=True, text=True,
                                timeout=4, check=False)
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _read_source(path: pathlib.Path) -> tuple[str | None, str | None]:
    try:
        if (path.is_symlink() or not path.is_file() or
                path.stat().st_size > _MAX_BYTES):
            return None, None
        data = path.read_bytes()
        return data.decode("utf8"), hashlib.sha256(data).hexdigest()
    except (OSError, UnicodeError):
        return None, None


def collect_live_snapshot(repo: pathlib.Path,
                          active_worker: pathlib.Path | None) -> dict[str, object]:
    """Passive source, process, socket and Podman inspection. NO HTTP or POST."""
    sources: dict[str, dict[str, object]] = {}
    for name in KNOWN_SINKS:
        path = active_worker if name == "active/worker.py" else repo / name
        source, digest = _read_source(path) if path is not None else (None, None)
        direct = None
        if source is not None:
            try:
                scan = (scan_python_source if name.endswith(".py")
                        else scan_text_source)
                direct = bool(scan(name, source))
            except (SyntaxError, UnicodeError, ValueError, TypeError):
                direct = None
        sources[name] = {
            "sha256": digest, "direct_prompt": direct,
            # Neither a source scan nor a self-reported migration proves OS ACL.
            "broker_only": False, "os_denied_direct": False,
        }

    lines = _run(["ss", "-H", "-ltnp"]).splitlines()
    listeners = [line for line in lines if
                 re.search(r"(?:127\.0\.0\.1|\[::1\]|::1|0\.0\.0\.0):8188\b", line)]
    # Inspect only three non-secret fields; never print container env or mounts.
    info = _run(["podman", "inspect", "--format",
                 "{{.HostConfig.NetworkMode}}|{{.State.Pid}}|{{.Config.User}}",
                 "mcp-vn-comfy"]).strip().split("|")
    network_mode = info[0] if len(info) == 3 else None
    comfy_pid = int(info[1]) if len(info) == 3 and info[1].isdigit() else 0
    worker_pid_text = _run(["systemctl", "--user", "show", "mcp-vn-worker",
                            "-p", "MainPID", "--value"]).strip()
    worker_pid = int(worker_pid_text) if worker_pid_text.isdigit() else 0
    # A pasta host-loopback listener is a known bypass regardless of /queue.
    return {
        "sources": sources,
        "topology": {
            "network_mode": network_mode,
            "host_publish": bool(listeners) if lines else None,
            "host_listener": bool(listeners) if lines else None,
            "worker_uid": _pid_uid(worker_pid) if worker_pid else None,
            "comfy_uid": _pid_uid(comfy_pid) if comfy_pid else None,
            "broker_uid": None,
            "podman_control_separated": False,
            "broker_socket_acl": False,
            "container_peer_denied": False,
            "foreign_client_denied": False,
        },
        "attestation": {}, "admission": {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=pathlib.Path)
    parser.add_argument("--active-worker", type=pathlib.Path)
    parser.add_argument("--snapshot", type=pathlib.Path,
                        help="untrusted offline fixture; never live authorization")
    args = parser.parse_args()
    if args.snapshot is not None:
        try:
            if args.snapshot.is_symlink() or args.snapshot.stat().st_size > _MAX_BYTES:
                raise ValueError("invalid snapshot")
            snapshot = json.loads(args.snapshot.read_text("utf8"))
        except (OSError, ValueError, UnicodeError):
            snapshot = None
    elif args.repo_root is not None:
        snapshot = collect_live_snapshot(args.repo_root, args.active_worker)
    else:
        parser.error("provide --snapshot or --repo-root")
    result = evaluate_preflight(snapshot)
    if isinstance(snapshot, Mapping) and args.snapshot is None:
        result["live_read_only"] = True
        result["direct_paths"] = sorted(
            path for path, info in _mapping(snapshot.get("sources")).items()
            if _mapping(info).get("direct_prompt") is True
        )
        t = _mapping(snapshot.get("topology"))
        result["observed_topology"] = {
            "network_mode": t.get("network_mode"),
            "host_listener": t.get("host_listener"),
            "worker_uid": t.get("worker_uid"),
            "comfy_uid": t.get("comfy_uid"),
        }
    else:
        result["live_read_only"] = False
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 2 if result["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())


def reversible_isolation_proposal() -> tuple[str, ...]:
    """Owner-approved future procedure only. Calling this changes nothing."""
    return (
        "BACKUP unit, Podman network and ACL configuration; record live queue/history and game hashes",
        "DENY all new GPU admission before changing any service; reconcile unknown in-flight jobs",
        "Provision separate root-managed Comfy, worker and broker UIDs and Podman-control ACL",
        "Remove host-loopback pasta publish; use private namespace with broker-only Comfy socket",
        "Route all six inventoried sinks through authenticated broker; fail closed on dynamic clients",
        "Independently verify host, worker, container-peer and foreign direct /prompt DENIAL",
        "Verify durable fenced lease, queue generation/history, disposable save, concurrent-game isolation",
        "Require Chief approval for ONE bounded disposable job; then independent G2 original-pixel review",
        "ROLLBACK: disable admission first, reconcile jobs, restore backed-up units/ACL under owner control",
        "Never reopen unfenced direct /prompt during rollback; G3 remains NO_GO pending full E2E",
    )
