// Narrow incremental updates for an already-open VN. Full game state is sent
// only on initial open or when the client has lost its message cursor.
const concise=(v,n=350)=>String(v??"").slice(0,n);
export function makeGameDelta(g,{known_version=0,known_messages=0,known_last_id=""}={}){
 if(g.version===known_version)return null;
 const count=Number(known_messages);
 if(!Number.isInteger(count)||count<1||count>g.messages.length||
   g.messages[count-1]?.id!==known_last_id){
   return {version:g.version,full_reload_required:true};
 }
 return {
   version:g.version,updated_at:g.updated_at,
   awaiting_narrator:!!g.awaiting_narrator,
   new_messages:g.messages.slice(count),
   scene:g.scene,choices:g.choices||[],
   flags:g.flags||{},inventory:g.inventory||[],
   relationships:g.relationships||{},rules:g.rules||{mode:"narrative"},
   identities:g.identities||{},
   turn_metrics:g.turn_metrics||null,
   local_scene:g.local_scene||{mode:"main"},
   undo_count:g.undo_stack?.length||0,
   memory_stats:{
     chapters:g.memory?.chapters?.length||0,facts:g.memory?.facts?.length||0,
     quests:g.memory?.quests?.length||0
   }
 };
}
export function compactJob(job){
 return {
  id:job.id,game_id:job.game_id,status:job.status,stage:job.stage,
  kind:job.kind,character:concise(job.character,100),style:job.style,
  progress:job.progress||0,attempts:job.attempts||0,
  created_at:job.created_at,claimed_at:job.claimed_at,finished_at:job.finished_at,
  applied:job.applied,library_stored:job.library_stored,
  asset_url:job.spec?.preview_only?job.asset_url:undefined,
  quality_status:job.quality_status,error:concise(job.error,230),
  timings:job.timings||{},
  attempt_history:(job.attempt_history||[]).map(a=>({
    number:a.number,outcome:a.outcome,wait_ms:a.wait_ms,timings:a.timings||{}
  })),
  qa:job.qa?{
    passed:job.qa.passed,semantic_status:job.qa.semantic_status,
    reasons:(job.qa.reasons||[]).slice(0,3),
    warnings:(job.qa.warnings||[]).slice(0,3),
    metrics:{
      vlm_caption:concise(job.qa.metrics?.vlm_caption,140),
      identity_similarity:job.qa.metrics?.identity_similarity,
      scene_count_verified:job.qa.metrics?.scene_count_verified,
      scene_location_verified:job.qa.metrics?.scene_location_verified,
      scene_count_confidence:job.qa.metrics?.scene_count_confidence,
      scene_solo_score:job.qa.metrics?.scene_solo_score,
      scene_pair_score:job.qa.metrics?.scene_pair_score,
      scene_action_contrast:job.qa.metrics?.scene_action_contrast,
      scene_action_verified:job.qa.metrics?.scene_action_verified,
      checkpoint_name:concise(job.qa.metrics?.checkpoint_name,110)
    }
  }:null,
  spec:{
    preview_only:!!job.spec?.preview_only,
    expected_location:concise(job.spec?.expected_location,140),
    background_asset:concise(job.spec?.background_asset,100),
    expected_variant_key:concise(job.spec?.expected_variant_key,260),
    variant:job.spec?.variant
  }
 };
}
