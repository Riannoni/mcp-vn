#!/usr/bin/env python3
"""Read-only Codex and Grok OAuth quota status via locally bound CLIProxyAPI v8.

No inference request, OAuth bearer read, credential content dump or persistent cache.
Output contains only account numbers (not identity), quota metrics and reset times.
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

BASE = "http://127.0.0.1:8317/v8/management"
KEYFILE = pathlib.Path.home() / ".config/mcp-vn/cli-proxy-management.key"
ZONE = ZoneInfo("Asia/Novosibirsk")
MAX_RESPONSE = 1024 * 1024
PROVIDERS = ("codex", "xai")


def percentage(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or not 0 <= value <= 100:
        return None
    return value


def iso_time(value):
    if not isinstance(value, str) or len(value) > 70:
        return None
    try:
        value = value.replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(dt.timezone.utc).isoformat()
    except ValueError:
        return None


def epoch_time(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return dt.datetime.fromtimestamp(value, dt.timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def call(path, payload=None):
    # Only this fixed localhost URL may receive the management password.
    if path not in ("/credentials", "/requests/api-call"):
        raise ValueError("Unsupported management route")
    key = KEYFILE.read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError("Local management key is empty")
    headers = {"X-Management-Key": key}
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        BASE + path,
        data=body,
        headers=headers,
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("Management response too large")
    return json.loads(raw)


def via_proxy(auth_index, url, extra_headers=None):
    headers = {"Authorization": "Bearer $TOKEN$", "Accept": "application/json"}
    headers.update(extra_headers or {})
    # Auth index and bearer substitution are handled inside the proxy.
    result = call("/requests/api-call", {
        "auth_index": auth_index,
        "method": "GET",
        "url": url,
        "header": headers,
    })
    code = result.get("status_code")
    if code != 200:
        return {"status": "upstream_error", "http": code if isinstance(code, int) else None}
    raw = result.get("body")
    if not isinstance(raw, str) or len(raw) > MAX_RESPONSE:
        return {"status": "invalid_response"}
    try:
        return {"status": "ok", "data": json.loads(raw)}
    except (ValueError, TypeError):
        return {"status": "invalid_response"}


def codex_window(window):
    if not isinstance(window, dict):
        return {"status": "unavailable"}
    used = percentage(window.get("used_percent"))
    length = window.get("limit_window_seconds")
    reset = window.get("reset_at")
    return {
        "status": "ok" if used is not None else "unavailable",
        "used_percent": used,
        "remaining_percent": round(100 - used, 3) if used is not None else None,
        "window_seconds": length if isinstance(length, int) and 0 < length <= 31536000 else None,
        "reset_at": epoch_time(reset),
    }


def parse_codex(raw):
    if not isinstance(raw, dict):
        return {"status": "invalid_response"}
    limit = raw.get("rate_limit")
    if not isinstance(limit, dict):
        return {"status": "unavailable"}
    return {
        "status": "ok",
        "plan": raw.get("plan_type") if isinstance(raw.get("plan_type"), str) else None,
        "allowed": limit.get("allowed") if isinstance(limit.get("allowed"), bool) else None,
        "limit_reached": limit.get("limit_reached") if isinstance(limit.get("limit_reached"), bool) else None,
        "windows": {
            "5h_or_primary": codex_window(limit.get("primary_window")),
            "7d_or_secondary": codex_window(limit.get("secondary_window")),
        },
        "extra_pool_count": len(raw.get("additional_rate_limits") or [])
            if isinstance(raw.get("additional_rate_limits"), list) else 0,
    }


def parse_xai(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("config"), dict):
        return {"status": "unavailable"}
    config = raw["config"]
    used = percentage(config.get("creditUsagePercent"))
    current = config.get("currentPeriod")
    if not isinstance(current, dict):
        current = {}
    kind = current.get("type")
    period = {
        "USAGE_PERIOD_TYPE_WEEKLY": "weekly",
        "USAGE_PERIOD_TYPE_MONTHLY": "monthly",
        "USAGE_PERIOD_TYPE_DAILY": "daily",
    }.get(kind, "unknown")
    start = iso_time(current.get("start") or config.get("billingPeriodStart"))
    end = iso_time(current.get("end") or config.get("billingPeriodEnd"))
    seconds = None
    if start is not None and end is not None:
        seconds = int((dt.datetime.fromisoformat(end) - dt.datetime.fromisoformat(start)).total_seconds())
        if seconds <= 0 or seconds > 400 * 86400:
            seconds = None
    # Do not fabricate 0% when field is absent; no refund/credit totals exposed.
    return {
        "status": "ok" if used is not None else "unavailable",
        "used_percent": used,
        "remaining_percent": round(100 - used, 3) if used is not None else None,
        "period": period,
        "window_seconds": seconds,
        "start_at": start,
        "reset_at": end,
        "is_unified_billing_user": config.get("isUnifiedBillingUser")
            if isinstance(config.get("isUnifiedBillingUser"), bool) else None,
    }


def inspect_provider(provider, account_number, record):
    url, extra_headers = (
        ("https://chatgpt.com/backend-api/wham/usage", {})
        if provider == "codex" else
        ("https://cli-chat-proxy.grok.com/v1/billing?format=credits",
         {"X-XAI-Token-Auth": "xai-grok-cli"})
    )
    response = via_proxy(record["auth_index"], url, extra_headers)
    if response["status"] != "ok":
        return {"provider": provider, "account_number": account_number, **response}
    result = parse_codex(response["data"]) if provider == "codex" else parse_xai(response["data"])
    return {"provider": provider, "account_number": account_number, **result}


def friendly_reset(value):
    if value is None:
        return "unknown"
    return dt.datetime.fromisoformat(value).astimezone(ZONE).strftime("%Y-%m-%d %H:%M:%S %Z")


def show(accounts):
    for item in accounts:
        provider = "Grok / xAI" if item["provider"] == "xai" else "Codex"
        print(f"{provider} account #{item['account_number']}: {item['status']}")
        if item["status"] != "ok":
            if item.get("http") is not None:
                print("  Upstream HTTP:", item["http"])
            continue
        if item["provider"] == "codex":
            print("  Plan:", item.get("plan") or "unknown", "allowed:", item.get("allowed"),
                  "limit reached:", item.get("limit_reached"))
            for label, window in item.get("windows", {}).items():
                used = window.get("used_percent")
                print(f"  {label}: {used}% used / {window.get('remaining_percent')}% remaining"
                      if used is not None else f"  {label}: unavailable")
                print("    reset:", friendly_reset(window.get("reset_at")))
        else:
            print(f"  Period: {item.get('period')} ({item.get('window_seconds')} seconds)")
            print(f"  {item.get('used_percent')}% used / {item.get('remaining_percent')}% remaining")
            print("  reset:", friendly_reset(item.get("reset_at")))
    print("Local management UI: http://127.0.0.1:8317/management.html")


def main():
    parser = argparse.ArgumentParser(description="Local CLIProxyAPI Codex + Grok OAuth quotas")
    parser.add_argument("--provider", choices=("all", *PROVIDERS), default="all")
    parser.add_argument("--json", action="store_true", help="Print sanitized machine-readable JSON")
    args = parser.parse_args()
    records = call("/credentials").get("files", [])
    if not isinstance(records, list):
        raise ValueError("Invalid credential listing")
    selected = PROVIDERS if args.provider == "all" else (args.provider,)
    items = []
    for provider in selected:
        entries = [r for r in records if isinstance(r, dict) and
                   r.get("provider") == provider and
                   isinstance(r.get("auth_index"), str) and r.get("auth_index") and
                   not r.get("disabled")]
        if not entries:
            items.append({"provider": provider, "account_number": 0, "status": "no_credential"})
        for i, record in enumerate(entries, 1):
            try:
                items.append(inspect_provider(provider, i, record))
            except (OSError, ValueError, TypeError, urllib.error.URLError, RuntimeError):
                items.append({"provider": provider, "account_number": i, "status": "request_failed"})
    report = {
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "timezone": "Asia/Novosibirsk",
        "accounts": items,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        show(items)
    return 0 if all(x["status"] == "ok" for x in items) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
        # Deliberately no exception body: it might contain a URL or credential.
        print(f"Quota check failed ({type(exc).__name__})", file=sys.stderr)
        sys.exit(1)
