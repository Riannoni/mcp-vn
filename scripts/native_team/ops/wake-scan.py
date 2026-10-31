#!/usr/bin/env python3
"""Minute-by-minute advisory for idle cloud task lanes; never calls a model."""
import datetime
import json
import pathlib
import sqlite3
import time

from wake_guard import LANES, check, check_review
from idle_metrics import calculate

ROOT=pathlib.Path.home()/".local/share/web-vn-native-team/run-20261031-full"
with sqlite3.connect(ROOT/"state/team.sqlite3",timeout=10) as db:
    db.row_factory=sqlite3.Row
    latency=calculate(db,now=time.time())
result={"at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source":"local_advisory_only",
        "automations_invoked":False,
        "lanes":{lane:check(ROOT,lane) for lane in LANES},
        "chief_review":check_review(ROOT),
        "latency":latency,
        "sla_violations":[lane for lane,entry in latency.items()
                          if entry["over_10_minutes"] or entry.get("planning_deficit_over_10_minutes")],
        "five_minute_alerts":[lane for lane,entry in latency.items()
                          if (entry.get("ready_idle_seconds") or 0)>300 or entry.get("planning_deficit_over_5_minutes")]}
print(json.dumps(result,ensure_ascii=False,sort_keys=True))
