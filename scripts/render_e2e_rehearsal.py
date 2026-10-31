"""Disposable offline crash/retry/rollback rehearsal for web-vn publish invariants.

ONLY synthetic bytes in a new TemporaryDirectory whose basename begins
web-vn-e2e-synthetic-. This is NOT a live game publisher, integration test,
GPU runner, G2 visual proof or substitute for an atomic production CAS lock.

The journal models crash windows around asset persistence and canonical save
replacement. Recovery never auto-submits GPU work or auto-publishes a candidate.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import tempfile
from typing import Any


class FenceRejected(RuntimeError):
    """A fail-closed rehearsal guard."""


class CrashInjected(RuntimeError):
    """Controlled process failure in a synthetic fixture."""


_JOB = re.compile(r"[a-zA-Z0-9_-]{1,64}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_MARKER = "web-vn-synthetic-rehearsal-v1"


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class Rehearsal:
    def __init__(self, root: pathlib.Path):
        self.root = pathlib.Path(root)
        if (self.root.is_symlink() or
            not self.root.name.startswith("web-vn-e2e-synthetic-") or
            not self.root.is_dir() or
            not (self.root / ".synthetic-only").is_file() or
            (self.root / ".synthetic-only").read_text() != _MARKER):
            raise FenceRejected("not_a_disposable_synthetic_rehearsal")

    @classmethod
    def create(cls, root: pathlib.Path, *, game_id: str, version: int,
               scene_fingerprint: str, action_id: str,
               accepted_asset: bytes) -> "Rehearsal":
        root = pathlib.Path(root)
        if (root.is_symlink() or
            not root.name.startswith("web-vn-e2e-synthetic-") or
            not root.is_dir() or any(root.iterdir())):
            raise FenceRejected("requires_new_empty_synthetic_directory")
        if (not isinstance(game_id, str) or not game_id or
            not isinstance(action_id, str) or not action_id or
            type(version) is not int or not 0 <= version < 2**53 or
            not isinstance(scene_fingerprint, str) or
            not _HASH.fullmatch(scene_fingerprint) or
            not isinstance(accepted_asset, bytes) or not accepted_asset):
            raise FenceRejected("invalid_synthetic_seed")
        (root / ".synthetic-only").write_text(_MARKER)
        for sub in ("assets", "candidates", "journal"):
            (root / sub).mkdir(mode=0o700)
        store = cls(root)
        store._write_bytes(root / "assets/accepted.bin", accepted_asset)
        store._write_json(root / "save.json", {
            "game_id": game_id, "version": version,
            "scene_fingerprint": scene_fingerprint, "action_id": action_id,
            "published_job_id": "previous", "asset_name": "accepted.bin",
            "asset_sha256": _digest(accepted_asset)})
        return store

    @staticmethod
    def _write_bytes(path: pathlib.Path, data: bytes) -> None:
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            pathlib.Path(tmp).unlink(missing_ok=True)

    @classmethod
    def _write_json(cls, path: pathlib.Path, data: dict[str, Any]) -> None:
        cls._write_bytes(path, (json.dumps(data, sort_keys=True,
                                         separators=(",", ":")) + "\n").encode())

    @staticmethod
    def _read_json(path: pathlib.Path) -> dict[str, Any]:
        try:
            if path.is_symlink():
                raise FenceRejected("symlinked_metadata")
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                raise ValueError("not an object")
            return data
        except (OSError, ValueError) as exc:
            raise FenceRejected("missing_or_corrupt_metadata") from exc

    @staticmethod
    def _job(job_id: str) -> str:
        if not isinstance(job_id, str) or not _JOB.fullmatch(job_id):
            raise FenceRejected("invalid_job_id")
        return job_id

    def state(self) -> dict[str, Any]:
        return self._read_json(self.root / "save.json")

    def _journal(self, job_id: str) -> tuple[pathlib.Path, dict[str, Any]]:
        path = self.root / "journal" / (self._job(job_id) + ".json")
        return path, self._read_json(path)

    def _candidate(self, job_id: str, expected_digest: str) -> bytes:
        path = self.root / "candidates" / (self._job(job_id) + ".bin")
        if path.is_symlink():
            raise FenceRejected("candidate_symlink")
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise FenceRejected("candidate_missing") from exc
        if _digest(data) != expected_digest:
            raise FenceRejected("candidate_digest_changed")
        return data

    def prepare(self, job_id: str, candidate: bytes, *, expected_version: int,
                expected_scene_fingerprint: str, expected_action_id: str) -> None:
        job_id = self._job(job_id)
        if (not isinstance(candidate, bytes) or not 0 < len(candidate) <= 4_000_000 or
            type(expected_version) is not int or
            not 0 <= expected_version < 2**53 or
            not isinstance(expected_scene_fingerprint, str) or
            not _HASH.fullmatch(expected_scene_fingerprint) or
            not isinstance(expected_action_id, str) or not expected_action_id):
            raise FenceRejected("invalid_prepare")
        save = self.state()
        if (save["version"] != expected_version or
            save["scene_fingerprint"] != expected_scene_fingerprint or
            save["action_id"] != expected_action_id):
            raise FenceRejected("stale_at_prepare")
        candidate_path = self.root / "candidates" / (job_id + ".bin")
        journal_path = self.root / "journal" / (job_id + ".json")
        if candidate_path.exists() or journal_path.exists():
            raise FenceRejected("duplicate_job_id")
        # Exclusive create: never replace another candidate's bytes.
        with candidate_path.open("xb") as f:
            f.write(candidate)
            f.flush()
            os.fsync(f.fileno())
        self._write_json(journal_path, {
            "job_id": job_id, "state": "prepared",
            "source_version": expected_version,
            "scene_fingerprint": expected_scene_fingerprint,
            "action_id": expected_action_id,
            "candidate_sha256": _digest(candidate),
            "before": save})

    def _asset_matches(self, name: str, digest: str) -> bool:
        path = self.root / "assets" / name
        return (not path.is_symlink() and path.is_file() and
                _digest(path.read_bytes()) == digest)

    def publish(self, job_id: str, *, qa_accepted: bool,
                crash_at: str | None = None) -> str:
        job_id = self._job(job_id)
        if crash_at not in (None, "after_asset", "after_save"):
            raise FenceRejected("invalid_crash_point")
        journal_path, j = self._journal(job_id)
        save = self.state()
        asset_name = job_id + ".bin"
        if save.get("published_job_id") == job_id:
            if not self._asset_matches(asset_name, j["candidate_sha256"]):
                raise FenceRejected("published_asset_corrupt")
            return "already_applied"
        if j["state"] != "prepared":
            raise FenceRejected("requires_explicit_review")
        if qa_accepted is not True:
            raise FenceRejected("qa_not_accepted")
        if (save["version"] != j["source_version"] or
            save["scene_fingerprint"] != j["scene_fingerprint"] or
            save["action_id"] != j["action_id"] or
            save["game_id"] != j["before"]["game_id"]):
            raise FenceRejected("canonical_state_changed")
        data = self._candidate(job_id, j["candidate_sha256"])
        asset_path = self.root / "assets" / asset_name
        if asset_path.exists() and not self._asset_matches(asset_name, j["candidate_sha256"]):
            raise FenceRejected("asset_collision")
        if not asset_path.exists():
            self._write_bytes(asset_path, data)
        if crash_at == "after_asset":
            raise CrashInjected("after_asset")
        new = dict(save, version=save["version"] + 1,
                   published_job_id=job_id, asset_name=asset_name,
                   asset_sha256=j["candidate_sha256"])
        self._write_json(self.root / "save.json", new)
        if crash_at == "after_save":
            raise CrashInjected("after_save")
        j["state"] = "committed"
        self._write_json(journal_path, j)
        return "applied"

    def recover(self) -> dict[str, str]:
        """No GPU submission or automatic canonical publication on restart."""
        save = self.state()
        result: dict[str, str] = {}
        paths = sorted((self.root / "journal").glob("*.json"))
        journals = [(path, self._read_json(path)) for path in paths]
        # Historical committed assets can be the rollback source of a newer
        # transaction. Never classify them as disposable crash orphans.
        protected = {save.get("asset_name")}
        for _, record in journals:
            before = record.get("before")
            if isinstance(before, dict):
                protected.add(before.get("asset_name"))
        for path, j in journals:
            job_id = self._job(path.stem)
            asset_name = job_id + ".bin"
            if save.get("published_job_id") == job_id:
                if not self._asset_matches(asset_name, j["candidate_sha256"]):
                    raise FenceRejected("published_asset_corrupt")
                j["state"] = "committed"
            elif j["state"] == "committed":
                if not self._asset_matches(asset_name, j["candidate_sha256"]):
                    raise FenceRejected("historical_asset_corrupt")
            elif j["state"] in ("prepared", "needs_review"):
                # A candidate without canonical commit is not auto-published.
                # Delete its orphan only if no later rollback references it.
                orphan = self.root / "assets" / asset_name
                if orphan.is_symlink():
                    raise FenceRejected("orphan_symlink")
                if asset_name not in protected:
                    orphan.unlink(missing_ok=True)
                j["state"] = "needs_review"
            self._write_json(path, j)
            result[job_id] = j["state"]
        return result

    def reauthorize(self, job_id: str, *, approved: bool) -> None:
        path, j = self._journal(job_id)
        if approved is not True or j["state"] != "needs_review":
            raise FenceRejected("explicit_revalidation_required")
        save = self.state()
        if (save["version"] != j["source_version"] or
            save["scene_fingerprint"] != j["scene_fingerprint"] or
            save["action_id"] != j["action_id"]):
            raise FenceRejected("canonical_state_changed")
        self._candidate(job_id, j["candidate_sha256"])
        j["state"] = "prepared"
        self._write_json(path, j)

    def rollback(self, job_id: str) -> str:
        path, j = self._journal(job_id)
        save = self.state()
        if (j["state"] != "committed" or
            save.get("published_job_id") != job_id or
            save["version"] != j["source_version"] + 1 or
            not self._asset_matches(job_id + ".bin", j["candidate_sha256"])):
            raise FenceRejected("rollback_fence_mismatch")
        before = j["before"]
        if not self._asset_matches(before["asset_name"], before["asset_sha256"]):
            raise FenceRejected("rollback_source_corrupt")
        restored = dict(before, version=save["version"] + 1)
        self._write_json(self.root / "save.json", restored)
        j["state"] = "rolled_back"
        self._write_json(path, j)
        return "rolled_back"
