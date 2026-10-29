"""Versioned CLIP text label bank; tests prevent inconsistent category keys."""
import json
from pathlib import Path
def load_profiles(filename=None):
    path=Path(filename) if filename else Path(__file__).with_name("qa-environments.json")
    data=json.loads(path.read_text())
    if data.get("schema")!="mcp-vn.qa-environments.v1":raise ValueError("QA profile schema mismatch")
    profiles=data.get("profiles") or {}
    default=profiles.get(data.get("default"))
    if not isinstance(default,dict) or len(default)!=7:
        raise ValueError("Invalid default QA environment labels")
    keys=set(default)
    if any(set(labels)!=keys or any(not isinstance(v,str) or not v for v in labels.values())
           for labels in profiles.values()):
        raise ValueError("QA environment profiles diverge")
    return data["default"],profiles
