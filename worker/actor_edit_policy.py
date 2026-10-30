"""Fail-closed source-anatomy lock policy for a stationary upper-body CG edit.

This is an isolated preflight guard, not a contact, identity or outfit verifier.
Do not use it for walking or any action changing feet/leg poses.
"""
from __future__ import annotations

from math import isfinite

from PIL import Image


class ActorEditPolicyError(ValueError):
    pass


def stationary_upper_body_lock(frame, principal_index, keypoint_format="openpose18"):
    """Calculate a *source-pose-derived* lower-leg lock boundary in pixels.

    All image pixels from that boundary to the bottom must stay immutable.
    Requires observed bilateral knee and ankle joints; no fallback guessed ROI.
    """
    if keypoint_format != "openpose18":
        raise ActorEditPolicyError("unsupported_body_keypoint_format")
    if not isinstance(frame, dict) or isinstance(principal_index, bool) or not isinstance(principal_index, int):
        raise ActorEditPolicyError("missing_attributed_source_pose")
    try:
        width, height = frame["canvas_width"], frame["canvas_height"]
        people = frame["people"]
        if not isinstance(width, int) or not isinstance(height, int) or min(width, height) < 128:
            raise ValueError("invalid canvas")
        if not 0 <= principal_index < len(people):
            raise ValueError("principal out of range")
        pose = people[principal_index]["pose_keypoints_2d"]
        if not isinstance(pose, (tuple, list)) or len(pose) != 54:
            raise ValueError("wrong body joint layout")
        # OpenPose18 0-indexed: right knee/ankle (9,10), left knee/ankle (12,13).
        joints = []
        for joint in (9, 10, 12, 13):
            x, y, conf = map(float, pose[joint * 3:joint * 3 + 3])
            if not all(isfinite(v) for v in (x, y, conf)) or conf < 0.55:
                raise ValueError("unobserved knee or ankle")
            if not 0 <= x < width or not 0 <= y < height:
                raise ValueError("joint out of canvas")
            joints.append((x, y))
        right_knee, right_ankle, left_knee, left_ankle = joints
        spans = (right_ankle[1] - right_knee[1], left_ankle[1] - left_knee[1])
        if min(spans) < height * 0.07:
            raise ValueError("leg pose not confidently standing")
        if abs(right_knee[1] - left_knee[1]) > height * 0.17:
            raise ValueError("asymmetric leg pose unsupported")
        # A pose-derived upper-shin boundary leaves knees editable for action
        # blending, but freezes the remaining shins/boots. No fixed y=420.
        lock_from_y = max(0, int(min(right_knee[1], left_knee[1]) + .2 * min(spans)))
        if not height * .25 <= lock_from_y <= height * .85:
            raise ValueError("lower-body boundary improbable")
    except (KeyError, ValueError, TypeError, IndexError, OverflowError) as error:
        raise ActorEditPolicyError("lower_leg_landmarks_unobservable") from error
    return {"lock_from_y":lock_from_y, "canvas":(width, height),
            "status":"source_pose_derived_not_scene_qa"}


def check_stationary_upper_body_mask(edit_mask, frame, principal_index, *, keypoint_format="openpose18"):
    """Reject ANY permitted change of retained lower body, not just its center."""
    if not isinstance(edit_mask, Image.Image):
        raise ActorEditPolicyError("missing_edit_mask")
    boundary = stationary_upper_body_lock(frame, principal_index, keypoint_format)
    if edit_mask.size != boundary["canvas"]:
        raise ActorEditPolicyError("mask_canvas_mismatch")
    lower = edit_mask.convert("L").crop((0, boundary["lock_from_y"], edit_mask.width, edit_mask.height))
    if lower.getextrema()[1] != 0:
        raise ActorEditPolicyError("non_target_lower_body_editable")
    return {"status":"lower_body_locked", "lock_from_y":boundary["lock_from_y"],
            "locked_lower_pixels":lower.width*lower.height,
            "evidence":"observed_bilateral_knees_and_ankles"}
