"""Conservative, source-only ABA/version fence for prospective image publication.

This module is NOT connected to the live renderer and never authorizes a publish.
A successful result means only that the metadata matches at the instant of the
read; the actual publisher must re-check within its canonical transaction,
perform independent scene QA and enforce the current scene fingerprint.

Motivation: src/art-spec.mjs/currentSceneMatches compares visual intent, not
the monotonically increasing game version. A return to identical visual intent
after an intervening narrative action (ABA) can therefore match an old request.
This *shadow* policy rejects that class by binding job, attempt, game version,
action and scene provenance. It is intentionally stricter than live behavior:
even an unrelated game-version increment rejects; calibrate before integration.

Inputs must come from trusted server-side job metadata and canonical game
state, not from a browser-supplied candidate or an unverified image caption.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_TEXT = re.compile(r"[^\x00-\x1f\x7f]{1,128}\Z")
_EXPECTED = ("game_id", "game_version", "scene_key", "scene_fingerprint",
             "action_id", "job_id", "attempt")
_CURRENT = ("game_id", "game_version", "scene_key", "scene_fingerprint",
            "action_id")
_CANDIDATE = ("game_id", "source_game_version", "scene_key",
              "scene_fingerprint", "action_id", "job_id", "attempt",
              "status", "superseded_by")


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(_TEXT.fullmatch(value)) and bool(value.strip())


def _valid_version(value: object, *, positive: bool = False) -> bool:
    # JavaScript canonical game versions are Number safe integers.
    return type(value) is int and (1 if positive else 0) <= value <= (2**53 - 1)


def _valid(payload: object, fields: tuple[str, ...]) -> bool:
    if not isinstance(payload, Mapping) or any(key not in payload for key in fields):
        return False
    for key in fields:
        value = payload[key]
        if key in ("game_version", "source_game_version"):
            if not _valid_version(value):
                return False
        elif key == "attempt":
            if not _valid_version(value, positive=True):
                return False
        elif key == "scene_fingerprint":
            if not isinstance(value, str) or not _DIGEST.fullmatch(value):
                return False
        elif key == "superseded_by":
            if value is not None and not _valid_text(value):
                return False
        elif not _valid_text(value):
            return False
    return True


def _decision(reason: str) -> dict[str, object]:
    return {"status": "shadow_match" if reason == "metadata_matches" else "rejected",
            "reason": reason, "can_publish": False}


def evaluate_fence(expected: object, current: object,
                   candidate: object) -> dict[str, object]:
    """Fail closed on missing/changed provenance; never grant publish rights.

    expected: immutable server-side enqueue snapshot.
    current: canonical state freshly read immediately before publication.
    candidate: trusted job record for the exact completed generation attempt.

    The caller must additionally enforce atomic compare-and-swap and visual
    acceptance. Even shadow_match is NOT an approval of G2 or G3.
    """
    if not _valid(expected, _EXPECTED):
        return _decision("invalid_expected")
    if not _valid(current, _CURRENT):
        return _decision("invalid_current")
    if not _valid(candidate, _CANDIDATE):
        return _decision("invalid_candidate")

    if current["game_id"] != expected["game_id"]:
        return _decision("game_mismatch")
    if candidate["game_id"] != expected["game_id"]:
        return _decision("candidate_provenance_mismatch")
    if current["game_version"] != expected["game_version"]:
        return _decision("version_changed")
    if current["scene_key"] != expected["scene_key"]:
        return _decision("scene_changed")
    if current["scene_fingerprint"] != expected["scene_fingerprint"]:
        return _decision("scene_fingerprint_changed")
    if current["action_id"] != expected["action_id"]:
        return _decision("action_changed")

    for current_key, expected_key in (
        ("source_game_version", "game_version"),
        ("scene_key", "scene_key"),
        ("scene_fingerprint", "scene_fingerprint"),
        ("action_id", "action_id"),
    ):
        if candidate[current_key] != expected[expected_key]:
            return _decision("candidate_provenance_mismatch")
    if candidate["job_id"] != expected["job_id"]:
        return _decision("job_mismatch")
    if candidate["attempt"] != expected["attempt"]:
        return _decision("attempt_mismatch")
    if candidate["superseded_by"] is not None:
        return _decision("candidate_superseded")
    if candidate["status"] != "done":
        return _decision("candidate_not_done")
    return _decision("metadata_matches")
