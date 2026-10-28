import fs from "node:fs/promises";
import path from "node:path";
import {randomUUID} from "node:crypto";
import {dataRoot,gameGet,gameLocalSceneStart,gameLocalSceneStop,
  gameLocalTurnBegin,gameLocalTurnComplete} from "./game-store.mjs";
import {narratorMessages,responseQuality} from "./local-narrator.mjs";
import {extractLocalVisual,initialVisualState,normalizeVisualState,
 directorMessages,parseDirectorPlan,visualContinuityIssues} from "./local-director.mjs";
import {activeGpuJobs,enqueue,getJob} from "./jobs.mjs";
import {withLocalGpu,isLocalGpuReserved} from "./gpu-coordinator.mjs";
import {groundedLocalFrame} from "./local-visual-qa.mjs";
import {decideVisualRender,visualSignature,spriteSignature} from "./render-policy.mjs";

const DIR=path.join(dataRoot,"local-scenes");
const MODEL_URL=(process.env.VN_LOCAL_MODEL_URL||"http://172.19.0.1:28189").replace(/\/$/,"");
const MODEL_ID=process.env.VN_LOCAL_MODEL_ID||"qwen3.5:9b-q4_K_M";
const NARRATOR_MODEL_ID=process.env.VN_LOCAL_NARRATOR_MODEL||MODEL_ID;
const NARRATOR_FALLBACK_ID=process.env.VN_LOCAL_NARRATOR_FALLBACK||MODEL_ID;
const MODEL_TOKEN=process.env.VN_LOCAL_ROUTER_TOKEN||"";
const modelHeaders=()=>MODEL_TOKEN?{Authorization:"Bearer "+MODEL_TOKEN}:{};
const COMFY_FREE_URL=process.env.VN_COMFY_FREE_URL||"";
const UUID=/^[a-f0-9-]{36}$/;
const pendingTasks=new Map();
const visualTasks=new Map();
let fileWriteQueue=Promise.resolve();
const exclusive=fn=>{const p=fileWriteQueue.then(fn);fileWriteQueue=p.catch(()=>{});return p};
const file=id=>{
 if(typeof id!=="string"||!UUID.test(id))throw Error("Invalid game ID");
 return path.join(DIR,id+".json");
};
async function load(gameId){
 try{return JSON.parse(await fs.readFile(file(gameId),"utf8"))}
 catch(e){if(e.code==="ENOENT")return {schema:1,game_id:gameId,sessions:[]};throw e}
}
async function write(gameId,record){
 await fs.mkdir(DIR,{recursive:true});
 const dest=file(gameId),tmp=dest+"."+randomUUID()+".tmp";
 await fs.writeFile(tmp,JSON.stringify(record),{mode:0o600});
 await fs.rename(tmp,dest);
}
async function edit(gameId,mutate){
 return exclusive(async()=>{
  const data=await load(gameId),value=await mutate(data);
  data.sessions=(data.sessions||[]).slice(-12);
  await write(gameId,data);return value;
 });
}
const getSession=(data,id)=>{
 const s=(data.sessions||[]).find(x=>x.id===id);
 if(!s)throw Error("Local session not found");
 return s;
};
export async function beginLocalScene(gameId,version){
 const game=await gameGet(gameId);
 const result=await gameLocalSceneStart(gameId,version);
 await edit(gameId,d=>{
  d.sessions||=[];d.sessions.push({id:result.session_id,participants:result.participants,
   location:game.scene?.location||"",started_at:new Date().toISOString(),ended_at:null,
   transcript:[],pending:null,metrics:[],status:"active",
   visual_state:initialVisualState(game),visual_events:[],
   visual_display:{mode:"layers",cg_job_id:"",sprite_jobs:{}},
   sprite_previews:[],cg_previews:[],video_previews:[]});
 });
 return result;
}
export async function exitLocalScene(gameId,version){
 const result=await gameLocalSceneStop(gameId,version);
 await edit(gameId,d=>{
  const s=getSession(d,result.session_id);
  s.status="complete";s.ended_at=new Date().toISOString();s.pending=null;
 });
 return result;
}
const scrub=s=>String(s||"").replace(/<think>[\s\S]*?<\/think>/gi,"").trim().slice(0,3600);

async function releaseComfy(){
 if(!COMFY_FREE_URL)return;
 const r=await fetch(COMFY_FREE_URL,{method:"POST",headers:{"content-type":"application/json"},
  body:JSON.stringify({unload_models:true,free_memory:true}),
  signal:AbortSignal.timeout(8000)});
 if(!r.ok)throw Error("ComfyUI could not release GPU memory: "+r.status);
}
async function infer(messages,{num_predict=660,num_ctx=8192,
 temperature=0.7,top_p=0.88,repeat_penalty=1.13,
 model=MODEL_ID}={}){
 const started=Date.now();
 const r=await fetch(MODEL_URL+"/api/chat",{
  method:"POST",headers:{"content-type":"application/json",...modelHeaders()},
  body:JSON.stringify({model,messages,stream:false,think:false,
   keep_alive:0,options:{num_ctx,num_predict,
    temperature,top_p,repeat_penalty}}),
  signal:AbortSignal.timeout(185000)
 });
 const raw=await r.text();
 if(!r.ok)throw Error("Local model HTTP "+r.status+": "+raw.slice(0,170));
 const parsed=JSON.parse(raw),text=scrub(parsed?.message?.content);
 if(text.length<12)throw Error("Local model returned an empty response");
 return {text,metrics:{backend:String(parsed.backend||"koboldcpp"),
  model:String(parsed.model||MODEL_ID),
  overall_ms:Date.now()-started,
  total_duration_ms:Math.round(Number(parsed.total_duration||0)/1e6),
  load_duration_ms:Math.round(Number(parsed.load_duration||0)/1e6),
  prompt_eval_count:Number(parsed.prompt_eval_count||0),
  eval_count:Number(parsed.eval_count||0),
  eval_duration_ms:Math.round(Number(parsed.eval_duration||0)/1e6)}};
}
async function runLocal(gameId,requestId){
 try{
  const game=await gameGet(gameId);
  if(game.local_scene?.pending?.request_id!==requestId)throw Error("Local turn no longer pending");
  const d=await load(gameId),s=getSession(d,game.local_scene.session_id);
  const action=s.transcript.find(x=>x.request_id===requestId&&x.role==="player");
  if(!action)throw Error("Local player action is missing");
  const messages=narratorMessages(game,s,action);
  const prior=s.transcript.filter(x=>x.role==="narrator").at(-1)?.text||"";
  const response=await withLocalGpu({
   activeArtJobs:async()=>(await activeGpuJobs()).length,
   prepare:releaseComfy,
   infer:async()=>{
    let result;
    try{result=await infer(messages,{num_ctx:4096,num_predict:500,
      model:NARRATOR_MODEL_ID,temperature:0.72});}
    catch(error){
      if(NARRATOR_MODEL_ID===NARRATOR_FALLBACK_ID)throw error;
      console.warn("Narrator fallback to Qwen:",String(error.message).slice(0,100));
      result=await infer(messages,{num_ctx:8192,num_predict:520,
        model:NARRATOR_FALLBACK_ID,temperature:0.72});
      result.metrics.narrator_fallback=true;
      result.metrics.narrator_fallback_reason=String(error.message).slice(0,100);
    }
    let parsed=extractLocalVisual(result.text,{
      action:action.text,previous:s.visual_state});
    const judged=responseQuality(parsed.narration,prior);
    if(!judged.ok){
     const retry=[...messages,{
      role:"assistant",content:parsed.narration.slice(0,750)
     },{
      role:"user",content:"Предыдущий ответ нарушил правило: "+judged.reason+
       ". Дай НОВЫЙ текст без реплик и действий Макса, закончи целым предложением."
     }];
     const retryModel=result.metrics.model===NARRATOR_MODEL_ID&&
      NARRATOR_MODEL_ID!==NARRATOR_FALLBACK_ID?
      NARRATOR_FALLBACK_ID:result.metrics.model;
     const candidate=await infer(retry,{
      num_ctx:retryModel===NARRATOR_MODEL_ID?4096:8192,
      num_predict:420,model:retryModel});
     const corrected=extractLocalVisual(candidate.text,{
       action:action.text,previous:s.visual_state});
     const second=responseQuality(corrected.narration,prior);
     if(!second.ok)throw Error("Story quality check failed: "+second.reason);
     result={...candidate,metrics:{...candidate.metrics,retried:true,
       narrator_fallback:retryModel!==NARRATOR_MODEL_ID,
       retry_reason:judged.reason,
       overall_ms:result.metrics.overall_ms+candidate.metrics.overall_ms}};
     parsed=corrected;
    }
    return {...result,text:parsed.narration};
   },timeoutMs:180000
  });
  await edit(gameId,d=>{
   const session=getSession(d,game.local_scene.session_id);
   if(session.transcript.some(x=>x.request_id===requestId&&x.role==="narrator"))return;
   session.transcript.push({id:randomUUID(),request_id:requestId,role:"narrator",
    speaker:"Локальный рассказчик",text:response.text,at:new Date().toISOString()});
   session.pending=null;
   session.metrics.push({request_id:requestId,at:new Date().toISOString(),...response.metrics});
   session.metrics=session.metrics.slice(-35);
   session.visual_pending={request_id:requestId,started_at:new Date().toISOString()};
   session.visual_warning="";
  });
  // Write and expose the narration BEFORE the second AI/director pass.
  // Image planning must never keep the player waiting for dialogue.
  await gameLocalTurnComplete(gameId,requestId);
  dispatchVisualDirector(gameId,game.local_scene.session_id,requestId);
 }catch(e){
  const reason=String(e?.message||e).slice(0,200);
  try{
   const game=await gameGet(gameId);
   if(game.local_scene?.pending?.request_id===requestId){
    await edit(gameId,d=>{
     const session=getSession(d,game.local_scene.session_id);
     session.pending=null;session.last_error=reason;
    });
    await gameLocalTurnComplete(gameId,requestId,{error:reason});
   }
  }catch(inner){console.error("local scene error recovery",inner)}
  console.warn("local scene request failed:",reason);
 }finally{pendingTasks.delete(requestId)}
}
// Independent AI director: this runs only AFTER local narration has been saved.
// The player sees the dialogue immediately; the cinematic beat follows later.
async function runVisualDirector(gameId,sessionId,requestId){
 const eligible=async()=>{
  const g=await gameGet(gameId);
  if(g.local_scene?.mode!=="local"||
     g.local_scene.session_id!==sessionId||g.local_scene.pending)return null;
  const doc=await load(gameId),ep=getSession(doc,sessionId);
  const latest=ep.transcript.filter(x=>x.role==="player").at(-1);
  if(ep.visual_pending?.request_id!==requestId||
     latest?.request_id!==requestId)return null;
  return {game:g,ep};
 };
 try{
  const state=await eligible();if(!state)return;
  const {game,ep}=state;
  const player=ep.transcript.find(x=>x.role==="player"&&x.request_id===requestId);
  const narrator=ep.transcript.find(x=>x.role==="narrator"&&x.request_id===requestId);
  if(!player||!narrator)throw Error("Director dialogue is incomplete");
  const input={action:player.text,narration:narrator.text,previous:ep.visual_state};
  let directorRaw="",directorMs=0;
  try{
   const prompt=directorMessages({
    ...input,game,location:game.scene?.location,
    participants:ep.participants,
    recent_dialogue:ep.transcript.slice(-4)
   });
   const start=Date.now();
   const result=await withLocalGpu({
    activeArtJobs:async()=>(await activeGpuJobs()).length,
    prepare:releaseComfy,
    infer:()=>infer(prompt,{
      num_ctx:4096,num_predict:470,temperature:0.16,top_p:0.82,repeat_penalty:1.04
    }),timeoutMs:180000
   });
   directorMs=Date.now()-start;
   directorRaw=result.text;
  }catch(e){
   console.warn("AI visual director fallback",String(e.message).slice(0,100));
  }
  let {plan,warning}=parseDirectorPlan(directorRaw,{...input,game});
  // A visibly incompatible state must be repaired before it is sent to GPU,
  // rather than publishing a visually unrelated but technically valid image.
  if(!warning){
   const issues=visualContinuityIssues({...input,plan});
   if(issues.length){
    try{
     const revise=[...directorMessages({
      ...input,game,location:game.scene?.location,
      participants:ep.participants,recent_dialogue:ep.transcript.slice(-8)
     }),{role:"assistant",content:directorRaw.slice(0,3000)},
      {role:"user",content:"The preceding visual JSON is inconsistent: "+
       issues.join(" ")+" Return a complete corrected JSON scene plan. "+
       "Preserve only confirmed story events, freeform wardrobe and pose details. "+
       "Do not invent an action rejected by an NPC."}];
     const fixed=await withLocalGpu({
      activeArtJobs:async()=>(await activeGpuJobs()).length,
      prepare:releaseComfy,
      infer:()=>infer(revise,{num_ctx:4096,num_predict:510,
       temperature:0.14,top_p:0.82,repeat_penalty:1.04}),
      timeoutMs:180000
     });
     const corrected=parseDirectorPlan(fixed.text,{...input,game});
     const remaining=visualContinuityIssues({...input,plan:corrected.plan});
     if(!corrected.warning&&!remaining.length){
      plan={...corrected.plan,source:"ai_director_reconciled"};
     }else{
      warning="Не удалось согласовать внешний вид и действие. "+
       "Новый CG не создаётся, прежний кадр сохранён.";
      plan={...plan,render:false};
     }
    }catch(e){
     console.warn("Visual continuity correction failed",String(e.message||e).slice(0,90));
     warning="Не удалось исправить противоречие в визуальном состоянии; "+
      "прошлый CG сохранён.";
     plan={...plan,render:false};
    }
   }
  }
  // Deterministic visual decision, independent of the director's
  // enthusiastic render=true suggestion. No speculative new outfits.
  // v6.3 sidecars had CG previews but no explicit display selector.
  // Keep their latest accepted CG visible after upgrading.
  const priorDisplay=ep.visual_display?.mode||
   ((ep.cg_previews||[]).length?"cg":"layers");
  const forced=ep.visual_pending?.manual===true;
  let decision=decideVisualRender({
   previous:ep.visual_state,plan,action:player.text,narration:narrator.text,
   previousDisplay:priorDisplay,stageReady:!game.scene?.background_dirty,
   style:game.art_style
  });
  if(forced&&!warning){
   decision={...decision,mode:"cg",reason:"manual_visual_replan",
    spriteNames:[]};
  }
  if(warning)decision={...decision,mode:"none",reason:"unresolved_visual_continuity"};
  // The director is advisory, but the deterministic scheduler controls GPU.
  plan={...plan,render:decision.mode==="cg"};
  // A newer player action or exiting local mode supersedes this director
  // response. Never queue stale artwork for an old request.
  if(!(await eligible()))return;
  await edit(gameId,d=>{
   const current=getSession(d,sessionId);
   if(current.visual_pending?.request_id!==requestId)return;
   const former=current.visual_state;
   current.visual_state={...plan,last_queued:!plan.render&&!!former?.last_queued,
    last_job_id:former?.last_job_id||"",
    based_on_request_id:requestId,updated_at:new Date().toISOString(),
    director_ms:directorMs};
   current.visual_events ||= [];
   current.visual_events.push({
    request_id:requestId,camera:plan.camera,location:plan.location,
    characters:plan.characters.map(x=>({name:x.name,pose:x.pose,
      outfit:x.outfit,equipment:x.equipment})),
    render:plan.render,mode:decision.mode,reason:decision.reason,
    source:plan.source,director_ms:directorMs
   });
   current.visual_decision={
    request_id:requestId,mode:decision.mode,reason:decision.reason,
    changed:decision.changed||[],at:new Date().toISOString(),
    cached:false,generated_jobs:[]
   };
   current.visual_events=current.visual_events.slice(-50);
   current.visual_warning=warning;
   current.visual_pending=null;
  });
  if(decision.mode!=="none"&&!warning&&
     (await eligibleFreshLocalScene(gameId,sessionId,requestId))){
   try{
    if(decision.mode==="cg"){
      const created=await queueLocalCG(gameId,{quality:"standard",
       auto:true,allowCache:true});
      await edit(gameId,d=>{
       const s=getSession(d,sessionId);
       if(s.visual_state?.based_on_request_id===requestId&&s.visual_decision){
        s.visual_decision.cached=!!created.cache_hit;
        s.visual_decision.generated_jobs=created.cache_hit?[]:[created.id];
       }
      });
    }else if(decision.mode==="sprite"){
      const created=await queueLocalSprites(gameId,decision.spriteNames,
       {requestId});
      await edit(gameId,d=>{
       const s=getSession(d,sessionId);
       if(s.visual_state?.based_on_request_id===requestId&&s.visual_decision){
        s.visual_decision.cached=created.generated.length===0;
        s.visual_decision.generated_jobs=created.generated;
       }
      });
    }
   }catch(e){
    const msg=String(e.message||e).slice(0,190);
    await edit(gameId,d=>{
     const s=getSession(d,sessionId);
     if(s.visual_state?.based_on_request_id===requestId)
      s.visual_warning="Визуальное обновление не поставлено в очередь: "+msg;
    });
   }
  }
 }catch(e){
  console.warn("Visual director failed",String(e.message||e).slice(0,130));
  try{
   await edit(gameId,d=>{
    const s=getSession(d,sessionId);
    if(s.visual_pending?.request_id===requestId){
     s.visual_pending=null;
     s.visual_warning="Не удалось выбрать иллюстрацию: "+String(e.message||e).slice(0,120);
    }
   });
  }catch{}
 }finally{visualTasks.delete(requestId)}
}
async function eligibleFreshLocalScene(gameId,sessionId,requestId){
 const g=await gameGet(gameId);
 if(g.local_scene?.mode!=="local"||g.local_scene.session_id!==sessionId||
    g.local_scene.pending)return false;
 const ep=getSession(await load(gameId),sessionId);
 return ep.visual_state?.based_on_request_id===requestId&&
  ep.transcript.filter(x=>x.role==="player").at(-1)?.request_id===requestId;
}
function dispatchVisualDirector(gameId,sessionId,requestId){
 if(visualTasks.has(requestId))return;
 visualTasks.set(requestId,runVisualDirector(gameId,sessionId,requestId));
}
function dispatch(gameId,requestId){
 if(pendingTasks.has(requestId))return;
 pendingTasks.set(requestId,runLocal(gameId,requestId));
}
export async function submitLocalTurn(gameId,action,version){
 const text=String(action||"").trim();
 if(!text||text.length>2000)throw Error("Local action must have 1-2000 characters");
 const g=await gameGet(gameId),rec=await gameLocalTurnBegin(gameId,version);
 await edit(gameId,d=>{
  const s=getSession(d,rec.session_id);
  s.transcript.push({id:randomUUID(),request_id:rec.request_id,
   role:"player",speaker:g.hero.name,text,at:rec.submitted_at});
  s.pending={request_id:rec.request_id,started_at:rec.submitted_at};
 });
 dispatch(gameId,rec.request_id);
 return {game_id:gameId,version:rec.version,session_id:rec.session_id,
  request_id:rec.request_id,status:"generating",submitted_at:rec.submitted_at};
}
// Recompute the last visual beat without a second player turn.
export async function replanLocalScene(gameId){
 const g=await gameGet(gameId);
 if(g.local_scene?.mode!=="local")throw Error("Local scene is not active");
 if(g.local_scene.pending)throw Error("Finish the current player action first");
 const ep=getSession(await load(gameId),g.local_scene.session_id);
 if(ep.visual_pending)throw Error("Visual planning already in progress");
 const last=ep.transcript.filter(x=>x.role==="player").at(-1);
 if(!last||!ep.transcript.some(x=>x.role==="narrator"&&x.request_id===last.request_id))
  throw Error("No completed local turn is available for visual replanning");
 await edit(gameId,d=>{
  const s=getSession(d,g.local_scene.session_id);
  if(s.visual_pending)throw Error("Visual planning already in progress");
  s.visual_pending={request_id:last.request_id,
   started_at:new Date().toISOString(),manual:true};
  s.visual_warning="";
 });
 dispatchVisualDirector(gameId,g.local_scene.session_id,last.request_id);
 return {game_id:gameId,session_id:g.local_scene.session_id,
  status:"replanning",request_id:last.request_id};
}

// Compose the actual current visual state into a single text-to-image
// specification. No outfit, item or pose enum exists in this pipeline.
export function describeLocalVisual(plan,game){
 const actorDescriptions=(plan.characters||[]).map(c=>{
  const canonical=c.name===game.hero?.name?game.hero?.description:
    (game.story?.characters||[]).find(p=>p.name===c.name)?.description;
  return [
   "Character "+c.name,
   "Identity: "+String(canonical||"").slice(0,320),
   "Outfit: "+c.outfit,
   "Equipment and held items: "+c.equipment,
   "Body pose: "+c.pose,
   "Facial expression: "+c.expression,
   "Physical action: "+c.action
  ].join(". ");
 }).join("\n");
 return [
  "Original illustrated visual novel cinematic still.",
  "Current location: "+plan.location,
  "Environment and objects: "+plan.environment,
  "Camera framing and viewpoint: "+plan.camera,
  "Lighting: "+plan.lighting,
  "Story action and relations: "+plan.activity,
  "Keep established adult characters recognizable and distinct.",
  actorDescriptions,
  "The current physical actions, exact body poses, wardrobe arrangement and equipment placement are visual requirements, not optional atmosphere.",
  "Avoid an unrelated static portrait or incompatible clothing and pose details.",
  "One coherent, naturally posed scene. Consistent perspective, anatomy and light."
 ].join("\n").slice(0,3900);
}

// Local dialogue sprites remain preview-only. They are actually displayed
// as transparent layers in the stage. They never rewrite canonical sprites.
export async function queueLocalSprites(gameId,names,{requestId=""}={}){
 const game=await gameGet(gameId);
 if(game.local_scene?.mode!=="local"||game.local_scene.pending)
  throw Error("Local dialogue must finish before sprite rendering");
 const data=await load(gameId);
 const ep=getSession(data,game.local_scene.session_id);
 const state=normalizeVisualState(ep.visual_state,game);
 const requested=new Set((names||[]).map(x=>String(x).toLocaleLowerCase("ru")));
 const selected=state.characters.filter(a=>
  requested.has(a.name.toLocaleLowerCase("ru")));
 const jobs={...(ep.visual_display?.sprite_jobs||{})};
 const generated=[];
 for(const actor of selected){
  const signature=spriteSignature(actor,state.location,game.art_style);
  const history=[...(ep.sprite_previews||[])].reverse();
  let selectedJob=null;
  for(const item of history){
   if(item.character!==actor.name||item.signature!==signature)continue;
   try{
    const candidate=await getJob(item.job_id);
    if(candidate.status==="done"&&candidate.asset_url&&candidate.qa?.passed){
     selectedJob=candidate;break;
    }
    if(["working","queued"].includes(candidate.status)){
     selectedJob=candidate;break;
    }
   }catch{}
  }
  if(!selectedJob){
   selectedJob=await enqueue({game_id:gameId,kind:"sprite",
    style:game.art_style,character:actor.name,quality:"fast",
    preview_only:true,force:true,priority:62,
    outfit:actor.outfit,pose:actor.pose,emotion:actor.expression,
    prompt:["Single established fictional adult character",actor.name,
     "Recognizable canonical face and physique.",
     "Current outfit:",actor.outfit,"Expression:",actor.expression,
     "Pose:",actor.pose,"Gear:",actor.equipment,
     "Cutout with clean plain matte background; no scenery."
    ].join(" ").slice(0,2400)});
   generated.push(selectedJob.id);
  }
  jobs[actor.name]=selectedJob.id;
  await edit(gameId,d=>{
   const s=getSession(d,game.local_scene.session_id);
   s.sprite_previews||=[];
   if(!s.sprite_previews.some(x=>x.job_id===selectedJob.id))
    s.sprite_previews.push({job_id:selectedJob.id,character:actor.name,
      signature,requested_at:new Date().toISOString()});
   s.sprite_previews=s.sprite_previews.slice(-90);
  });
 }
 await edit(gameId,d=>{
  const s=getSession(d,game.local_scene.session_id);
  if(s.visual_state?.based_on_request_id!==requestId&&requestId)return;
  s.visual_display={mode:"layers",cg_job_id:"",
   sprite_jobs:jobs,updated_at:new Date().toISOString()};
 });
 return {sprite_jobs:jobs,generated};
}

// Every local still is GPU diffusion work. The previous accepted still may
// provide an img2img continuity reference; the canonical scene is untouched.
export async function queueLocalCG(gameId,{
 direction="",quality="standard",auto=false,allowCache=false}={}){
 const g=await gameGet(gameId);
 if(g.local_scene?.mode!=="local")throw Error("A local scene must be active");
 if(g.local_scene?.pending)throw Error("Finish local text generation before creating artwork");
 if(!["fast","standard","cinematic"].includes(quality))throw Error("Invalid image quality");
 const data=await load(gameId);
 const ep=getSession(data,g.local_scene.session_id);
 if(ep.visual_pending)throw Error("Wait for visual continuity replanning");
 const current=normalizeVisualState(ep.visual_state,g);
 const plan=direction.trim()?{...current,
  camera:String(direction).trim().slice(0,320)}:current;
 const prompt=describeLocalVisual(plan,g);
 // Existing approved canonical references condition the CG directly via
 // IPAdapter on the GPU. No duplicate full-length sprite renders here.
 const variants=[];
 const signature=visualSignature(plan,{style:g.art_style});
 if(auto&&allowCache){
  for(const old of [...(ep.cg_previews||[])].reverse()){
   if(old.signature!==signature)continue;
   try{
    const candidate=await getJob(old.job_id);
    const qa=groundedLocalFrame(candidate,{
     sessionId:g.local_scene.session_id,visualState:plan});
    if(!qa.ok)continue;
    await edit(gameId,d=>{
     const session=getSession(d,g.local_scene.session_id);
     session.cg_previews||=[];
     session.cg_previews.push({job_id:candidate.id,source:"cache",
      signature,camera:plan.camera,description:plan.activity,
      requested_at:new Date().toISOString()});
     session.cg_previews=session.cg_previews.slice(-30);
     session.visual_display={mode:"cg",cg_job_id:candidate.id,
      sprite_jobs:{},updated_at:new Date().toISOString()};
     if(session.visual_state){session.visual_state.last_queued=true;
      session.visual_state.last_job_id=candidate.id}
    });
    return {id:candidate.id,kind:"local_cg",status:"done",
      quality,cache_hit:true,composition:"neural_story",variant_jobs:[]};
   }catch{}
  }
 }
 // Only the latest genuinely verified shot can serve as image-to-image
 // continuity. A published file with the wrong cast or background is not a
 // trusted seed even if its PNG and general QA previously passed.
 let lastFrameUrl="",lastFrameJobId="",seedReason="no_prior_frame";
 for(const old of [...(ep.cg_previews||[])].reverse()){
  try{
   const j=await getJob(old.job_id);
   if(j.status!=="done"){
    seedReason="newer_frame_not_ready";
    break;
   }
   const verdict=groundedLocalFrame(j,{
    sessionId:g.local_scene.session_id,visualState:plan});
   seedReason=verdict.reason;
   if(verdict.ok){lastFrameUrl=j.asset_url;lastFrameJobId=j.id}
   // Never silently fall back to a different, older visual moment.
   break;
  }catch{seedReason="previous_frame_unavailable";break}
 }
 // A materially changed action or camera must not inherit the previous
 // full-frame body pose. Immutable face references still protect identity.
 const canonical=new Map((g.scene?.sprites||[]).map(x=>[x.name,x]));
 const differsFromCanon=plan.location!==g.scene?.location||
  plan.characters.some(c=>{
   const old=canonical.get(c.name);
   return !old||String(c.outfit||"")!==String(old.outfit||"")||
     String(c.pose||"")!==String(old.pose||"")||
     !!String(c.action||"").trim();
  });
 const freshComposition=differsFromCanon||(!lastFrameUrl&&(
  !!String(plan.activity||"").trim()||
  plan.characters.some(c=>String(c.action||"").trim())))||
  /^(Scene activity changed|Character (?:outfit|equipment|action|pose) changed|Camera viewpoint changed|Visible cast changed)$/u.test(seedReason);
 const job=await enqueue({game_id:gameId,kind:"local_cg",
  style:g.art_style,quality,preview_only:true,force:true,priority:73,
  prompt,local_visual_state:plan,local_fresh_composition:freshComposition,
  local_basis_asset:lastFrameUrl,
  local_basis_job_id:lastFrameJobId,local_basis_verified:!!lastFrameUrl,
  local_variant_jobs:variants});
 await edit(gameId,d=>{
  const session=getSession(d,g.local_scene.session_id);
  session.cg_previews||=[];
  session.cg_previews.push({job_id:job.id,source:auto?"ai":"manual",
   signature,camera:plan.camera,description:plan.activity,
   seed_source_job_id:lastFrameJobId,seed_reason:seedReason,
   fresh_composition:freshComposition,
   requested_at:new Date().toISOString()});
  session.cg_previews=session.cg_previews.slice(-30);
  session.visual_display={mode:"cg",cg_job_id:job.id,
   sprite_jobs:{},updated_at:new Date().toISOString()};
  if(session.visual_state&&auto){
   session.visual_state.last_queued=true;
   session.visual_state.last_job_id=job.id;
  }
  session.visual_warning="";
 });
 return {id:job.id,kind:"local_cg",status:job.status,preview_only:true,
  quality,session_id:g.local_scene.session_id,
  camera:plan.camera,composition:"neural_story",
  variant_jobs:variants.map(v=>v.job_id)};
}

// Video is explicitly opt-in. It animates the latest ACCEPTED local still,
// never a stale queued image or the canonical main-story frame.
export async function queueLocalVideo(gameId,{motion=""}={}){
 const g=await gameGet(gameId);
 if(g.local_scene?.mode!=="local")throw Error("A local scene must be active");
 if(g.local_scene.pending)throw Error("Wait until narration is finished");
 const data=await load(gameId),session=getSession(data,g.local_scene.session_id);
 const plan=normalizeVisualState(session.visual_state,g);
 const newest=(session.cg_previews||[]).at(-1);
 if(!newest)throw Error("Create and finish a local CG before requesting video");
 const frame=await getJob(newest.job_id);
 const verdict=groundedLocalFrame(frame,{
  sessionId:g.local_scene.session_id,visualState:plan,forVideo:true});
 if(!verdict.ok)throw Error("Video needs a verified current CG: "+verdict.reason);
 const movement=String(motion).trim().slice(0,900)||
  plan.activity||"Subtle natural motion, cinematic camera movement";
 const prompt=[
  "Short continuous animated scene of these same fictional characters.",
  "Action: "+movement,
  "Camera: "+plan.camera,
  "Location: "+plan.location,
  "Preserve visual identity, appearance and costume of the supplied starting image.",
  "Natural motion, consistent light, coherent facial features, stable scene geometry."
 ].join(" ").slice(0,3900);
 const j=await enqueue({game_id:gameId,kind:"video",quality:"fast",
  style:g.art_style,preview_only:true,force:true,priority:40,prompt,
  local_visual_state:plan,video_start_asset:frame.asset_url,
  video_source_verified:true});
 await edit(gameId,d=>{
  const ep=getSession(d,g.local_scene.session_id);
  ep.video_previews||=[];
  ep.video_previews.push({job_id:j.id,source_frame_id:frame.id,
   motion:movement,requested_at:new Date().toISOString()});
  ep.video_previews=ep.video_previews.slice(-15);
 });
 return {id:j.id,kind:"video",status:j.status,preview_only:true,
  session_id:g.local_scene.session_id,source_frame_id:frame.id};
}
export async function getLocalEpisode(gameId,{session_id}={}){
 const g=await gameGet(gameId),data=await load(gameId);
 const wanted=session_id||g.local_scene?.session_id||g.local_scene?.last_session_id;
 if(!wanted)return {game_id:gameId,status:"none",transcript:[],active:false};
 const s=getSession(data,wanted);
 const lastLegacyCg=(s.cg_previews||[]).at(-1)?.job_id||"";
 const display={mode:s.visual_display?.mode||
    (lastLegacyCg?"cg":"layers"),
  cg_job_id:s.visual_display?.cg_job_id||lastLegacyCg,
  sprite_jobs:{...(s.visual_display?.sprite_jobs||{})},
  cg_url:"",sprite_urls:{}};
 if(display.mode==="cg"&&display.cg_job_id){
  try{
   const cg=await getJob(display.cg_job_id);
   if(cg.status==="done"&&cg.asset_url&&cg.qa?.passed&&
      cg.qa?.metrics?.scene_count_verified===true)
    display.cg_url=cg.asset_url;
  }catch{}
 }
 if(display.mode==="layers"){
  for(const [name,jobId] of Object.entries(display.sprite_jobs).slice(0,5)){
   try{
    const job=await getJob(jobId);
    if(job.kind==="sprite"&&job.status==="done"&&job.asset_url&&
       job.qa?.passed&&job.spec?.preview_only)
     display.sprite_urls[name]=job.asset_url;
   }catch{}
  }
 }
 return {game_id:gameId,session_id:s.id,status:s.status,
  active:g.local_scene?.mode==="local"&&g.local_scene?.session_id===s.id,
  participants:s.participants,started_at:s.started_at,ended_at:s.ended_at,
  transcript:s.transcript.slice(-60),pending:s.pending,last_error:s.last_error||"",
  last_metrics:s.metrics.at(-1)||null,total_messages:s.transcript.length,
  cg_previews:(s.cg_previews||[]).slice(-12),
  sprite_previews:(s.sprite_previews||[]).slice(-25),
  visual_display:display,
  visual_decision:s.visual_decision||null,
  video_previews:(s.video_previews||[]).slice(-10),
  visual_state:s.visual_state||null,
  visual_pending:s.visual_pending||null,
  visual_warning:s.visual_warning||"",
  version:g.version};
}
export async function localHealth(){
 try{
  const start=Date.now(),r=await fetch(MODEL_URL+"/api/tags",
   {headers:modelHeaders(),signal:AbortSignal.timeout(3500)});
  if(!r.ok)throw Error("HTTP "+r.status);
  const data=await r.json();
  return {online:true,model:NARRATOR_MODEL_ID,director_model:MODEL_ID,
   model_ready:(data.models||[]).some(m=>
    m.name===NARRATOR_MODEL_ID||m.model===NARRATOR_MODEL_ID),
   latency_ms:Date.now()-start,gpu_busy:isLocalGpuReserved()};
 }catch(e){return {online:false,model:NARRATOR_MODEL_ID,
  error:String(e.message).slice(0,100),gpu_busy:isLocalGpuReserved()}}
}
export async function recoverLocalTurns(){
 try{
  const files=(await fs.readdir(path.join(dataRoot,"games"))).filter(f=>f.endsWith(".json"));
  for(const f of files){
   const gameId=f.slice(0,-5);
   try{
    const game=await gameGet(gameId),p=game.local_scene?.pending;
    if(game.local_scene?.mode!=="local")continue;
    const data=await load(gameId),s=getSession(data,game.local_scene.session_id);
    if(p){
      if(s.transcript.some(x=>x.request_id===p.request_id&&x.role==="narrator"))
        await gameLocalTurnComplete(gameId,p.request_id);
      else if(s.transcript.some(x=>x.request_id===p.request_id&&x.role==="player"))
        dispatch(gameId,p.request_id);
      else await gameLocalTurnComplete(gameId,p.request_id,{error:"Missing request after restart"});
    }
    // The sidecar still remembers unfinished scene direction after a process
    // restart. Replay only the newest completed local turn, never an old one.
    const todo=s.visual_pending?.request_id;
    if(todo&&s.transcript.filter(x=>x.role==="player").at(-1)?.request_id===todo&&
       s.transcript.some(x=>x.role==="narrator"&&x.request_id===todo))
      dispatchVisualDirector(gameId,game.local_scene.session_id,todo);
   }catch(e){console.warn("Local recovery skipped",gameId,e.message)}
  }
 }catch(e){console.warn("Local recovery unavailable:",e.message)}
}
