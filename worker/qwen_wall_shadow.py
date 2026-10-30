"""Offline CPU Qwen3-VL wall-action observation for controlled QA A/B only.

Only the documented Apache-2.0 2B weights in an isolated local directory;
not a global yes/no accept tool. Each call returns an observable category.
"""
from __future__ import annotations
import re,time
from pathlib import Path

PROMPT=(
 "Inspect actual pixels, not a stated intended pose. Identify where the main person's hands are. "
 "Choose exactly ONE option: WALL (both hands against upright masonry), "
 "HEAD (hands on their own head), GROUND (hands on pavement), "
 "SIDES (hands resting beside their body), PROP (hands holding an object), "
 "UNCLEAR (no reliable visual evidence). Answer one option, then a brief specific reason."
)
LABELS={'WALL','HEAD','GROUND','SIDES','PROP','UNCLEAR'}

def parse_action_answer(text):
    match=re.match(r'^\s*(WALL|HEAD|GROUND|SIDES|PROP|UNCLEAR)\b',str(text or '').upper())
    label=match.group(1) if match else 'UNCLEAR'
    return {'label':label,
            'verdict':'wall_observed' if label=='WALL' else
                      'unobservable' if label=='UNCLEAR' else 'not_wall',
            'answer_excerpt':str(text or '')[:180]}

class QwenWallShadow:
    def __init__(self,model_dir):
        root=Path(model_dir)
        if not root.is_dir() or not (root/'config.json').is_file() or not (root/'model.safetensors').is_file():
            raise ValueError('qwen_shadow_model_missing')
        from transformers import Qwen3VLForConditionalGeneration,AutoProcessor
        import torch
        torch.set_num_threads(5)
        self.torch=torch
        self.processor=AutoProcessor.from_pretrained(str(root),local_files_only=True,trust_remote_code=False)
        self.model=Qwen3VLForConditionalGeneration.from_pretrained(
            str(root),dtype=torch.float32,local_files_only=True,
            trust_remote_code=False).eval().to('cpu')

    def observe(self,image):
        if image is None:raise ValueError('missing_frame')
        frame=image.convert('RGB');frame.thumbnail((768,768))
        messages=[{'role':'user','content':[{'type':'image','image':frame},
                    {'type':'text','text':PROMPT}]}]
        start=time.monotonic()
        x=self.processor.apply_chat_template(messages,add_generation_prompt=True,
             tokenize=True,return_dict=True,return_tensors='pt')
        with self.torch.inference_mode():
            y=self.model.generate(**x,max_new_tokens=55,do_sample=False,
                                  repetition_penalty=1.02)
        raw=self.processor.batch_decode(y[:,x['input_ids'].shape[1]:],skip_special_tokens=True)[0]
        return {**parse_action_answer(raw),
                'duration_seconds':round(time.monotonic()-start,2),
                'source_model':'Qwen3-VL-2B-Instruct',
                'note':'Shadow evidence, not verified physical contact'}
