import http from "node:http";
import fs from "node:fs/promises";
import crypto from "node:crypto";
import * as games from "./src/game-store.mjs";
import * as jobs from "./src/jobs.mjs";
import {waitGameEvents} from "./src/live-events.mjs";
import {makeNarrationPacket} from "./src/narration-packet.mjs";
import {measureTurnPerformance} from "./src/turn-performance.mjs";
import * as local from "./src/local-scene.mjs";
import {scheduleStandaloneVisuals,sceneCGPrompt} from "./src/standalone-visuals.mjs";
import {executeStandaloneCommand,standaloneContext} from "./src/standalone-commands.mjs";

const PORT=Number(process.env.VN_PORT||3100),HOST=process.env.VN_HOST||"127.0.0.1";
const WORKER_KEY=process.env.VN_WORKER_TOKEN||"";
const PUBLIC=(process.env.VN_PUBLIC_ORIGIN||"https://xavoks.jo3.org/vn").replace(/\/$/,"");
// Standalone HTTP API only; legacy ChatGPT MCP endpoint intentionally removed.
if(HOST!=="127.0.0.1"&&!WORKER_KEY)
 throw Error("VN_WORKER_TOKEN required on LAN");
function validBearer(req,key){
 if(!key)return HOST==="127.0.0.1";
 const a=Buffer.from(req.headers.authorization||""),b=Buffer.from("Bearer "+key);
 return a.length===b.length&&crypto.timingSafeEqual(a,b);
}
function json(res,code,x){res.writeHead(code,{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store"});res.end(JSON.stringify(x))}
const service=http.createServer(async(req,res)=>{
 const u=new URL(req.url||"/","http://localhost");
 try{
 if(u.pathname==="/healthz")return json(res,200,{ok:true,name:"mcp-vn",version:"0.7.0"});
 if(u.pathname.startsWith("/worker/")){
  if(!validBearer(req,WORKER_KEY))return json(res,401,{error:"Unauthorized"});
  // Dedicated authenticated REST facade for the independent local VN web UI.
  // The web frontend never receives WORKER_KEY.
  if(u.pathname.startsWith("/worker/standalone/")){
   const sub=u.pathname.slice("/worker/standalone/".length);
   if(req.method==="GET"&&sub==="games")
    return json(res,200,{games:await games.list("games")});
   const contextMatch=sub.match(/^context\/([a-f0-9-]{36})$/i);
   if(req.method==="GET"&&contextMatch)
    return json(res,200,{packet:await standaloneContext(contextMatch[1])});
   if(req.method==="POST"&&sub==="command"){
    const input=JSON.parse((await body(req,18000)).toString());
    return json(res,200,await executeStandaloneCommand(input));
   }
   const jobMatch=sub.match(/^visual-jobs\/([a-f0-9-]{36})$/i);
   if(req.method==="GET"&&jobMatch){
    await games.gameGet(jobMatch[1]);
    const relevant=(await jobs.jobsForGame(jobMatch[1])).slice(0,25).map(j=>({
     id:j.id,kind:j.kind,character:j.character||"",style:j.style||"",status:j.status,
     stage:j.stage||"",applied:!!j.applied,
     narrator_prompt:j.spec?.narrator_prompt===true,
     error:String(j.error||"").slice(0,180),
     not_applied_reason:String(j.not_applied_reason||"").slice(0,180),
     quality_status:j.quality_status||"",
     attempts:j.attempts||0,
     timings:j.timings||{},attempt_history:(j.attempt_history||[]).slice(-5),
     qa:{semantic_status:j.qa?.semantic_status||"",reasons:(j.qa?.reasons||[]).slice(0,4),
       warnings:(j.qa?.warnings||[]).slice(0,4)},created_at:j.created_at,finished_at:j.finished_at,
     progress:j.progress||0,preview:!!j.spec?.preview_only,
     ...(j.kind==="video"&&j.status==="done"?{asset_url:j.asset_url||""}:{})
    }));
    return json(res,200,{jobs:relevant});
   }
   if(req.method==="POST"&&sub==="visual-refresh"){
    const input=JSON.parse((await body(req,4096)).toString());
    const gameId=String(input.game_id||"");
    if(!/^[a-f0-9-]{36}$/i.test(gameId))
     return json(res,400,{error:"Invalid game ID"});
    const current=await games.gameEnsureSceneCast(gameId);
    return json(res,200,{visual:await scheduleStandaloneVisuals(current,{
      retry:input.retry===true})});
   }
   const memoryMatch=sub.match(/^memory\/([a-f0-9-]{36})$/i);
   if(req.method==="GET"&&memoryMatch)
    return json(res,200,{memory:await games.gameMemory(memoryMatch[1],{
      query:"",limit:15})});
   const perfMatch=sub.match(/^performance\/([a-f0-9-]{36})$/i);
   if(req.method==="GET"&&perfMatch)
    return json(res,200,{performance:measureTurnPerformance(
      await games.gameGet(perfMatch[1]),{limit:12})});
   if(req.method==="POST"&&sub==="undo"){
    const input=JSON.parse((await body(req,4096)).toString());
    const id=String(input.game_id||"");
    if(!/^[a-f0-9-]{36}$/i.test(id))
     return json(res,400,{error:"Invalid game ID"});
    const g=await games.gameGet(id);
    if(!Number.isSafeInteger(input.expected_version)||
       g.version!==input.expected_version)
     return json(res,409,{error:"Version changed; refresh before undo"});
    return json(res,200,{game:await games.gameUndo(id,input.expected_version)});
   }
   if(req.method==="POST"&&sub==="local-exit"){
    const input=JSON.parse((await body(req,4096)).toString());
    const id=String(input.game_id||"");
    if(!/^[a-f0-9-]{36}$/i.test(id))
     return json(res,400,{error:"Invalid game ID"});
    return json(res,200,{local_scene:await local.exitLocalScene(
      id,Number.isSafeInteger(input.expected_version)?
      input.expected_version:undefined)});
   }
   if(req.method==="POST"&&sub==="visual-cg-regenerate"){
    const input=JSON.parse((await body(req,4096)).toString());
    const id=String(input.game_id||"");
    if(!/^[a-f0-9-]{36}$/i.test(id))
     return json(res,400,{error:"Invalid game ID"});
    const g=await games.gameGet(id);
    if(!Number.isSafeInteger(input.expected_version)||g.version!==input.expected_version)
     return json(res,409,{error:"Version changed; refresh before regenerating CG"});
    if(g.awaiting_narrator||g.local_scene?.mode==="local")
     return json(res,409,{error:"Finish current turn before regenerating CG"});
    if(!g.scene?.background_url||g.scene.background_dirty||!(g.scene.sprites||[]).length)
     return json(res,409,{error:"Generate a background and establish the scene first"});
    if(g.scene.sprites.some(actor=>{
     const identity=g.identities?.[actor.name]||{};
     return !identity.face_url&&!identity.base_sprite_url;
    }))return json(res,409,{error:"Canonical character face references are required"});
    const authored=g.scene.image_prompts?.cg;
    const prompt=typeof authored==="string"&&authored.trim()?authored.trim():sceneCGPrompt(g);
    const job=await jobs.enqueue({game_id:id,kind:"scene",neural_scene:true,
     narrator_prompt:!!(typeof authored==="string"&&authored.trim()),
     style:g.art_style,quality:"standard",force:true,prompt,priority:75});
    return json(res,200,{job:{id:job.id,kind:job.kind,status:job.status,
     deduplicated:!!job.deduplicated}});
   }
   if(req.method==="POST"&&sub==="visual-cg"){
    const input=JSON.parse((await body(req,4096)).toString());
    const id=String(input.game_id||"");
    if(!/^[a-f0-9-]{36}$/i.test(id))
     return json(res,400,{error:"Invalid game ID"});
    const g=await games.gameGet(id);
    if(!Number.isSafeInteger(input.expected_version)||
       g.version!==input.expected_version)
     return json(res,409,{error:"Version changed; refresh before rendering"});
    if(g.awaiting_narrator||g.local_scene?.mode==="local")
     return json(res,409,{error:"Finish current turn before rendering"});
    if(!g.scene?.background_url||g.scene.background_dirty||
       !(g.scene.sprites||[]).length||
       (g.scene.sprites||[]).some(x=>x.visual_dirty))
     return json(res,409,{error:"Generate background and characters first"});
    const names=g.scene.sprites.map(x=>x.name).join(", ");
    const lastNarration=g.messages.filter(x=>x.role==="narrator").at(-1);
    const prompt=["Cohesive cinematic fantasy visual novel scene.",
      "Location:",g.scene.location||"unknown",
      ". Characters:",names,". Visual style:",g.art_style,
      ". Established context:",String(lastNarration?.text||"").slice(0,500),
      ". Use existing approved canonical character sprites. No new people."
    ].join(" ").slice(0,1800);
    const job=await jobs.enqueue({game_id:id,kind:"scene",
      style:g.art_style,quality:"standard",force:input.force===true,
      prompt,priority:55});
    return json(res,200,{job:{id:job.id,kind:job.kind,status:job.status}});
   }
   const localMatch=sub.match(/^local-status\/([a-f0-9-]{36})$/i);
   if(req.method==="GET"&&localMatch)
    return json(res,200,{local_episode:await local.getLocalEpisode(localMatch[1])});
   if(req.method==="POST"&&sub==="local-submit"){
    const input=JSON.parse((await body(req,12000)).toString());
    const gameId=String(input.game_id||"");
    if(!/^[a-f0-9-]{36}$/i.test(gameId)||
       typeof input.action!=="string"||input.action.length>2000||
       !input.action.trim())return json(res,400,{error:"Invalid local action"});
    const names={
      "local-cydonia-24b":"cydonia:24b-v4.3-iq4_xs",
      "local-qwen-9b":"qwen3.5:9b-q4_K_M"
    };
    const model=String(input.model||"");
    const selected=names[model]||model;
    const data=await local.submitLocalTurn(gameId,input.action,
      Number.isSafeInteger(input.expected_version)?input.expected_version:undefined,
      selected);
    return json(res,200,{local_request:data});
   }
   const match=sub.match(/^game\/([a-f0-9-]{36})$/i);
   if(req.method==="GET"&&match)
    return json(res,200,{game:await games.gameGet(match[1])});
   const packetMatch=sub.match(/^packet\/([a-f0-9-]{36})$/i);
   if(req.method==="GET"&&packetMatch){
    const game=await games.gameGet(packetMatch[1]);
    if(!game.awaiting_narrator)
     return json(res,409,{error:"No pending player turn"});
    return json(res,200,{packet:makeNarrationPacket(game)});
   }
   if(req.method==="POST"&&sub==="submit"){
    const bodyData=JSON.parse((await body(req,18000)).toString());
    if(!/^[a-f0-9-]{36}$/i.test(String(bodyData.game_id||""))||
       typeof bodyData.action!=="string"||!bodyData.action.trim()||
       bodyData.action.length>5000)
      return json(res,400,{error:"Invalid game or action"});
    const expected=bodyData.expected_version;
    if(expected!==undefined&&(!Number.isSafeInteger(expected)||expected<1))
      return json(res,400,{error:"Invalid expected_version"});
    const g=await games.gameAction(bodyData.game_id,bodyData.action,expected);
    return json(res,200,{submitted:{id:g.id,version:g.version,
      awaiting_narrator:g.awaiting_narrator},packet:makeNarrationPacket(g)});
   }
   if(req.method==="POST"&&sub==="commit"){
    const input=JSON.parse((await body(req,38000)).toString());
    const gameId=String(input.game_id||"");
    if(!/^[a-f0-9-]{36}$/i.test(gameId))
      return json(res,400,{error:"Invalid game id"});
    const g=await games.gameGet(gameId);
    const pendingId=g.turn_metrics?.pending?.action_id||
      g.messages?.filter(x=>x.role==="player").at(-1)?.id;
    if(!g.awaiting_narrator||!pendingId||
       !input.action_id||String(input.action_id)!==pendingId)
      return json(res,409,{error:"Narration is not pending for this action"});
    if(!Array.isArray(input.messages)||!input.messages.length||
       input.messages.length>12||input.messages.some(x=>
        !x||typeof x.speaker!=="string"||typeof x.text!=="string"||
        x.text.trim().length<1||x.text.length>10000))
      return json(res,400,{error:"Invalid narrator messages"});
    const safeScene={};
    if(input.scene&&typeof input.scene==="object"){
      for(const key of ["location","time_of_day","weather"])
       if(typeof input.scene[key]==="string")safeScene[key]=input.scene[key].slice(0,170);
      if(typeof input.scene.visual_direction==="string")
       safeScene.visual_direction=input.scene.visual_direction.slice(0,420);
      if(["cg","layers"].includes(input.scene.visual_mode))
       safeScene.visual_mode=input.scene.visual_mode;
      if(input.scene.image_prompts&&typeof input.scene.image_prompts==="object"&&
          !Array.isArray(input.scene.image_prompts)){
       const source=input.scene.image_prompts,clean={};
       for(const kind of ["background","cg"])
        if(typeof source[kind]==="string"&&source[kind].trim())
         clean[kind]=source[kind].trim().slice(0,2000);
       if(source.sprites&&typeof source.sprites==="object"&&!Array.isArray(source.sprites)){
        const known=new Set([g.hero?.name,...(g.story?.characters||[]).map(x=>x.name),
         ...(g.scene?.sprites||[]).map(x=>x.name)].filter(Boolean));
        const items={};
        for(const [name,prompt] of Object.entries(source.sprites).slice(0,5))
         if(known.has(name)&&typeof prompt==="string"&&prompt.trim())
          items[name]=prompt.trim().slice(0,1600);
        if(Object.keys(items).length)clean.sprites=items;
       }
       if(Object.keys(clean).length)safeScene.image_prompts=clean;
      }
      // A remote narrator may suggest image-layer state, but may ONLY
      // describe established, named cast members. Never allow arbitrary
      // image URLs or changes to the game's locked visual style.
      if(Array.isArray(input.scene.sprites)&&input.scene.sprites.length<=5){
       const known=new Set([g.hero?.name,...(g.story?.characters||[]).map(x=>x.name),
        ...(g.scene?.sprites||[]).map(x=>x.name)].filter(Boolean));
       const seen=new Set(),visible=[];
       for(const actor of input.scene.sprites){
        if(!actor||typeof actor!=="object")continue;
        const name=String(actor.name||"").trim().slice(0,100);
        if(!known.has(name)||seen.has(name))continue;
        seen.add(name);
        const item={name};
       for(const [key,limit] of [["pose",80],["outfit",80],["emotion",60]])
        if(typeof actor[key]==="string"&&actor[key].trim())
         item[key]=actor[key].trim().slice(0,limit);
       visible.push(item);
       }
       if(visible.length||input.scene.sprites.length===0)safeScene.sprites=visible;
      }
    }
    const safeFlags={};
    if(input.flags&&typeof input.flags==="object"&&!Array.isArray(input.flags)){
     for(const [key,value] of Object.entries(input.flags).slice(0,80)){
      if(/^[a-zA-Z0-9_-]{1,80}$/.test(key)&&(
       typeof value==="boolean"||
       (typeof value==="number"&&Number.isFinite(value)&&Math.abs(value)<=1e9)||
       (typeof value==="string"&&value.length<=180)))safeFlags[key]=value;
     }
    }
    const committed=await games.gameNarrate({game_id:gameId,expected_action_id:input.action_id,
      messages:input.messages,scene:safeScene,flags:safeFlags,
      choices:Array.isArray(input.choices)?
        input.choices.filter(x=>typeof x==="string").slice(0,6):[]});
    return json(res,200,{game:committed});
   }
   return json(res,404,{error:"Unknown standalone route"});
  }
  if(req.method==="GET"&&u.pathname==="/worker/next"){
   const pool=u.searchParams.get("pool")||"any";
   if(!["any","cpu","gpu"].includes(pool))return json(res,400,{error:"Invalid pool"});
   return json(res,200,{job:await jobs.nextJob(pool)});
  }
  const assetMatch=u.pathname.match(/^\/worker\/asset\/([a-f0-9-]{36}\.(?:png|jpg|webp|mp4))$/);
  if(req.method==="GET"&&assetMatch){
   const bytes=await fs.readFile(await jobs.assetFile(assetMatch[1]));
   const mime=assetMatch[1].endsWith(".mp4")?"video/mp4":assetMatch[1].endsWith(".png")?"image/png":assetMatch[1].endsWith(".webp")?"image/webp":"image/jpeg";
   res.writeHead(200,{"Content-Type":mime,"Cache-Control":"no-store","Content-Length":bytes.length});
   return res.end(bytes);
  }
  const match=u.pathname.match(/^\/worker\/(complete|fail|qa|stage)\/([a-f0-9-]{36})$/);
  if(req.method!=="POST"||!match)return json(res,404,{error:"Not found"});
  if(match[1]==="fail"){const b=await body(req,8192);const d=JSON.parse(b.toString());return json(res,200,{job:await jobs.failJob(match[2],d.error)})}
  if(match[1]==="qa"){const b=await body(req,16384);const d=JSON.parse(b.toString());return json(res,200,{job:await jobs.reportQA(match[2],d)})}
  if(match[1]==="stage"){const b=await body(req,8192);const d=JSON.parse(b.toString());return json(res,200,{job:await jobs.stageJob(match[2],d)})}
  const mime=(req.headers["content-type"]||"").split(";")[0],bytes=await body(req,104857600);
  return json(res,200,{job:await jobs.completeJob(match[2],bytes,mime,PUBLIC)});
 }
 if(u.pathname.startsWith("/assets/")){
  if(req.method!=="GET")return json(res,405,{error:"Method"});
  const name=u.pathname.slice(8),sig=u.searchParams.get("sig")||"",expected=jobs.assetSignature(name);
  const a=Buffer.from(sig),b=Buffer.from(expected);
  if(a.length!==b.length||!crypto.timingSafeEqual(a,b))return json(res,403,{error:"Asset forbidden"});
  const f=await jobs.assetFile(name),bytes=await fs.readFile(f);
  const mime=name.endsWith(".mp4")?"video/mp4":name.endsWith(".png")?"image/png":name.endsWith(".webp")?"image/webp":"image/jpeg";
  res.writeHead(200,{"Content-Type":mime,"Cache-Control":"private, max-age=300","Content-Length":bytes.length});return res.end(bytes);
 }
 return json(res,404,{error:"Not found"});
 }catch(e){console.error(e);if(!res.headersSent)json(res,e.code==="ENOENT"?404:400,{error:e.message})}
});
async function body(req,limit){
 const b=[];let n=0;for await(const chunk of req){n+=chunk.length;if(n>limit)throw Error("Payload too large");b.push(chunk)}return Buffer.concat(b);
}
await games.init();
await local.recoverLocalTurns();
const migrated=await games.migrateLegacyGameStyles();
if(migrated.length)console.log("Migrated style locks",migrated);
const storyBackfill=await games.migrateLegacyStoryMemories();
if(storyBackfill.length)console.log("Backfilled story events",storyBackfill);
service.listen(PORT,HOST,()=>console.log("mcp-vn http://"+HOST+":"+PORT));
