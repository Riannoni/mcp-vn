"""Global rendering policy versioned across game packs and saves."""
import json
from pathlib import Path

def read_engine_contract():
    p=Path(__file__).resolve().parent.parent/'engine'/'contract.json'
    doc=json.loads(p.read_text())
    if doc.get('engine_id')!='mcp-vn' or doc.get('contract_version')!=1:
        raise ValueError('Unsupported engine policy')
    return doc

def assert_engine_snapshot(snapshot):
    if snapshot is None:
        return True
    doc=read_engine_contract()
    render=doc['render']
    expected={
        'engine_id':doc['engine_id'],
        'contract_version':doc['contract_version'],
        'render_profile':render['profile'],
        'pose_catalog':render['pose_catalog'],
        'qa_policy':render['qa_policy'],
        'max_anchored_principals_per_pass':render['max_anchored_principals_per_pass'],
    }
    if snapshot!=expected:
        raise ValueError('Server and rendering worker engine contracts differ')
    return True
