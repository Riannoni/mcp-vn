"""Reproducible OpenPose COCO-18 guide library for SDXL ControlNet.

Outputs native-colour OpenPose PNG hint images AND editor-compatible
pose_keypoints_2d JSON, at scene and sprite resolutions. No diffusion is run.
Keys are pixel coordinates in a 600x800 virtual frame. Right/left refer to
the character's anatomical sides, not the observer's.
"""
from __future__ import annotations
import json
from pathlib import Path

JOINTS=("nose","neck","r_shoulder","r_elbow","r_wrist",
        "l_shoulder","l_elbow","l_wrist","r_hip","r_knee","r_ankle",
        "l_hip","l_knee","l_ankle","r_eye","l_eye","r_ear","l_ear")
# Standard COCO-18 OpenPose image colours, RGB; black background.
COLORS=((255,0,0),(255,85,0),(255,170,0),(255,255,0),
        (170,255,0),(85,255,0),(0,255,0),(0,255,85),
        (0,255,170),(0,255,255),(0,170,255),(0,85,255),
        (0,0,255),(85,0,255),(170,0,255),(255,0,255),
        (255,0,170),(255,0,85))
BONES=((1,2),(1,5),(2,3),(3,4),(5,6),(6,7),
       (1,8),(8,9),(9,10),(1,11),(11,12),(12,13),
       (1,0),(0,14),(14,16),(0,15),(15,17))
BONE_COLORS=((153,0,0),(153,51,0),(153,102,0),(153,153,0),
             (102,153,0),(51,153,0),(0,153,0),(0,153,51),
             (0,153,102),(0,153,153),(0,102,153),(0,51,153),
             (0,0,153),(51,0,153),(102,0,153),(153,0,153),
             (153,0,102))

# 14 base body keypoints; facial landmarks are derived from nose/neck.
FRONT=((300,98),(300,165),(251,188),(231,293),(219,390),
       (349,188),(369,293),(381,390),
       (271,428),(264,578),(255,729),
       (329,428),(337,578),(346,729))
SIDE=((313,98),(294,168),(284,190),(279,289),(285,380),
      (312,195),(319,294),(322,382),
      (283,430),(290,579),(297,728),
      (311,432),(320,579),(331,728))
BACK=((300,98),(300,165),(248,187),(218,283),(210,377),
      (351,187),(381,283),(389,377),
      (268,428),(260,578),(254,728),
      (332,428),(341,578),(348,728))
THREE_QUARTER=((315,98),(303,165),(260,184),(230,284),(221,383),
               (353,190),(377,289),(387,391),
               (276,428),(275,573),(269,728),
               (333,432),(351,579),(359,731))
BASES={"front":FRONT,"side":SIDE,"back":BACK,"three_quarter":THREE_QUARTER}

def _pose(base, *, label, category, tags=(), **changes):
    return {"base":base,"label":label,"category":category,"tags":list(tags),
            "changes":changes}

# Each patch edits explicitly identified COCO joints. We do not transpose a
# front skeleton to pretend it is a rear/side skeleton.
POSES={
 "stand_front":_pose("front",label="Standing · front",category="standing"),
 "stand_side":_pose("side",label="Standing · side",category="standing"),
 "stand_back":_pose("back",label="Standing · back",category="standing"),
 "stand_three_quarter":_pose("three_quarter",label="Standing · three-quarter",category="standing"),
 "hands_on_hips_front":_pose("front",label="Hands on hips",category="standing",
   r_elbow=(207,325),r_wrist=(271,426),l_elbow=(393,325),l_wrist=(329,426)),
 "arms_crossed_front":_pose("front",label="Arms crossed",category="standing",
   r_elbow=(244,299),r_wrist=(347,273),l_elbow=(356,299),l_wrist=(253,272)),
 "arms_up_front":_pose("front",label="Hands overhead",category="standing",
   r_elbow=(213,125),r_wrist=(233,47),l_elbow=(385,122),l_wrist=(369,44)),
 "point_right_front":_pose("front",label="Pointing to image right",category="gesture",
   l_elbow=(431,210),l_wrist=(534,201),r_elbow=(234,295),r_wrist=(251,417)),
 "wave_front":_pose("front",label="Waving",category="gesture",
   l_elbow=(395,124),l_wrist=(432,65)),
 "walk_front":_pose("front",label="Walking · front",category="motion",
   r_elbow=(220,293),r_wrist=(231,373),l_elbow=(381,270),l_wrist=(401,369),
   r_knee=(240,578),r_ankle=(221,724),l_knee=(369,568),l_ankle=(400,705)),
 "walk_side":_pose("side",label="Walking · side",category="motion",
   r_elbow=(250,281),r_wrist=(207,369),l_elbow=(343,294),l_wrist=(370,390),
   r_knee=(223,558),r_ankle=(164,707),l_knee=(361,562),l_ankle=(402,713)),
 "walk_back":_pose("back",label="Walking · back",category="motion",
   r_elbow=(225,292),r_wrist=(253,377),l_elbow=(379,293),l_wrist=(350,385),
   r_knee=(238,570),r_ankle=(228,722),l_knee=(355,562),l_ankle=(390,718)),
 "run_front":_pose("front",label="Running · front",category="motion",
   r_elbow=(193,262),r_wrist=(225,185),l_elbow=(400,301),l_wrist=(440,371),
   r_knee=(218,555),r_ankle=(265,701),l_knee=(379,520),l_ankle=(413,627)),
 "run_side":_pose("side",label="Running · side",category="motion",
   nose=(327,91),neck=(286,168),r_shoulder=(276,195),r_elbow=(211,227),
   r_wrist=(177,180),l_shoulder=(305,203),l_elbow=(356,285),l_wrist=(404,301),
   r_hip=(281,426),r_knee=(199,512),r_ankle=(119,619),
   l_hip=(312,431),l_knee=(400,515),l_ankle=(441,641)),
 "kneel_one_front":_pose("front",label="One-knee kneel · front",category="kneeling",
   nose=(300,138),neck=(300,205),r_shoulder=(252,226),l_shoulder=(350,226),
   r_elbow=(245,311),r_wrist=(266,401),l_elbow=(367,322),l_wrist=(354,407),
   r_hip=(266,463),r_knee=(224,588),r_ankle=(320,629),
   l_hip=(330,463),l_knee=(388,552),l_ankle=(388,710)),
 "kneel_one_side":_pose("side",label="One-knee kneel · side",category="kneeling",
   nose=(312,133),neck=(294,200),r_shoulder=(279,225),
   r_elbow=(283,316),r_wrist=(303,410),l_shoulder=(307,225),
   l_elbow=(342,305),l_wrist=(358,412),
   r_hip=(285,457),r_knee=(216,576),r_ankle=(341,622),
   l_hip=(315,459),l_knee=(380,531),l_ankle=(386,679)),
 "kneel_both_front":_pose("front",label="Both knees down · front",category="kneeling",
   nose=(301,132),neck=(300,204),r_shoulder=(250,227),
   l_shoulder=(350,227),r_elbow=(242,330),r_wrist=(269,427),
   l_elbow=(360,328),l_wrist=(333,428),
   r_hip=(264,470),r_knee=(247,607),r_ankle=(299,650),
   l_hip=(336,470),l_knee=(351,608),l_ankle=(304,650)),
 "crouch_front":_pose("front",label="Deep crouch · front",category="crouching",
   nose=(301,254),neck=(301,318),r_shoulder=(265,340),l_shoulder=(341,338),
   r_elbow=(215,422),r_wrist=(240,532),l_elbow=(390,427),l_wrist=(361,528),
   r_hip=(272,504),r_knee=(201,573),r_ankle=(212,680),
   l_hip=(335,504),l_knee=(402,568),l_ankle=(397,680)),
 "crouch_side":_pose("side",label="Deep crouch · side",category="crouching",
   nose=(339,251),neck=(315,305),r_shoulder=(303,336),
   r_elbow=(356,428),r_wrist=(396,508),l_shoulder=(329,343),
   l_elbow=(390,431),l_wrist=(421,516),r_hip=(273,501),
   r_knee=(360,562),r_ankle=(291,683),l_hip=(292,507),
   l_knee=(387,580),l_ankle=(316,687)),
 "sit_chair_front":_pose("front",label="Sitting on chair · front",category="sitting",
   nose=(300,175),neck=(300,244),r_shoulder=(255,263),l_shoulder=(348,261),
   r_elbow=(243,373),r_wrist=(261,461),l_elbow=(355,378),l_wrist=(345,462),
   r_hip=(259,483),r_knee=(202,553),r_ankle=(206,713),
   l_hip=(340,485),l_knee=(392,551),l_ankle=(389,713)),
 "sit_chair_side":_pose("side",label="Sitting on chair · side",category="sitting",
   nose=(347,172),neck=(324,245),r_shoulder=(311,264),l_shoulder=(333,265),
   r_elbow=(321,358),r_wrist=(350,468),l_elbow=(342,360),l_wrist=(367,464),
   r_hip=(277,486),r_knee=(397,493),r_ankle=(400,694),
   l_hip=(303,488),l_knee=(419,503),l_ankle=(421,698)),
 "sit_floor_side":_pose("side",label="Sitting on floor · side",category="sitting",
   nose=(333,278),neck=(316,341),r_shoulder=(300,364),l_shoulder=(322,367),
   r_elbow=(307,465),r_wrist=(336,557),l_elbow=(337,466),l_wrist=(363,554),
   r_hip=(260,570),r_knee=(392,602),r_ankle=(450,678),
   l_hip=(287,570),l_knee=(415,613),l_ankle=(472,680)),
 "lean_wall_side":_pose("side",label="Shoulder against wall · side",category="wall",
   nose=(348,106),neck=(323,171),r_shoulder=(307,193),l_shoulder=(329,195),
   r_elbow=(380,250),r_wrist=(437,277),l_elbow=(388,242),l_wrist=(443,267),
   r_hip=(282,424),r_knee=(280,573),r_ankle=(274,728),
   l_hip=(309,427),l_knee=(311,579),l_ankle=(323,729)),
 "lean_wall_back":_pose("back",label="Shoulder against wall · back",category="wall",
   neck=(327,169),r_shoulder=(280,190),l_shoulder=(371,190),
   r_elbow=(263,278),r_wrist=(266,374),l_elbow=(433,248),l_wrist=(474,185),
   r_hip=(279,434),r_knee=(267,573),r_ankle=(255,727),
   l_hip=(350,436),l_knee=(354,575),l_ankle=(361,731)),
 "brace_wall_side":_pose("side",label="Both hands against wall · side",category="wall",
   nose=(408,184),neck=(384,255),r_shoulder=(365,272),l_shoulder=(388,280),
   r_elbow=(438,305),r_wrist=(502,326),l_elbow=(452,332),l_wrist=(503,341),
   r_hip=(266,447),l_hip=(294,448),
   r_knee=(270,582),r_ankle=(255,728),l_knee=(298,578),l_ankle=(308,730)),
 "brace_wall_rear":_pose("back",label="Both hands against wall · rear",category="wall",
   neck=(388,257),r_shoulder=(343,284),r_elbow=(415,324),r_wrist=(482,348),
   l_shoulder=(423,284),l_elbow=(482,316),l_wrist=(521,348),
   r_hip=(268,458),r_knee=(267,578),r_ankle=(245,728),
   l_hip=(346,459),l_knee=(356,586),l_ankle=(368,728)),
 "bend_forward_side":_pose("side",label="Forward bend · side",category="bending",
   nose=(433,278),neck=(411,317),r_shoulder=(379,326),l_shoulder=(402,343),
   r_elbow=(424,422),r_wrist=(451,515),l_elbow=(444,443),l_wrist=(466,526),
   r_hip=(265,450),l_hip=(296,449),
   r_knee=(267,581),r_ankle=(247,729),l_knee=(306,578),l_ankle=(308,729)),
 "bend_forward_rear":_pose("back",label="Forward bend · rear",category="bending",
   neck=(373,316),r_shoulder=(331,329),l_shoulder=(408,327),
   r_elbow=(386,429),r_wrist=(430,532),l_elbow=(452,431),l_wrist=(477,534),
   r_hip=(261,450),r_knee=(257,579),r_ankle=(241,726),
   l_hip=(340,452),l_knee=(358,582),l_ankle=(366,726)),
 "bend_forward_front":_pose("front",label="Forward bend · front",category="bending",
   nose=(374,328),neck=(371,385),r_shoulder=(317,382),l_shoulder=(415,380),
   r_elbow=(303,480),r_wrist=(301,573),l_elbow=(444,479),l_wrist=(464,563),
   r_hip=(272,462),r_knee=(254,584),r_ankle=(244,727),
   l_hip=(344,465),l_knee=(348,585),l_ankle=(350,731)),
 "reach_down_front":_pose("front",label="Reaching down · front",category="gesture",
   nose=(307,187),neck=(305,264),r_shoulder=(262,279),l_shoulder=(355,282),
   r_elbow=(220,375),r_wrist=(206,500),l_elbow=(374,395),l_wrist=(361,573),
   r_hip=(269,452),r_knee=(263,581),r_ankle=(254,728),
   l_hip=(335,452),l_knee=(340,578),l_ankle=(350,729)),
 "look_back_over_shoulder":_pose("back",label="Looking back over shoulder",category="standing",
   nose=(357,94),neck=(301,166),r_shoulder=(249,188),
   l_shoulder=(353,190),r_elbow=(217,285),r_wrist=(207,392),
   l_elbow=(382,281),l_wrist=(390,379)),
 "lie_supine_side":_pose("side",label="Lying on back · side",category="floor",
   nose=(151,433),neck=(200,444),r_shoulder=(223,438),
   r_elbow=(300,431),r_wrist=(345,445),l_shoulder=(225,458),
   l_elbow=(304,478),l_wrist=(367,470),r_hip=(385,451),
   r_knee=(476,451),r_ankle=(550,447),l_hip=(385,477),
   l_knee=(474,487),l_ankle=(553,489)),
 "lie_prone_side":_pose("side",label="Lying face down · side",category="floor",
   nose=(152,522),neck=(203,505),r_shoulder=(227,494),
   r_elbow=(282,543),r_wrist=(345,546),l_shoulder=(225,514),
   l_elbow=(304,557),l_wrist=(367,557),r_hip=(387,493),
   r_knee=(476,501),r_ankle=(549,509),l_hip=(390,518),
   l_knee=(478,528),l_ankle=(553,540))
}

def point_list(pose_id):
    """18 2D COCO joints with absent rear-face landmarks represented by None."""
    cfg=POSES[pose_id]
    base={name:tuple(point) for name,point in zip(JOINTS[:14],BASES[cfg["base"]])}
    changes={k:tuple(v) for k,v in cfg["changes"].items()}
    # Follow the neck movement with the nose unless this pose explicitly
    # moves the head; otherwise bending gives an impossibly long neck.
    if "nose" not in changes:
        dx=changes.get("neck",base["neck"])[0]-base["neck"][0]
        dy=changes.get("neck",base["neck"])[1]-base["neck"][1]
        base["nose"]=(base["nose"][0]+dx,base["nose"][1]+dy)
    base.update(changes)
    nose=base["nose"]
    if cfg["base"]=="back" and pose_id!="look_back_over_shoulder":
        for facial in ("nose","r_eye","l_eye","r_ear","l_ear"):
            base[facial]=None
    else:
        base["r_eye"]=(nose[0]-13,nose[1]-4)
        base["l_eye"]=(nose[0]+13,nose[1]-4)
        base["r_ear"]=(nose[0]-29,nose[1]+7)
        base["l_ear"]=(nose[0]+29,nose[1]+7)
        if cfg["base"]=="side":
            base["r_eye"]=None
            base["r_ear"]=None
    return [base.get(name) for name in JOINTS]

def project(points,width,height):
    """Uniform isotropic scaling, with padding, never stretch a bent body."""
    visible=[p for p in points if p is not None]
    minx,maxx=min(x for x,y in visible),max(x for x,y in visible)
    miny,maxy=min(y for x,y in visible),max(y for x,y in visible)
    extent_x=max(1,maxx-minx)
    extent_y=max(1,maxy-miny)
    scale=min(width*.76/extent_x,height*.84/extent_y,1.6)
    offset_x=width*.5-(minx+maxx)*.5*scale
    offset_y=height*.5-(miny+maxy)*.5*scale
    return [None if p is None else
            (round(p[0]*scale+offset_x),round(p[1]*scale+offset_y))
            for p in points]

def validate_pose(pose_id):
    """Minimal geometric checks; artistic confirmation is a separate step."""
    pts=point_list(pose_id)
    if len(pts)!=18:return False
    present=[p for p in pts if p is not None]
    if len(present)<13 or len(set(present))<11:return False
    if any(not 0<=v<=800 for p in present for v in p):return False
    if pose_id.startswith("brace_wall"):
        # The extended hands must be nearer the side wall than the hips.
        if max(pts[4][0],pts[7][0])<=max(pts[8][0],pts[11][0])+70:
            return False
    if pose_id.startswith("bend_forward"):
        if abs(pts[1][0]-(pts[8][0]+pts[11][0])/2)<55:
            return False
    return True

def render_pose(pose_id,width,height):
    from PIL import Image,ImageDraw
    pts=project(point_list(pose_id),width,height)
    im=Image.new("RGB",(width,height),(0,0,0))
    draw=ImageDraw.Draw(im)
    unit=max(1,min(width/832,height/704))
    line=max(3,round(5*unit))
    radius=max(3,round(5*unit))
    for (a,b),color in zip(BONES,BONE_COLORS):
        if pts[a] is not None and pts[b] is not None:
            draw.line((pts[a],pts[b]),fill=color,width=line)
    for i,p in enumerate(pts):
        if p is not None:
            x,y=p
            draw.ellipse((x-radius,y-radius,x+radius,y+radius),fill=COLORS[i])
    return im

def pose_json(pose_id,width,height):
    pts=project(point_list(pose_id),width,height)
    data=[]
    for p in pts:
        data.extend([p[0],p[1],1.0] if p is not None else [0,0,0.0])
    return {"canvas_width":width,"canvas_height":height,
            "people":[{"pose_keypoints_2d":data}],
            "name":pose_id,"label":POSES[pose_id]["label"],
            "camera":POSES[pose_id]["base"],
            "status":"draft_requires_gpu_validation"}

def generate_library(root):
    """Keep old validated guides unchanged; produce versioned draft output."""
    from PIL import Image,ImageDraw,ImageFont
    root=Path(root)
    targets={"cg":(1216,704),"sprite":(832,1216)}
    for path in targets: (root/path).mkdir(parents=True,exist_ok=True)
    catalog=[]
    for pose_id,cfg in POSES.items():
        if not validate_pose(pose_id):raise ValueError("Invalid joints: "+pose_id)
        for domain,(width,height) in targets.items():
            out=root/domain
            render_pose(pose_id,width,height).save(out/(pose_id+".png"))
            (out/(pose_id+".json")).write_text(
                json.dumps(pose_json(pose_id,width,height),ensure_ascii=False,
                           indent=2)+"\n",encoding="utf-8")
        catalog.append({"id":pose_id,"label":cfg["label"],
                        "category":cfg["category"],"camera":cfg["base"],
                        "status":"draft_requires_gpu_validation"})
    (root/"manifest.json").write_text(json.dumps(catalog,indent=2)+"\n")
    # Human review thumbnail index, never used as a ControlNet input.
    ids=list(POSES)
    thumbw,thumbh=220,175
    cols=5
    rows=(len(ids)+cols-1)//cols
    sheet=Image.new("RGB",(cols*thumbw,rows*(thumbh+36)),(25,25,29))
    draw=ImageDraw.Draw(sheet)
    for i,pid in enumerate(ids):
        x=(i%cols)*thumbw;y=(i//cols)*(thumbh+36)
        thumb=render_pose(pid,thumbw-12,thumbh-8)
        sheet.paste(thumb,(x+6,y+4))
        draw.text((x+6,y+thumbh+3),pid,fill=(230,230,233))
    sheet.save(root/"pose-contact-sheet.png")
    return catalog

def select_story_pose(prompt):
    """Conservative selector: only exact, observable camera/action semantics.

    More generic movements and all unvalidated guides remain manual/draft.
    """
    s=str(prompt or "").lower()
    rear=any(x in s for x in ("from behind","rear view","back view","from the back"))
    side=any(x in s for x in ("side view","from the side","profile view"))
    wall=any(x in s for x in ("stone wall","brick wall","against the wall",
                               "braced on the wall","vertical wall","stone arch"))
    hands=any(x in s for x in ("both palms","both hands","palms braced",
                                "hands braced","palms planted"))
    bent=any(x in s for x in ("leans forward","leaning forward","bent forward",
                               "bending forward","leans over"))
    if wall and hands and bent and rear:return "brace_wall_rear"
    if wall and hands and bent and side:return "brace_wall_side"
    return ""

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    poses=generate_library(args.output)
    print("Generated",len(poses),"COCO-18 draft guides in",args.output)
