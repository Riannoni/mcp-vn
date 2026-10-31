#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$HOME/.local/share/web-vn-native-team/run-20261031-full"
python3 "$root/control/teamctl.py" watchdog > "$root/state/watchdog-latest.tmp"
mv "$root/state/watchdog-latest.tmp" "$root/state/watchdog-latest.json"

# Approved, fixed P0 task catalog. This only inserts validated source-only tasks
# into the local WAL queue. No model calls, GPU jobs, external API or approvals.
# Independent Chief review is still mandatory for any completed task.
if python3 "$root/control/task_catalog.py" --root "$root" --catalog "$root/control/task-catalog.json" > "$root/state/catalog-latest.tmp"; then
    mv "$root/state/catalog-latest.tmp" "$root/state/catalog-latest.json"
else
    rm -f "$root/state/catalog-latest.tmp"
    printf '{"ok":false,"reason":"catalog_failed; see journal"}\n' > "$root/state/catalog-latest.json"
fi
python3 "$root/control/teamctl.py" status > "$root/state/team-latest.tmp"
mv "$root/state/team-latest.tmp" "$root/state/team-latest.json"
/usr/bin/python3 "$root/control/quota-sample.py" > "$root/state/quota-latest.json" || true

# Advisory only: local timer never invokes ChatGPT, Codex or model APIs.
if /usr/bin/python3 "$root/control/wake-scan.py" > "$root/state/wake-ready.tmp"; then
  mv "$root/state/wake-ready.tmp" "$root/state/wake-ready.json"
else
  rm -f "$root/state/wake-ready.tmp"
fi
