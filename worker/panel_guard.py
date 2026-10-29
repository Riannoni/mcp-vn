"""Fast conservative rejection of duplicated 2-by-2 composite CG panels.

Only apply to an explicitly single-frame neural-story CG. This protects against
the tiled/duplicated multi-view generation observed in the October regression.
It is NOT a general-purpose collage classifier, so negatives are not proofs.
"""
from PIL import Image

def detect_four_panel_collage(image):
    """Return bounded numeric evidence; reject only a high-confidence 2x2 case.

    Two strong orthogonal seams alone could be an ordinary window or grid.
    Require both vertical repeated-region similarity and obvious seams.
    """
    import numpy as np
    gray=np.asarray(image.convert("L").resize((512,384),
                           Image.Resampling.BILINEAR),dtype=np.float32)
    h,w=gray.shape
    vertical=np.abs(np.diff(gray,axis=1))
    horizontal=np.abs(np.diff(gray,axis=0))
    x=float(vertical[:,w//2-1].mean())
    y=float(horizontal[h//2-1,:].mean())
    xbaseline=max(1.,float(np.median(vertical.mean(axis=0))))
    ybaseline=max(1.,float(np.median(horizontal.mean(axis=1))))
    sx=x/xbaseline
    sy=y/ybaseline
    def corr(a,b):
        a=a[::4,::4].ravel()
        b=b[::4,::4].ravel()
        aa=a-a.mean();bb=b-b.mean()
        denom=float(np.sqrt((aa*aa).sum()*(bb*bb).sum()))
        return float((aa*bb).sum()/denom) if denom>1 else 0.
    upper_left=gray[:h//2,:w//2]
    lower_left=gray[h//2:,:w//2]
    upper_right=gray[:h//2,w//2:]
    lower_right=gray[h//2:,w//2:]
    left=corr(upper_left,lower_left)
    right=corr(upper_right,lower_right)
    tiled=(sx>3.2 and sy>3.2 and min(left,right)>.28
           and (left+right)/2>.36)
    return {"detected":bool(tiled),"seam_x_ratio":round(sx,2),
            "seam_y_ratio":round(sy,2),
            "repeat_left":round(left,3),"repeat_right":round(right,3)}
