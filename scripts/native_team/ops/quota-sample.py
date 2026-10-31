#!/usr/bin/env python3
import subprocess, json, datetime, pathlib, sys
root=pathlib.Path(__file__).resolve().parent.parent
at=datetime.datetime.now(datetime.timezone.utc).isoformat()
try:
 r=subprocess.run([str(pathlib.Path.home()/".local/bin/vn-proxy-quota"),"--provider","codex","--json"],capture_output=True,text=True,timeout=14)
 if r.returncode:raise RuntimeError("quota CLI returned nonzero")
 body=json.loads(r.stdout)
 account=next(x for x in body["accounts"] if x.get("provider")=="codex" and x.get("status")=="ok")
 w=account["windows"]
 entry={"utc":at,"ok":True,"5h_used":w["5h_or_primary"]["used_percent"],"7d_used":w["7d_or_secondary"]["used_percent"]}
except Exception as exc:
 entry={"utc":at,"ok":False,"error_type":type(exc).__name__}
with (root/"state"/"quota-timeline.jsonl").open("a",encoding="utf-8") as out:
 out.write(json.dumps(entry,ensure_ascii=False)+"\n")
print(json.dumps(entry,ensure_ascii=False))
