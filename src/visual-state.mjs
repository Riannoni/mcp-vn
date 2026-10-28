// Persist the *requested* appearance separately from what a PNG actually depicts.
// This module has no I/O, so both gameplay and art scheduling share the same rule.
const norm=(value,fallback)=>String(value??fallback).trim()||fallback;
export function variantKey({art_style="realistic",outfit="default",pose="standing",emotion="neutral"}={}){
 return [norm(art_style,"realistic"),norm(outfit,"default"),norm(pose,"standing"),norm(emotion,"neutral")].join("|");
}
export function assetId(url){
 if(!url)return "";
 try{return new URL(url).pathname.split("/").pop()||""}catch{return ""}
}
export function variantOfImage(identity,url){
 if(!identity||!url)return "";
 const target=assetId(url);
 for(const [key,asset] of Object.entries(identity.variants||{}))
  if(assetId(asset)===target&&target)return key;
 return "";
}
export function visualFingerprint(scene){
 const sprites=(scene?.sprites||[]).map(s=>[
   norm(s.name,""),assetId(s.image_url),
   s.rendered_variant_key||"",s.visual_dirty===true?"dirty":"ready"
 ].join("#"));
 const revision=Number.isSafeInteger(scene?.cg_revision)&&scene.cg_revision>0?
  "cg_revision:"+scene.cg_revision:"";
 return [assetId(scene?.background_url),...sprites,...(revision?[revision]:[])].join(";");
}
export function normalizeSprite(sprite={},identity={},sceneBackground="",gameStyle=""){
 const s={...sprite};
 s.art_style=norm(s.art_style||identity?.base_style,"realistic");
 s.outfit=norm(s.outfit,"default");
 s.pose=norm(s.pose,"standing");
 s.emotion=norm(s.emotion,"neutral");
 s.desired_variant_key=variantKey({...s,art_style:gameStyle||s.art_style});
 const provenance=variantOfImage(identity,s.image_url);
 s.rendered_variant_key=
   (s.rendered_variant_key&&assetId(s.rendered_image_url||s.image_url)===assetId(s.image_url)
      ?s.rendered_variant_key:"")||provenance||"";
 const key=s.rendered_variant_key;
 const backgrounds=identity?.variant_backgrounds||{};
 s.rendered_background_asset=norm(s.rendered_background_asset||backgrounds[key]||"","");
 const environmentChanged=!!sceneBackground&&s.rendered_background_asset!==assetId(sceneBackground);
 s.visual_dirty=!s.image_url||s.transparent!==true||
   s.desired_variant_key!==key||environmentChanged;
 s.visual_status=s.visual_dirty?"stale":"ready";
 return s;
}
export function normalizeVisualState(g){
 if(!g?.scene)return g;
 const scene=g.scene;
 scene.background_dirty=!!scene.background_url&&
   (!!g.art_style&&scene.background_style!==g.art_style);
 scene.sprites=(scene.sprites||[]).map(s=>
   normalizeSprite(s,g.identities?.[s.name]||{},scene.background_url,g.art_style));
 if(scene.cg_url){
   scene.cg_dirty=scene.background_dirty||!!(g.art_style&&scene.cg_style!==g.art_style)||
     scene.sprites.some(s=>s.visual_dirty)||
      !scene.cg_basis||scene.cg_basis!==visualFingerprint(scene);
   if(scene.cg_dirty&&scene.mode==="cg")scene.mode="layered";
 }else{
   scene.cg_dirty=false;
   if(scene.mode==="cg")scene.mode="layered";
 }
 return g;
}
