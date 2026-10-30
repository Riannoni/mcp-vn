"""Opt-in local face-identity *observation* for CG and sprite QA.

Uses pinned OpenCV Zoo YuNet/SFace ONNX models in a private directory. Does
not set an acceptance threshold or override any production QA. A missing,
ambiguous, or occluded face remains unobservable. No identity bytes leave host.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

MODEL_SHA={
    'yunet.onnx':'8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4',
    'sface.onnx':'0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79',
}

def model_integrity(directory):
    root=Path(directory)
    if not root.is_dir():return {'ok':False,'reason':'model_directory_unavailable'}
    for name,wanted in MODEL_SHA.items():
        p=root/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=wanted:
            return {'ok':False,'reason':'model_missing_or_hash_mismatch:'+name}
    return {'ok':True,'reason':'verified_pinned_models'}

class SFaceShadow:
    def __init__(self,directory):
        status=model_integrity(directory)
        if not status['ok']:raise ValueError(status['reason'])
        import cv2
        self.cv=cv2
        root=Path(directory)
        self.det=cv2.FaceDetectorYN.create(str(root/'yunet.onnx'),'',(320,320),score_threshold=.67)
        self.rec=cv2.FaceRecognizerSF.create(str(root/'sface.onnx'),'')
    def _face(self,pil):
        import numpy as np
        cv=self.cv
        im=cv.cvtColor(np.asarray(pil.convert('RGB')),cv.COLOR_RGB2BGR)
        if min(im.shape[:2])<112:return (None,{'verdict':'unobservable','reason':'insufficient_resolution'})
        self.det.setInputSize((im.shape[1],im.shape[0]))
        _,faces=self.det.detect(im)
        if faces is None:return (None,{'verdict':'unobservable','reason':'face_not_detected'})
        selected=[x for x in faces if x[2]>=30 and x[3]>=30 and x[14]>=.67]
        if len(selected)!=1:
            return (None,{'verdict':'unobservable','reason':'face_attribution_ambiguous',
                          'face_count':len(selected)})
        f=selected[0]
        embedding=self.rec.feature(self.rec.alignCrop(im,f))
        return (embedding,{'verdict':'observed','face_box':[int(round(v)) for v in f[:4]],
                            'detector_confidence':round(float(f[14]),4)})
    def compare(self,canonical,candidate):
        try:
            source,src=self._face(canonical)
            target,dst=self._face(candidate)
            if source is None:return {'verdict':'unobservable','reason':'canonical_'+src['reason']}
            if target is None:return {'verdict':'unobservable','reason':'candidate_'+dst['reason']}
            value=float(self.rec.match(source,target,self.cv.FaceRecognizerSF_FR_COSINE))
            if not -1<=value<=1:raise ValueError('invalid_similarity')
            return {'verdict':'observed','cosine':round(value,5),'candidate_face_box':dst['face_box'],
                    'method':'OpenCV_Zoo_SFace','warning':'Uncalibrated synthetic-face similarity; not an accept gate'}
        except (ValueError,TypeError,RuntimeError) as exc:
            return {'verdict':'unobservable','reason':'measurement_failed','detail':str(exc)[:75]}
