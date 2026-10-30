"""Preflight stale-limb erasure when an existing sprite changes its hand pose.

An original composited hand left outside the editing mask will survive a
successful generation and yield duplicate limbs. This guard inspects cached,
versioned independent source DWPose landmarks and the proposed *edit* mask.
It never certifies the new hand pose or visual quality; ambiguity blocks.
"""
from __future__ import annotations
from PIL import Image,ImageOps


def check_stale_hand_coverage(frame,principal_index,edit_mask,min_coverage=.92):
    def fail(why,**extra):return {'verdict':'unobservable','reason':why,**extra}
    if not isinstance(frame,dict) or not isinstance(edit_mask,Image.Image):
        return fail('source_pose_or_mask_unavailable')
    try:
        w=int(frame['canvas_width']);h=int(frame['canvas_height'])
        people=frame['people'];person=people[principal_index]
        if not isinstance(principal_index,int) or principal_index<0 or w<128 or h<128:
            raise ValueError()
    except (IndexError,KeyError,ValueError,TypeError):return fail('source_pose_invalid')
    if edit_mask.size!=(w,h):return fail('mask_canvas_mismatch')
    if not .85<=min_coverage<=1:return fail('coverage_threshold_invalid')
    # Pure black=locked, white=editable, already canonicalised to L.
    mask=edit_mask.convert('L')
    coverage=[]
    for side in ('hand_left_keypoints_2d','hand_right_keypoints_2d'):
        vec=person.get(side) or []
        if len(vec)!=63:return fail('source_hands_not_observable')
        points=[]
        for i in range(21):
            try:x,y,c=map(float,vec[i*3:i*3+3])
            except (ValueError,TypeError):return fail('source_hand_coordinate_invalid')
            if c>=.55 and 0<=x<w and 0<=y<h:points.append((x,y))
        if len(points)<17:return fail('source_hands_low_confidence')
        # Extend bbox to skin edge. Pixels under the old hand must be mutable;
        # otherwise the old dangling fingers remain as fourth-hand artifacts.
        x0=max(0,int(min(x for x,y in points))-5)
        x1=min(w,int(max(x for x,y in points))+6)
        y0=max(0,int(min(y for x,y in points))-6)
        y1=min(h,int(max(y for x,y in points))+7)
        if x1-x0<8 or y1-y0<8:return fail('hand_bbox_unreliable')
        roi=mask.crop((x0,y0,x1,y1))
        values=roi.histogram()
        fully_editable=sum(values[225:])/(roi.width*roi.height)
        coverage.append({'source_hand':side,'editable_fraction':round(fully_editable,4),
                         'original_bbox':[x0,y0,x1,y1]})
    if not all(c['editable_fraction']>=min_coverage for c in coverage):
        return {'verdict':'violated','reason':'original_hands_outside_edit_mask',
                'coverage':coverage}
    return {'verdict':'covered_for_replacement','reason':'both_original_hands_editable',
            'coverage':coverage,'note':'not evidence of correct regenerated anatomy'}
