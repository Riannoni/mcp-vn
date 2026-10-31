#!/usr/bin/env python3
"""Fail-closed advisory quota gate for *additional* Cloud wake requests.
The proxy meter is a useful proxy, not an authoritative Work usage record.
Scheduled tasks and provider-side limits remain the final authority.
"""
import datetime
import json
import time
from pathlib import Path

MAX_5H_USED = 75
MAX_7D_USED = 75
MAX_SAMPLE_AGE_SECONDS = 180

def permit(root, now=None, provider="codex_oauth"):
    """Native Scheduled tasks do not use the CLIProxy Codex OAuth meter.

    Admission for ChatGPT Scheduled workers is handled by ChatGPT itself.
    This never authorizes a Codex, Work or paid API call.
    """
    if provider == "chatgpt_scheduled":
        return {
            "eligible": True,
            "reason": "native_chatgpt_platform_quota_authoritative",
            "quota_meter": "not_available_locally",
        }
    if provider != "codex_oauth":
        raise ValueError("unknown quota provider")

    now = time.time() if now is None else now
    try:
        sample = json.loads((Path(root) / "state" / "quota-latest.json").read_text())
        if sample.get("ok") is not True:
            return {"eligible": False, "reason": "quota_unavailable"}
        sample_time = datetime.datetime.fromisoformat(sample["utc"]).timestamp()
        age = now - sample_time
        if age < -30 or age > MAX_SAMPLE_AGE_SECONDS:
            return {"eligible": False, "reason": "quota_stale"}
        five, week = sample["5h_used"], sample["7d_used"]
        if any(type(v) not in (float, int) or not 0 <= v <= 100 for v in (five, week)):
            return {"eligible": False, "reason": "quota_invalid"}
        if five >= MAX_5H_USED:
            return {"eligible": False, "reason": "quota_5h_soft_limit"}
        if week >= MAX_7D_USED:
            return {"eligible": False, "reason": "quota_7d_soft_limit"}
        return {"eligible": True, "reason": "quota_sample_ok"}
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        return {"eligible": False, "reason": "quota_unavailable"}
