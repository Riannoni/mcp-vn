// Prompt enhancer for ComfyUI / SDXL / Pony / WAI / Anima.
// Takes visual state or narrator-provided prompts and adds quality tags,
// style-specific boosters, better negatives, and NSFW-aware descriptors.

const QUALITY = {
  pony: "masterpiece, best quality, highres, absurdres, very aesthetic, detailed skin, detailed eyes, sharp focus",
  wai: "masterpiece, best quality, high quality, very aesthetic, detailed, sharp focus",
  anima: "masterpiece, best quality, highly detailed, sharp focus, vibrant colors"
};

const NEGATIVE_BASE = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry, artist name, extra limbs, malformed limbs, mutated hands, poorly drawn hands, poorly drawn face, mutation, deformed, ugly, bad proportions, extra arms, extra legs, fused fingers, too many fingers, long neck, disfigured, gross proportions, missing arms, missing legs, extra arms, extra legs, mutated, (bad anatomy:1.3), (bad hands:1.3)";

const NSFW_BOOST = "nsfw, explicit, detailed genitalia, detailed nipples, soft lighting, intimate atmosphere";

export function enhancePrompt({style = "realistic", positive = "", negative = "", isNsfw = false, visualState = null} = {}) {
  const styleKey = style === "anime" ? "wai" : style === "animation" ? "anima" : "pony";
  const q = QUALITY[styleKey] || QUALITY.pony;

  let pos = String(positive || "").trim();
  if (visualState && !pos) {
    // Build from visual state if no narrator prompt given
    const chars = (visualState.characters || []).map(c => {
      const parts = [c.name, c.outfit, c.pose, c.expression, c.action].filter(Boolean);
      return parts.join(", ");
    }).join(", ");
    pos = [visualState.location, visualState.environment, visualState.camera, visualState.lighting, visualState.activity, chars].filter(Boolean).join(", ");
  }

  if (isNsfw) pos = `${pos}, ${NSFW_BOOST}`;
  pos = `${q}, ${pos}`.replace(/\s+/g, " ").trim();

  const neg = `${NEGATIVE_BASE}${negative ? ", " + negative : ""}`.replace(/\s+/g, " ").trim();

  return { positive: pos, negative: neg, styleKey };
}

export function isLikelyNsfw(text = "") {
  return /nude|naked|sex|fuck|cock|pussy|breast|nipple|cum|orgasm|nsfw|explicit|penetration|undress|bare|обнаж|раздет|секс|член|киска|грудь|сосок/i.test(String(text));
}
