#!/usr/bin/env python3
"""Optional local CPU VLM quality judge. Returns bounded JSON; never uploads images."""
import json
import re
import sys
import time
from pathlib import Path

def output(**data):
    print(json.dumps(data,ensure_ascii=False),flush=True)

def main():
    if len(sys.argv)!=3:
        output(status="unavailable",reason="usage: vision_qa.py kind image_path");return
    kind,image_path=sys.argv[1],Path(sys.argv[2])
    spec=json.loads(sys.stdin.read() or "{}")
    import torch
    from PIL import Image
    from transformers import AutoProcessor,AutoModelForImageTextToText

    torch.set_num_threads(6)
    model_id="HuggingFaceTB/SmolVLM2-500M-Video-Instruct"
    t0=time.monotonic()
    processor=AutoProcessor.from_pretrained(model_id)
    model=AutoModelForImageTextToText.from_pretrained(
        model_id,dtype=torch.float32,attn_implementation="eager").eval()
    image=Image.open(image_path).convert("RGBA")
    if image.getchannel("A").getextrema()!=(255,255):
        matte=Image.new("RGBA",image.size,(120,120,120,255))
        matte.alpha_composite(image)
        image=matte
    image.thumbnail((672,672),Image.Resampling.LANCZOS)
    if kind=="sprite":
        prompt=("Describe this image in one short sentence: how many people are visible, "
                "what colors and types of clothing are visibly worn, and what is behind them? "
                "Report only visible details, no guesses.")
    elif kind=="scene":
        prompt=("Describe the architecture and surroundings in this fantasy scene. "
                "Also say how many people are visible and what clothing they appear to wear. "
                "Answer factually in one or two short sentences, no speculation.")
    else:
        prompt=("Describe the architecture, environment, or landscape in this image. "
                "Also say whether any people are visible. Use one factual sentence.")
    messages=[{"role":"user","content":[{"type":"image","image":image.convert("RGB")},
                 {"type":"text","text":prompt}]}]
    inputs=processor.apply_chat_template(messages,add_generation_prompt=True,
        tokenize=True,return_dict=True,return_tensors="pt")
    with torch.inference_mode():
        generated=model.generate(**inputs,max_new_tokens=115,do_sample=False)
    tokens=generated[:,inputs["input_ids"].shape[1]:]
    caption=processor.batch_decode(tokens,skip_special_tokens=True)[0].strip()
    desc=caption.lower()
    reasons=[]
    warnings=[]
    # A small vision model may confuse color in complex light; report inferred
    # palette differences as advisory unless the prompt explicitly demands a color.
    colors={
      "green":("green","зелён","зелен"),
      "red":("red","красн"),
      "blue":("blue","син","голуб"),
      "brown":("brown","коричн"),
      "black":("black","черн","чёрн"),
      "white":("white","бел"),
      "purple":("purple","фиолет"),
      "yellow":("yellow","желт","жёлт"),
      "gray":("gray","grey","сер"),
    }
    def expected_color(haystack):
        t=str(haystack or "").lower()
        for code,words in colors.items():
            if any(word in t for word in words):
                return code
        return None
    def observed_cloak_color(caption):
        found=re.search(r"\b(green|red|blue|brown|black|white|purple|yellow|gray|grey)\s+"
                        r"(?:\w+\s+){0,2}(?:cloak|cape|robe|coat|jacket)\b",caption)
        return found.group(1).replace("grey","gray") if found else None
    # A compact model is advisory: block only very explicit contradictions.
    num_expected=len(spec.get("characters") or [])
    if kind=="sprite":
        if re.search(r"\b(?:two|three|four|several|multiple|many)\s+(?:people|persons|women|men|characters)\b",desc):
            reasons.append("Visual QA found multiple characters in a single sprite")
        if re.search(r"\b(?:no people|no person|nobody|empty of people)\b",desc):
            reasons.append("Visual QA found no character")
        requested=str(spec.get("prompt","")).lower()
        wants_no_clothes=bool(re.search(r"\b(?:nude|naked|unclothed|fully nude)\b|обнажен|обнажён|без одежды|раздеться|раздет",requested))
        clothing=bool(re.search(r"\b(?:wearing|dressed in|clad in)\s+.{0,28}\b(?:bra|bikini|armor|armour|dress|shirt|pants|coat|cloak|lingerie|outfit)\b",desc))
        if wants_no_clothes and clothing:
            reasons.append("Visual QA reports clothing where an unclothed subject was requested")
        target=expected_color(spec.get("prompt","")) or expected_color(spec.get("appearance",""))
        observed=observed_cloak_color(desc)
        if target and observed and target!=observed:
            warning=f"Appearance color may be inconsistent: expected {target}, image described as {observed}"
            warnings.append(warning)
            # Strict prompt requirements have priority over low-confidence generated traits.
            if expected_color(spec.get("prompt",""))==target and "cloak" in str(spec.get("prompt","")).lower():
                reasons.append(warning)
    elif kind=="scene":
        if num_expected>0 and re.search(r"\b(?:no people|no person|nobody|empty of people)\b",desc):
            reasons.append("Scene CG omitted expected characters")
    elif kind=="background":
        if re.search(r"\b(?:two|three|several|multiple)\s+(?:people|persons|women|men)\b",desc):
            reasons.append("Background contains multiple unwanted characters")
    output(status="failed" if reasons else "passed",reasons=reasons,warnings=warnings,
        caption=caption[:300],duration_seconds=round(time.monotonic()-t0,1),model=model_id)

if __name__=="__main__":
    try:main()
    except Exception as error:
        output(status="unavailable",reason=str(error)[:250])
