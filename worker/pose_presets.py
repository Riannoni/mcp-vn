"""Human-readable shot planning for repeatable VN character poses.
Descriptive geometry rather than underscored tokens or contradictory 'standing' prompts.
"""
POSES = {
 "standing": (
  "natural full-body upright standing posture, feet on imaginary ground, relaxed shoulders, "
  "front-facing three-quarter view"
 ),
 "turned_and_leaning_forward": (
  "three-quarter back view with hips and shoulders visibly turned away from camera; "
  "torso bending forward at the waist about 35 degrees to investigate a small object near the feet; "
  "neck angled to look down, bent arms placed naturally, weight balanced on two legs"
 ),
 "turning_around": (
  "three-quarter back view, shoulders rotating while the head looks over one shoulder"
 ),
 "walking": (
  "mid-stride walking pose, one foot forward, natural opposing arm swing, slight movement in hair"
 ),
 "running": (
  "full-body dynamic mid-run pose, one leg reaching forward and the other pushing behind, "
  "slight forward movement and strong natural arm swing"
 ),
 "seated": (
  "sitting on a simple unobtrusive stool, bent hips and knees approximately 90 degrees, "
  "feet planted naturally, straight torso"
 ),
 "leaning_against_wall": (
  "standing with one shoulder leaning lightly against an implied wall, bent elbow and relaxed hip"
 ),
 "kneeling": (
  "one knee on ground with other leg bent upright, torso balanced over hips, hands resting naturally"
 ),
 "crouching": (
  "low squat with deeply bent knees, balanced feet, body inclined slightly forward"
 ),
 "arms_crossed": (
  "full-body relaxed standing, both forearms folded across chest, shoulders lowered"
 ),
 "pointing": (
  "body turned three quarters toward the scene, one arm extended to point at something off-camera"
 )
}
# Curated CharacterPose/Mixamo benchmark guides. Only A/B-validated classes
# are enabled. A custom unsupported pose uses prompt guidance as before.
POSE_CONTROL_GUIDES = {
 "running": "running.png",
 "running_fast": "running.png",
 "kneeling": "kneeling.png",
}
def pose_control_guide(pose):
    return POSE_CONTROL_GUIDES.get(str(pose or "").strip().lower(), "")

def pose_prompt(pose):
    text = str(pose or "standing").strip().lower()
    if text in POSES:
        return POSES[text]
    return ("human full-body pose: " + text.replace("_", " ").replace("-", " ") +
            "; anatomically plausible movement and limb positions")
def wants_fresh_latent(pose, has_face_anchor):
    return bool(has_face_anchor and str(pose or "standing").lower() not in (
        "standing","arms_crossed"))
