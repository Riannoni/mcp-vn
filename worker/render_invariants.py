"""Non-negotiable rendering invariants for narrator-authored image prompts.

Narration controls the creative shot, but cannot erase the type-specific
contract (transparent isolated sprite, empty environment plate, etc).
No game identifiers, character names or game lore are hard-coded here.
"""
from __future__ import annotations
from pose_presets import pose_prompt


def allow_sprite_body_img2img(spec):
    """Use full-body source only for a canonical default outfit.

    A face reference is independent of the garment; copying a prior full-body
    image for an explicit alternate outfit causes clothing and pose leakage.
    This errs on the side of a fresh latent rather than a stale body image.
    """
    if not isinstance(spec,dict):
        return False
    outfit=str((spec.get("variant") or {}).get("outfit","default")).strip().lower()
    return outfit=="default" and bool(
        spec.get("anchor_asset") or spec.get("previous_sprite_asset"))

def narrator_invariants(job):
    spec=job.get("spec") or {}
    kind=job.get("kind")
    env=spec.get("environment") or {}
    location=str(spec.get("location") or "")
    positive_env=", ".join(str(x)[:140] for x in (env.get("positive") or [])[:8])
    negative_env=", ".join(str(x)[:140] for x in (env.get("negative") or [])[:8])
    if kind=="background":
        positive=("REQUIRED ENVIRONMENT PLATE: coherent single location; "
                  +("exact physical setting: "+positive_env+". " if positive_env else "")
                  +("Scene: "+location[:180]+". " if location else "")
                  +"Wide establishing view with usable spatial depth. "
                   "No named actors, no foreground character portraits, "
                   "no character silhouettes blocking the setting.")
        negative="character portrait, foreground person, cropped face, person centered in frame, duplicate scenery"
        if negative_env:negative+=", "+negative_env
        return positive,negative
    if kind=="sprite":
        variant=spec.get("variant") or {}
        actor=str(job.get("character") or "")[:100]
        outfit=str(variant.get("outfit") or "default")[:180]
        pose=str(variant.get("pose") or "standing")[:180]
        expression=str(variant.get("emotion") or "neutral")[:90]
        positive=("ISOLATED SPRITE CONTRACT: exactly one established adult actor "
                  +actor+". Full-length body from head to feet in frame, "
                  "plain uniform gray background suitable for alpha extraction, "
                  "no scene props or architecture. "
                  "Facial identity must match the canonical character. "
                  "Current wardrobe is "+outfit+"; do not copy old garments "
                  "from a face reference. Required pose: "+pose_prompt(pose)[:500]+
                  ". Expression: "+expression+".")
        negative=("multiple figures, duplicate person, missing head, cropped feet, "
                  "interior, architecture, street, landscape, cluttered backdrop, "
                  "text, logo, watermark")
        return positive,negative
    if kind=="scene":
        actors=spec.get("characters") or []
        names=", ".join(str(x.get("name") or "")[:80] for x in actors)
        positive=("CG CONTINUITY CONTRACT: "+str(len(actors))+
                  " established principal characters ("+names+"); "
                  "one coherent shot, no duplicated principal identities. "
                  "Keep the canonical facial identity for each actor while "
                  "following the narrated pose and CURRENT wardrobe. "
                  "Never copy an earlier sprite's body posture into the shot. "
                  "Correct camera and depth perspective. "
                  +("Required location: "+positive_env+". " if positive_env else "")
                  )
        negative="duplicate identity, multiple copies of same actor, collage, pasted portrait, watermark"
        if negative_env:negative+=", "+negative_env
        return positive,negative
    return "",""
