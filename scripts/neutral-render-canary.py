#!/usr/bin/env python3
"""Private GPU canary: one revised sprite, followed by two related neutral CGs.

Only operates on the caller-supplied *read-only* job snapshot; does not publish
any result, edit saves, or submit actions. Never put output assets in Git.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import time
import uuid


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-job',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    if not os.environ.get('VN_WORKER_TOKEN'):
        raise RuntimeError('Production worker environment must be loaded privately')
    import worker
    source=json.loads(args.source_job.read_text())
    original=source['spec']
    cast=original.get('characters') or []
    if len(cast)!=1 or not cast[0].get('anchor_face_asset'):
        raise ValueError('Canary requires exactly one established adult face anchor')
    args.output_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
    person=cast[0]['name']
    outfit='blue travel jacket'
    specs=[]
    sprite=copy.deepcopy(original)
    sprite.update(kind='sprite',composition='transparent_layer',resolution=[832,1216],
                  narrator_prompt=False,character=person,appearance=cast[0].get('appearance',''),
                  variant={'outfit':outfit,'pose':'standing','emotion':'calm'},
                  anchor_asset=cast[0].get('anchor_asset'),
                  face_asset=cast[0].get('anchor_face_asset'),
                  anchor_style=source['style'],previous_sprite_asset='',visual_contract=None)
    specs.append(('sprite',sprite,
                  'Single full-length adult traveler wearing a blue travel jacket, calm neutral expression, clean neutral studio matte.'))
    for label,prompt in (
        ('cg-one', 'One adult traveler in a blue travel jacket studies a folded map beside a medieval market stall. The entire open-air market square, sunlit masonry, fruit baskets and tall town clock tower remain visible behind the traveler. One unified medium-wide camera shot.'),
        ('cg-two', 'The same adult traveler in a blue travel jacket walks beneath the stone archway at the edge of the same medieval market, carrying the folded map, with an old cart, shadowed stonework and market stalls visible behind. One unified wide three-quarter camera shot.'),
    ):
        scene=copy.deepcopy(original)
        scene.update(kind='scene',composition='neural_story',resolution=[1216,704],
                     narrator_prompt=True,variant={'outfit':'default','pose':'standing','emotion':'neutral'},
                     quality='standard')
        scene['characters'][0]['outfit']=outfit
        scene['characters'][0]['pose']='standing'
        contract=scene.get('visual_contract') or {}
        contract['contacts']=[]
        if contract.get('principals'):
            contract['principals'][0]['outfit']=outfit
            contract['principals'][0]['pose']='standing'
        scene['visual_contract']=contract
        specs.append((label,scene,prompt))
    for kind,spec,prompt in specs:
        start=time.monotonic()
        mode='sprite' if kind=='sprite' else 'scene'
        job={'id':str(uuid.uuid4()),'kind':mode,'style':source['style'],
             'spec':spec,'character':person if mode=='sprite' else '',
             'prompt':prompt,'attempts':1,'status':'working'}
        summary={'test':kind,'mode':mode,'attempts':1,'passed':False}
        try:
            graph,background=worker.image_graph(job)
            summary['face_adapter']=any(n.get('class_type')=='IPAdapterAdvanced' for n in graph.values())
            summary['body_img2img']=mode=='sprite' and any(
                n.get('class_type')=='VAEEncode' for n in graph.values())
            raw,ext=worker.run_comfy(job,graph)
            path=args.output_dir/(kind+ext)
            path.write_bytes(raw)
            os.chmod(path,0o600)
            summary['generation_seconds']=round(time.monotonic()-start,2)
            _,qa=worker.assess(job,raw,background)
            summary['passed']=qa.get('passed') is True
            summary['reasons']=qa.get('reasons',[])
            summary['qa_seconds']=round(time.monotonic()-start-summary['generation_seconds'],2)
        except Exception as error:
            summary['error']=type(error).__name__+': '+str(error)[:220]
        summary['total_seconds']=round(time.monotonic()-start,2)
        (args.output_dir/(kind+'.json')).write_text(json.dumps(summary,indent=2))
        print(json.dumps(summary),flush=True)
    print('NEUTRAL_CANARY_FINISHED',flush=True)


if __name__=='__main__':
    main()
