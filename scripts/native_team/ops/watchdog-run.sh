#!/usr/bin/env bash
set -euo pipefail
umask 077
root="$HOME/.local/share/web-vn-native-team/run-20261031-full"
python3 "$root/control/teamctl.py" watchdog > "$root/state/watchdog-latest.tmp"
mv "$root/state/watchdog-latest.tmp" "$root/state/watchdog-latest.json"
python3 "$root/control/teamctl.py" status > "$root/state/team-latest.tmp"
mv "$root/state/team-latest.tmp" "$root/state/team-latest.json"

/usr/bin/python3 "$root/control/quota-sample.py" > "$root/state/quota-latest.json" || true
