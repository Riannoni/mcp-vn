"""Clothing-state helpers shared by the art worker and the vision QA."""
import re

_UNCLOTHED=re.compile(
    r"\b(?:fully\s+(?:undressed|unclothed|nude|naked)|"
    r"completely\s+(?:undressed|unclothed|nude|naked)|"
    r"unclothed|nude|naked|undressed|no\s+clothes|without\s+clothes)\b"
    r"|(?:полностью\s+)?(?:обнажен[а-я]*|раздет[а-я]*)|без\s+одежды",re.I)
_NEGATED=re.compile(r"\b(?:not|never|no\s+longer)\s+(?:fully\s+)?(?:nude|naked|undressed|unclothed)\b",re.I)
_NO_GARMENTS=re.compile(
    r"\b(?:no\s+(?:visible\s+)?(?:clothes|clothing|garments|apparel|attire)|"
    r"without\s+(?:any\s+)?(?:clothes|clothing|garments|attire)|"
    r"not\s+wearing\s+(?:any\s+)?(?:clothes|clothing|garments)|"
    r"wearing\s+nothing|unclothed|nude|naked)\b",re.I)
_GARMENT=re.compile(
    r"\b(?:bra|bikini|dress|cloak|coat|shirt|jacket|armor|armour|robe|"
    r"skirt|pants|trousers|boots|belt|vest|underwear|lingerie|shorts|swimsuit|"
    r"top|bottoms|stockings|tunic)\b",re.I)
_WORN=re.compile(r"\b(?:wearing|dressed\s+in|clad\s+in|wears)\b",re.I)
_HELD=re.compile(r"\b(?:holding|carrying|on\s+(?:her|his|their)\s+arm|in\s+(?:her|his|their)\s+hand)\b",re.I)

def wants_unclothed(outfit):
    text=str(outfit or "").strip()
    return bool(_UNCLOTHED.search(text) and not _NEGATED.search(text))

def clothing_alignment(caption):
    """Return failed / passed / uncertain for a requested unclothed appearance.

    Captions are advisory unless they explicitly say no garments are worn.
    The mere presence of a garment name can describe clothing held off-body.
    """
    text=str(caption or "").lower()
    explicitly_bare=bool(_NO_GARMENTS.search(text))
    garment=bool(_GARMENT.search(text))
    worn=bool(_WORN.search(text))
    held=bool(_HELD.search(text))
    if garment and (worn or not held) and not (explicitly_bare and not worn):
        return "failed"
    if explicitly_bare and not (garment and worn):
        return "passed"
    return "uncertain"


# Select a *worn* upper garment; never take a palette color from
# the description of a removed, prohibited or previous garment.
_WARDROBE_EXCLUSION=re.compile(
    r"^\s*(?:no|without|not\s+wearing|removed|discarded|old|previous)\b",re.I)
_OUTERWEAR_COLOR=re.compile(
    r"\b(?P<color>black|white|green|red|blue|brown|purple|yellow|grey|gray)\b"
    r"[-\w\s]{0,45}?\b(?:jacket|cloak|cape|coat|tunic|shirt|dress|robe|vest|"
    r"blouse|sweater|armor|armour)\b",re.I)

def requested_outerwear_color(outfit):
    """Return primary upper-garment color without counting old/removed outfits.

    This is a conservative lexical observation, not visual proof of garment
    correctness. If no positively worn garment is specified, return None.
    """
    description=str(outfit or "")
    if wants_unclothed(description):
        return None
    segments=[segment for segment in re.split(r"[;,]",description)
              if not _WARDROBE_EXCLUSION.search(segment)]
    for segment in segments:
        match=_OUTERWEAR_COLOR.search(segment)
        if match:
            return "gray" if match["color"].lower()=="grey" else match["color"].lower()
    return None
