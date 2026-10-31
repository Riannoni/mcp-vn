"""Fail-closed, source-only audit of ComfyUI /prompt submission authority.

NO POST, GPU submission, queue mutation, live lock, service restart, or
production wiring. A successful static audit NEVER grants GPU authority.
Localhost binding does not prevent other local processes or container peers
from submitting directly to ComfyUI. GET /queue is not a durable generation
counter, history proof, or atomic compare-and-submit operation.

Minimal safe integration (NOT implemented here):
1. Inventory every active Comfy client, including worker, pose QA, reference
   tools, smoke scripts, external users and container peers. Move every
   submission behind ONE authenticated broker; prevent direct reachability
   using OS/container network isolation, not voluntary client conventions.
2. In that trusted broker, hold one durable lease and a serialized queue
   admission lock; recheck immutable disposable game/scene/source hashes,
   reviewer approval, lease fence and authoritative queue generation under
   the same admission protocol. Atomically record job/prompt ID and recovery
   state, and deny unknown foreign jobs, history gaps or restarts.
3. Deploy only with explicit owner authorization and a predeclared rollback.
   Verify bypass denial from each untrusted client before enabling GPU;
   retain independent audit, source-save hashes and full G2/G3 gates.
Rollback: disable broker admission (fail closed), stop new submissions,
restore prior services/network from backed-up configuration under owner
control; reconcile in-flight prompt IDs and queue history before resuming.
Never roll back by reopening an unfenced direct Comfy POST path.
"""
from __future__ import annotations

import argparse
import ast
import http.client
import json
import pathlib
import re
import subprocess
from collections.abc import Mapping

_SOURCE_SUFFIXES = frozenset({".py", ".js", ".mjs", ".ts", ".sh"})
_EXCLUDE_PARTS = frozenset({
    ".git", "node_modules", "__pycache__", "tests", "docs",
    ".venv", "venv", "dist", "build", "coverage",
})
_MAX_SOURCE_BYTES = 1024 * 1024
_MAX_QUEUE_BYTES = 16 * 1024
_ROUTE = re.compile(r"/prompt(?=$|[/?#\"'\x60\s,)}])")
_LINE_COMMENT = re.compile(r"(?m)^\s*//[^\n]*$")
_SOCKET = re.compile(r"(?<!\d)(?:127\.0\.0\.1|\[::1\]|::1|0\.0\.0\.0|\[::\]|\*|[\d.]+):8188\b")


def _sink(path: str, line: int) -> dict[str, object]:
    return {"path": path, "line": line, "kind": "potential_direct_comfy_prompt"}


def scan_python_source(path: str, source: str) -> list[dict[str, object]]:
    """Conservatively flag executable string literals mentioning /prompt.

    This does not prove absence of dynamically built routes, imports, plugins
    or foreign processes; the final audit remains fail closed regardless.
    """
    tree = ast.parse(source, filename=path)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)) and node.body:
            first = node.body[0]
            if (isinstance(first, ast.Expr) and
                    isinstance(first.value, ast.Constant) and
                    isinstance(first.value.value, str)):
                docstrings.add(id(first.value))
    result = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings and _ROUTE.search(node.value)):
            result.add(node.lineno)
    return [_sink(path, n) for n in sorted(result)]


def scan_text_source(path: str, source: str) -> list[dict[str, object]]:
    """Conservative non-Python scan; only full-line JS comments are ignored."""
    source = _LINE_COMMENT.sub(lambda m: " " * len(m.group(0)), source)
    return [_sink(path, i) for i, line in enumerate(source.splitlines(), 1)
            if _ROUTE.search(line)]


def audit_submission_paths(
    sources: Mapping[str, str],
    *,
    listener: Mapping[str, object],
    queue: Mapping[str, object],
    history_known: bool,
    exclusive_authority: bool,
    broker_enforced: bool,
    coverage_complete: bool,
    foreign_submit: bool | None,
) -> dict[str, object]:
    """Return a DENY-only authority report, including deterministic blockers."""
    blockers = {"source_only_not_live_authority"}
    sinks: list[dict[str, object]] = []
    if not isinstance(sources, Mapping) or not sources:
        blockers.add("source_inventory_incomplete")
    else:
        for path, source in sorted(sources.items()):
            if (not isinstance(path, str) or not path or path.startswith("/")
                    or ".." in pathlib.PurePosixPath(path).parts
                    or pathlib.PurePosixPath(path).suffix not in _SOURCE_SUFFIXES
                    or not isinstance(source, str)):
                blockers.add("source_inventory_incomplete")
                continue
            try:
                if path.endswith(".py"):
                    sinks.extend(scan_python_source(path, source))
                else:
                    sinks.extend(scan_text_source(path, source))
            except (SyntaxError, UnicodeError, ValueError, TypeError):
                blockers.add("source_inventory_incomplete")
    if not coverage_complete:
        blockers.add("source_inventory_incomplete")
    if sinks:
        blockers.add("direct_prompt_route_present")
    if not isinstance(listener, Mapping) or (
            listener.get("observed") is not True or
            listener.get("loopback") is not True):
        blockers.add("listener_untrusted")
    if (not isinstance(queue, Mapping) or queue.get("known") is not True or
            type(queue.get("running")) is not int or
            type(queue.get("pending")) is not int or
            queue.get("running") < 0 or queue.get("pending") < 0):
        blockers.add("queue_unknown")
    elif queue["running"] or queue["pending"]:
        blockers.add("queue_busy")
    if history_known is not True:
        blockers.add("queue_history_unknown")
    if exclusive_authority is not True:
        blockers.add("exclusive_authority_unproven")
    if broker_enforced is not True:
        blockers.add("broker_not_enforced")
    if foreign_submit is True:
        blockers.add("foreign_submit_observed")
    elif foreign_submit is not False:
        blockers.add("foreign_submit_unverifiable")
    return {
        "status": "denied",
        "can_submit_gpu": False,
        "blockers": sorted(blockers),
        "sinks": sorted(sinks, key=lambda item: (item["path"], item["line"])),
        "files_checked": len(sources) if isinstance(sources, Mapping) else 0,
    }


def collect_sources(repo: pathlib.Path, active_worker: pathlib.Path | None = None
                    ) -> tuple[dict[str, str], bool]:
    """Read source only; skip symlinks and fail if any scoped file unreadable."""
    sources = {}
    complete = True
    try:
        for path in sorted(repo.rglob("*")):
            if any(part in _EXCLUDE_PARTS for part in path.relative_to(repo).parts):
                continue
            if path.suffix not in _SOURCE_SUFFIXES:
                continue
            if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_SOURCE_BYTES:
                complete = False
                continue
            try:
                sources[path.relative_to(repo).as_posix()] = path.read_text("utf-8")
            except (OSError, UnicodeError):
                complete = False
        if active_worker is not None:
            if (active_worker.is_symlink() or not active_worker.is_file()
                    or active_worker.stat().st_size > _MAX_SOURCE_BYTES):
                complete = False
            else:
                sources["active/worker.py"] = active_worker.read_text("utf-8")
    except (OSError, UnicodeError):
        complete = False
    return sources, complete


def observe_listener() -> dict[str, bool]:
    """Read-only socket inventory. Loopback alone is NOT exclusive authority."""
    try:
        proc = subprocess.run(["ss", "-ltnp"], check=True, capture_output=True,
                              text=True, timeout=3)
        lines = [line for line in proc.stdout.splitlines() if _SOCKET.search(line)]
        loopback = bool(lines) and all(
            re.search(r"(?:127\.0\.0\.1|\[::1\]|::1):8188\b", line)
            for line in lines
        )
        return {"observed": bool(lines), "loopback": bool(loopback)}
    except (OSError, subprocess.SubprocessError):
        return {"observed": False, "loopback": False}


def observe_queue() -> dict[str, object]:
    """Bounded local GET /queue, no history, no prompt contents in report."""
    connection = http.client.HTTPConnection("127.0.0.1", 8188, timeout=2)
    try:
        connection.request("GET", "/queue", headers={"Accept": "application/json"})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("queue status")
        data = response.read(_MAX_QUEUE_BYTES + 1)
        if len(data) > _MAX_QUEUE_BYTES:
            raise ValueError("queue size")
        obj = json.loads(data)
        if (not isinstance(obj, dict) or
                set(obj) != {"queue_running", "queue_pending"} or
                not all(isinstance(obj[k], list) for k in obj)):
            raise ValueError("queue schema")
        return {"known": True, "running": len(obj["queue_running"]),
                "pending": len(obj["queue_pending"])}
    except (OSError, ValueError, UnicodeError, TypeError):
        return {"known": False, "running": 0, "pending": 0}
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", type=pathlib.Path, required=True)
    parser.add_argument("--active-worker", type=pathlib.Path)
    args = parser.parse_args()
    sources, complete = collect_sources(args.repo_root, args.active_worker)
    listener = observe_listener()
    queue = observe_queue()
    report = audit_submission_paths(
        sources, listener=listener, queue=queue, history_known=False,
        exclusive_authority=False, broker_enforced=False,
        coverage_complete=complete, foreign_submit=None,
    )
    report["listener"] = listener
    report["queue"] = queue
    report["coverage_complete"] = complete
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0  # Read-only diagnostic success, NOT GPU authorization.


if __name__ == "__main__":
    raise SystemExit(main())
