#!/usr/bin/env python3
"""Minute-by-minute advisory for idle cloud task lanes; never calls a model."""
import datetime
import json
import pathlib

from wake_guard import LANES, check

ROOT=pathlib.Path.home()/".local/share/web-vn-native-team/run-20261031-full"
result={"at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source":"local_advisory_only",
        "automations_invoked":False,
        "lanes":{lane:check(ROOT,lane) for lane in LANES}}
print(json.dumps(result,ensure_ascii=False,sort_keys=True))
