"""Classify previous QA failure and make an actually targeted next attempt.

This is deterministic and intentionally conservative. A new seed alone is
not a recovery policy. No automatic QA bypass.
"""
import re

def retry_plan(job):
    attempt=max(1,int(job.get("attempts") or 1))
    if attempt<=1:return {"category":"first_attempt","positive":"","negative":"",
                         "control_strength":0.78,"control_end":0.86}
    error=str(job.get("error") or "").lower()
    kind=job.get("kind") or ""
    if "multi-panel collage" in error:
        category="panel_layout"
        positive=("RETRY COMPOSITION CORRECTION: one continuous cinematic scene, "
                  "one camera viewpoint, one complete uninterrupted frame. "
                  "Render the named cast exactly once with no repeated views.")
        negative=("four-panel sheet, split screen, storyboard, comic panels, "
                  "contact sheet, repeated poses, tiled collage, multiple frames")
    elif "pose" in error or "geometry" in error or "required joints" in error:
        category="pose_geometry"
        positive=("RETRY POSE CORRECTION: the previous body geometry was wrong. "
                  "Follow the approved physical skeleton more closely. "
                  "Show correct supporting limbs and the intended body orientation.")
        negative="incorrect body pose, unsupported limbs, kneeling instead of standing"
    elif ("wall contact" in error or "wall-contact" in error or
          "scene action" in error or "action mismatch" in error):
        category="physical_contact"
        positive=("RETRY CONTACT CORRECTION: show the physical interaction "
                  "unambiguously in one frame. Keep hands and contacted "
                  "surface jointly visible at a readable camera angle.")
        negative="hands hidden behind body, floating hands, unsupported gesture, ambiguous physical contact"
    elif ("wardrobe" in error or "clothing" in error or "outfit" in error):
        category="wardrobe"
        positive=("RETRY WARDROBE CORRECTION: honor the current scene wardrobe "
                  "state instead of the outfit in the canonical identity reference.")
        negative="stale outfit, old costume carried over from reference"
    elif ("identity" in error or "face similarity" in error or
          "canonical anchor" in error):
        category="identity"
        positive="RETRY IDENTITY CORRECTION: match the canonical facial traits and hair; no face swap."
        negative="different face, identity drift, face swap, wrong hairstyle"
    elif ("location" in error or "forest" in error or
          "market square" in error or "environment" in error):
        category="environment"
        positive="RETRY SETTING CORRECTION: the stated location must be identifiable in this shot."
        negative="unrelated place, wrong architectural context, alternate setting"
    elif ("multiple" in error or "principal figure" in error or
          "person count" in error or "duplicate" in error):
        category="cardinality"
        positive="RETRY CAST CORRECTION: preserve each named principal exactly once without cloned bodies."
        negative="duplicated main character, mirrored extra person, double exposure"
    elif kind=="sprite" and ("alpha" in error or "transparent" in error or "background" in error):
        category="sprite_cutout"
        positive="RETRY CUTOUT CORRECTION: single full-length character on plain uniform neutral matte."
        negative="detailed scene background, cropped full body"
    else:
        category="unclassified"
        positive="";negative=""
    # Stronger control is useful only for actual pose geometry errors.
    strength = (0.90 if attempt==2 else 1.0) if category=="pose_geometry" else 0.78
    end = (0.95 if attempt==2 else 1.0) if category=="pose_geometry" else 0.86
    return {"category":category,"positive":positive,"negative":negative,
            "control_strength":strength,"control_end":end}

def permanent_render_failure(error):
    text=str(error or "").lower()
    # Errors that cannot be resolved by choosing another random seed.
    patterns=(
      "required wall-contact dwpose unavailable",
      "required pose reference disabled",
      "approved dwpose was selected but controlnet is disabled",
      "approved dwpose controlnet could not be applied",
      "canonical face/reference missing",
      "canonical face reference cannot be loaded",
      "incompatible engine contract",
      "cannot anchor ",
      "required pose reference",
    )
    return any(phrase in text for phrase in patterns)
