"""Named, composable pose descriptions for VN story planning.

These are LANGUAGE/SCENE contracts, NOT approved DWPose guides. A pose
description must never by itself trigger an unrelated hard ControlNet map.
Each actor may have an independent pose, including in a multi-person scene.
"""
from __future__ import annotations

# id -> (support, contact, short physical pose description)
POSE_CONTRACTS = {
 "stand_front":("feet","none","upright standing, both feet supporting the body, front view"),
 "stand_side":("feet","none","upright standing in profile, both feet supporting the body"),
 "stand_back":("feet","none","upright standing with back to viewer"),
 "stand_three_quarter":("feet","none","relaxed three-quarter standing posture"),
 "stand_arms_crossed":("feet","arms","upright stance, both forearms crossed over chest"),
 "stand_hands_hips":("feet","hips","upright stance, both hands on hips"),
 "stand_arms_raised":("feet","none","upright stance, both arms raised overhead"),
 "stand_look_over_shoulder":("feet","none","upright stance, head turned to look over one shoulder"),
 "stand_point":("feet","none","upright stance, one arm extended to point"),
 "stand_wave":("feet","none","upright stance, one hand raised in a wave"),
 "walk":("feet","none","walking naturally in the narrated direction with alternating gait"),
 "run":("feet","none","running naturally in the narrated direction with dynamic gait"),
 "sit":("seat","seat","sitting with hips supported by the narrated seat or surface"),
 "kneel":("knees","floor","kneeling with one or both knees as specified by the narration"),
 "point":("unspecified","none","one arm extending to point, posture determined by narration"),
 "walk_front":("feet","none","walking toward viewer, one foot forward, natural arm swing"),
 "walk_side":("feet","none","walking in profile, natural mid-step gait"),
 "walk_back":("feet","none","walking away from viewer, natural step"),
 "run_front":("feet","none","running toward viewer with natural arm swing"),
 "run_side":("feet","none","running in profile with athletic mid-stride"),
 "sit_chair_front":("seat","chair","seated upright on chair, knees bent, feet on floor"),
 "sit_chair_side":("seat","chair","seated sideways on chair, feet on floor"),
 "sit_floor":("floor","floor","seated on ground, hips supported by floor"),
 "sit_cross_legged":("floor","floor","seated cross-legged on ground"),
 "kneel_one":("knee_and_foot","ground","one knee on ground, opposite foot planted"),
 "kneel_both":("knees","ground","kneeling on both knees, torso balanced upright"),
 "crouch":("feet","none","low squat, bent knees, feet planted"),
 "squat":("feet","none","balanced deep squat with weight on both feet"),
 "bend_forward":("feet","none","standing while torso bends forward at hips"),
 "reach_down":("feet","none","standing with one hand reaching toward ground"),
 "reach_up":("feet","none","standing with one arm extended upward"),
 "lean_wall_shoulder":("feet_and_shoulder","wall","standing with shoulder leaning against vertical wall"),
 "lean_wall_palm_side":("feet_and_palms","wall","standing with palms against vertical wall, side view"),
 "lean_wall_palm_rear":("feet_and_palms","wall","standing with palms against vertical wall, rear view"),
 "hinge_wall_side":("feet_and_palms","wall","standing, torso hinged forward at hips, palms against wall, side view"),
 "hinge_wall_rear":("feet_and_palms","wall","standing, torso hinged forward at hips, palms against wall, rear three-quarter view"),
 "lie_back":("back","floor","lying on back on horizontal surface"),
 "lie_side":("side","floor","lying on side on horizontal surface"),
 "lie_prone":("torso","floor","lying face down on horizontal surface"),
 "turn_around":("feet","none","turning upper body and head over shoulder while standing"),
 "hug":("feet","other_person","standing while embracing another person"),
 "handshake":("feet","other_person","standing and shaking hands with another person"),
}
POSE_ALIASES={
 "standing":"stand_three_quarter","arms_crossed":"stand_arms_crossed",
 "hands_on_hips":"stand_hands_hips", "turning_around":"turn_around",
 "walking":"walk","running":"run","seated":"sit",
 "kneeling":"kneel","crouching":"crouch","pointing":"point",
 "leaning_against_wall":"lean_wall_shoulder",
 "turned_and_leaning_forward":"bend_forward",
}
def pose_contract(pose):
    key=str(pose or "").strip().lower().replace(" ","_").replace("-","_")
    key=POSE_ALIASES.get(key,key)
    if key not in POSE_CONTRACTS:
        return None
    support,contact,description=POSE_CONTRACTS[key]
    return {"id":key,"support":support,"contact":contact,"description":description,
            "status":"text_contract_only",
            "approved_control":False}
