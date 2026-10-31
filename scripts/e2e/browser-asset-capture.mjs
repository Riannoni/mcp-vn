// Disposable, authenticated-browser diagnostic. A screenshot is NOT G2 or a
// trusted enqueue->publish receipt; source attribution must be verified elsewhere.
import crypto from "node:crypto";
import fs from "node:fs/promises";

const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SHA256=/^[0-9a-f]{64}$/i;
const KINDS=new Set(["background","sprite","scene"]);
const PNG_MAGIC=Buffer.from([137,80,78,71,13,10,26,10]);

export function validateAssetBinding(binding){
 const errors=[];
 if(!binding||typeof binding!=="object"||Array.isArray(binding))
  return ["binding_missing"];
 for(const field of ["game_id","action_id","job_id","prompt_id"])
  if(!UUID.test(binding[field]||""))errors.push("invalid_"+field);
 for(const field of ["original_png_sha256","contract_sha256"])
  if(!SHA256.test(binding[field]||""))errors.push("invalid_"+field);
 if(!KINDS.has(binding.kind))errors.push("invalid_kind");
 if(binding.kind==="sprite"&&(!Number.isInteger(binding.sprite_index)||binding.sprite_index<1||binding.sprite_index>5))
  errors.push("invalid_sprite_index");
 if(typeof binding.asset_url!=="string"||!binding.asset_url.trim())errors.push("asset_url_missing");
 return errors;
}

function selectorFor(binding){
 if(binding.kind==="background")return "#scene-background";
 if(binding.kind==="scene")return "#scene-cg";
 return "#scene-sprites img:nth-child("+binding.sprite_index+")";
}

// Requires an ALREADY authenticated Playwright Page on an explicitly disposable
// game. Does not click, submit, login, enqueue, publish, or call model endpoints.
// No result of this function can establish independent G2 or a full-turn E2E.
export async function captureDisposableBrowserAsset(page,binding,{capture_path}={}){
 const bad=validateAssetBinding(binding);
 if(bad.length)throw Error("Unbound asset: "+bad.join(","));
 if(typeof capture_path!=="string"||!capture_path.endsWith(".png"))throw Error("Private PNG capture path required");
 if(!page||typeof page.url!=="function"||typeof page.evaluate!=="function"||
    typeof page.locator!=="function")throw Error("Authenticated Playwright Page required");
 const origin=new URL(await page.url());
 if(!/^https?:$/.test(origin.protocol))throw Error("Unsupported page protocol");
 const asset=new URL(binding.asset_url,origin);
 if(asset.origin!==origin.origin)throw Error("Cross-origin asset refused");
 if(!/^\/assets\/[0-9a-f-]{36}\.png$/i.test(asset.pathname))
  throw Error("Asset is not a project PNG path");
 const selector=selectorFor(binding);
 const expected=asset.href;
 const observation=await page.evaluate(async ({selector,expected,gameId,kind})=>{
  const fail=reason=>({ok:false,reason});
  const app=document.getElementById("app");
  if(!app||app.hidden||document.visibilityState!=="visible")return fail("document_not_visible");
  if(document.getElementById("save")?.value!==gameId)return fail("different_save");
  const element=document.querySelector(selector);
  if(!element||!element.isConnected)return fail("image_missing");
  const visible=()=>{
   if(element.hidden||document.getElementById("app")?.hidden)return false;
   const s=getComputedStyle(element),r=element.getBoundingClientRect();
   return s.display!=="none"&&s.visibility==="visible"&&Number(s.opacity)>0&&r.width>0&&r.height>0;
  };
  const source=()=>{
   if(kind!=="background")return element.currentSrc||element.src||"";
   const css=getComputedStyle(element).backgroundImage;
   if(!css.startsWith("url(")||!css.endsWith(")"))return "";
   return css.slice(4,-1).trim().replace(/^["']|["']$/g,"");
  };
  const matches=()=>{
   try{return new URL(source(),location.href).href===expected}
   catch{return false}
  };
  if(!visible())return fail("image_not_displayed");
  if(!matches())return fail("asset_url_mismatch");
  try{
   if(kind==="background"){
    const probe=new Image();probe.src=expected;await probe.decode();
    if(!probe.naturalWidth||!probe.naturalHeight)return fail("background_decode_empty");
   }else{
    await element.decode();
    if(!element.complete||!element.naturalWidth||!element.naturalHeight)return fail("image_decode_empty");
   }
  }catch{return fail("decode_failed")}
  await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  if(!visible()||!matches()||document.visibilityState!=="visible"||
     document.getElementById("save")?.value!==gameId)return fail("changed_before_capture");
  return {ok:true,epoch_ms:Date.now(),performance_ms:performance.now(),
   browser_time_origin_ms:performance.timeOrigin};
 },{selector,expected,gameId:binding.game_id,kind:binding.kind});
 if(!observation?.ok)throw Error("Browser capture refused: "+(observation?.reason||"unknown"));
 const shot=await page.locator(selector).screenshot({timeout:5000,animations:"disabled"});
 if(!Buffer.isBuffer(shot)||shot.length<=PNG_MAGIC.length||
    !shot.subarray(0,PNG_MAGIC.length).equals(PNG_MAGIC))throw Error("Screenshot is not a PNG");
 // Never overwrite an existing screenshot, particularly a canonical/private one.
 await fs.writeFile(capture_path,shot,{flag:"wx",mode:0o600});
 return {
  status:"SCREENSHOT_CAPTURED_UNVERIFIED",original_pixels_reviewed:false,
  browser_visible_verified:false,g2:"NOT_REVIEWED",full_turn:"NOT_MEASURED",
  game_id:binding.game_id,action_id:binding.action_id,job_id:binding.job_id,
  prompt_id:binding.prompt_id,contract_sha256:binding.contract_sha256,
  claimed_original_png_sha256:binding.original_png_sha256.toLowerCase(),
  screenshot_sha256:crypto.createHash("sha256").update(shot).digest("hex"),
  asset_url_sha256:crypto.createHash("sha256").update(expected).digest("hex"),
  screenshot_epoch_ms:observation.epoch_ms,
  browser_performance_ms:observation.performance_ms,
  browser_time_origin_ms:observation.browser_time_origin_ms,
  limitations:["producer_lineage_not_authenticated","screenshot_pixels_not_independently_reviewed",
   "capture_is_not_enqueue_to_eligible","browser_paint_not_proven_by_raf"]
 };
}
