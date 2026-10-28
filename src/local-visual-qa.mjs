// Independent technical quality contract for local full-frame CG previews.
// A "done" PNG is not automatically a faithful depiction of the novel.
// This helper controls seed reuse and optional video; it does not inspect
// content categories or change any existing narrative or generative prompts.
const flat=x=>String(x??"").replace(/\s+/gu," ").trim();

export function groundedLocalFrame(job,{sessionId,visualState=null,forVideo=false}={}){
 if(!job||job.kind!=="local_cg"||job.status!=="done")
  return {ok:false,reason:"No completed local CG"};
 const spec=job.spec||{},qa=job.qa||{},metrics=qa.metrics||{};
 if(!spec.preview_only||spec.composition!=="neural_story")
  return {ok:false,reason:"Not a full-frame neural preview"};
 if(!sessionId||spec.local_session_id!==sessionId)
  return {ok:false,reason:"Scene belongs to a different episode"};
 if(!job.file||!job.asset_url)
  return {ok:false,reason:"Published image is missing"};
 if(!qa.passed||qa.semantic_status!=="passed")
  return {ok:false,reason:"Image quality review did not pass"};
 if(metrics.scene_count_verified!==true)
  return {ok:false,reason:"Principal characters were not independently verified"};
 if(metrics.scene_location_verified!==true)
  return {ok:false,reason:"Scene location was not independently verified"};
 const prior=spec.local_visual_state||{};
 if(visualState){
  for(const key of ["location","environment","activity"]){
   if(flat(prior[key])!==flat(visualState[key]))
    return {ok:false,reason:key+" changed"};
  }
  const a=prior.characters||[],b=visualState.characters||[];
  if(a.length!==b.length)
   return {ok:false,reason:"Visible cast changed"};
  for(let i=0;i<a.length;i++){
   for(const key of ["name","outfit","equipment","action","pose"]){
    if(flat(a[i][key])!==flat(b[i][key]))
     return {ok:false,reason:"Character "+key+" changed"};
   }
  }
  // A verified picture becomes stale after a new action or viewpoint.
  // Video must also begin from the current pose and framing.
  if(flat(prior.camera)!==flat(visualState.camera))
   return {ok:false,reason:"Camera viewpoint changed"};
 }
 return {ok:true,reason:"Verified scene, characters and location"};
}
