import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
import {normalizeVisualState,variantKey,assetId,visualFingerprint,sceneIntentFingerprint} from "./visual-state.mjs";
import {ensureGameStyle,requireStyle,STYLES} from "./art-style.mjs";
import {ensureMemory,patchMemory,recordEvent,closeChapterIfNeeded,queryMemory} from "./story-memory.mjs";
import {rememberScene,restoreScene} from "./scene-cache.mjs";
import {ensureRules,setRulesMode,resolveCheck,getRuleSummary} from "./game-rules.mjs";
import {pushGameEvent} from "./live-events.mjs";
import {prepareStoryCommand} from "./story-commands.mjs";
const root=process.env.VN_DATA_DIR||"/data";
const demo={
  id:"ash-gate",title:"Пепельные врата",author:"mcp-vn",source:"original",rights_confirmed:true,
  summary:"Тиррен — город на границе миров, где исчезают воспоминания.",
  lore:"В Тиррене живут люди и магические существа. Время иногда движется вспять. Любое решение меняет мир.",
  opening:"Туман опускается на рыночную площадь. Из древних ворот раздаётся голос: «Назови своё имя, странник!»",
  scene:{location:"Площадь Тиррена",background_url:"",sprites:[]},
  characters:[{id:"mira",name:"Мира",age:26,description:"Взрослая проводница в зелёном плаще, наблюдательна и осторожна."}],
  choices:["Расспросить голос","Войти в ворота","Осмотреть площадь"]
};
const id=x=>{if(typeof x!=="string"||!/^[a-zA-Z0-9_-]{1,100}$/.test(x))throw Error("Invalid id");return x};
const txt=(x,n=10000)=>{if(typeof x!=="string")throw Error("Invalid text");return x.trim().slice(0,n)};
const urls=x=>{if(!x)return "";const u=new URL(x);if(u.protocol!=="https:"||u.username||u.password)throw Error("HTTPS URL required");return u.href};
const file=(k,x)=>path.join(root,k,id(x)+".json");
async function save(k,x,data){
 if(k==="games"){normalizeVisualState(ensureGameStyle(data));ensureMemory(data);ensureRules(data)}
 const f=file(k,x),t=f+"."+randomUUID()+".tmp";
 await fs.mkdir(path.dirname(f),{recursive:true});
 await fs.writeFile(t,JSON.stringify(data),{mode:0o600});
 await fs.rename(t,f);
 if(k==="games")pushGameEvent(x,"game",{version:data.version||0,
   location:data.scene?.location||"",awaiting_narrator:!!data.awaiting_narrator});
}
async function load(k,x){return JSON.parse(await fs.readFile(file(k,x),"utf8"))}
let lock=Promise.resolve();
const serialize=fn=>{const v=lock.then(fn);lock=v.catch(()=>{});return v};
export async function init(){
 for(const x of ["stories","games","jobs","assets"]) await fs.mkdir(path.join(root,x),{recursive:true});
 try{await fs.access(file("stories","ash-gate"))}catch{await save("stories","ash-gate",demo)}
}
export async function list(kind){
 await init();const dir=kind==="stories"?"stories":"games";
 const f=(await fs.readdir(path.join(root,dir))).filter(x=>x.endsWith(".json"));
 const all=await Promise.all(f.map(x=>load(dir,x.slice(0,-5))));
 return all.map(x=>({id:x.id,title:x.title,summary:x.summary||"",hero:x.hero?.name||"",updated_at:x.updated_at||""}));
}
export async function gameGet(gameId){await init();const g=normalizeVisualState(ensureGameStyle(await load("games",gameId)));ensureMemory(g);ensureRules(g);return g}
export async function gameStart(storyId="ash-gate",hero="Макс Кроу",
 description="",artStyle="realistic",rulesMode="narrative"){
 return serialize(async()=>{await init();const s=await load("stories",storyId),now=new Date().toISOString(),gid=randomUUID();
 const game={id:gid,story_id:s.id,title:s.title,
   art_style:requireStyle(artStyle),art_style_origin:"new_game",
   art_style_locked_at:now,
   hero:{name:txt(hero,100),description:txt(description,5000)},
   story:{summary:s.summary,lore:s.lore,characters:s.characters||[]},scene:s.scene||{location:"Начало",background_url:"",sprites:[]},
   messages:[{id:randomUUID(),role:"narrator",speaker:"Рассказчик",text:s.opening,at:now}],
   choices:s.choices||[],inventory:[],relationships:{},flags:{},identities:{},memory:{},
   rules:{mode:rulesMode,stats:{strength:1,agility:1,insight:1,presence:1,arcana:1},history:[]},
   version:1,awaiting_narrator:false,
   undo_stack:[],created_at:now,updated_at:now};
 await save("games",gid,game);return game});
}
export async function migrateLegacyGameStyles(){
 await init();
 return serialize(async()=>{
  const directory=path.join(root,"games");
  const entries=(await fs.readdir(directory)).filter(x=>x.endsWith(".json"));
  const candidates=new Map();
  for(const f of (await fs.readdir(path.join(root,"jobs"))).filter(x=>x.endsWith(".json"))){
   try{
    const j=JSON.parse(await fs.readFile(path.join(root,"jobs",f),"utf8"));
    if(!STYLES.includes(j.style)||!["sprite","background"].includes(j.kind)||
       j.status!=="done"||j.spec?.preview_only)continue;
    const prior=candidates.get(j.game_id);
    if(!prior||j.created_at<prior.created_at)
     candidates.set(j.game_id,{art_style:j.style,created_at:j.created_at});
   }catch{}
  }
  const changed=[];
  for(const fname of entries){
   const gid=fname.slice(0,-5),raw=await load("games",gid);
   const original=candidates.get(gid)?.art_style;
   const wrongLegacyChoice=raw.art_style_origin==="legacy_migration"&&
      original&&raw.art_style!==original;
   if(raw.art_style&&!wrongLegacyChoice)continue;
   if(original){
    raw.art_style=original;
    raw.art_style_origin=wrongLegacyChoice?"legacy_first_art_correction":"legacy_first_art";
    raw.art_style_locked_at=new Date().toISOString();
   }else ensureGameStyle(raw);
   if(wrongLegacyChoice)raw.version=(raw.version||0)+1;
   await save("games",gid,raw);
   changed.push({id:gid,art_style:raw.art_style,corrected:!!wrongLegacyChoice});
  }
  return changed;
 });
}
export async function migrateLegacyStoryMemories(){
 await init();
 return serialize(async()=>{
  const files=(await fs.readdir(path.join(root,"games"))).filter(x=>x.endsWith(".json"));
  const results=[];
  for(const fname of files){
   const gid=fname.slice(0,-5),g=await load("games",gid);
   const memory=ensureMemory(g);
   if(memory.backfilled_at||memory.events.length||memory.turn>0)continue;
   const actions=(g.messages||[]).filter(x=>x.role==="player");
   if(!actions.length)continue;
   let turn=0;
   for(const message of g.messages||[]){
    if(message.role==="player"){
     turn++;
     recordEvent(g,{kind:"action",text:message.text,location:g.scene?.location,turn});
    }else if(message.speaker==="Рассказчик"&&turn>0&&
      /(врат|метк|час|откры|закры|переход|двойник|тайн|решил|наш[её]л)/iu.test(message.text||"")){
     recordEvent(g,{kind:"narration",text:message.text,location:g.scene?.location,turn});
    }
   }
   memory.turn=turn;
   closeChapterIfNeeded(g);
   memory.backfilled_at=new Date().toISOString();
   // No newly inferred facts, quests or relationships: only transcript-derived events.
   await save("games",gid,g);
   results.push({id:gid,turns:turn,chapters:memory.chapters.length,events:memory.events.length});
  }
  return results;
 });
}
export async function gameMemory(gameId,{query="",limit=8}={}){
 const game=await gameGet(gameId);
 const retrieved=queryMemory(game,query);
 return {memory:game.memory,retrieved:[
  ...retrieved.facts.map(x=>({kind:"fact",id:x.id,text:[x.subject,x.key,x.value].filter(Boolean).join(" — "),scope:x.scope})),
  ...retrieved.notes.map(x=>({kind:"note",id:x.id,text:x.text,scope:x.scope})),
  ...retrieved.quests.map(x=>({kind:"quest",id:x.id,text:x.title+": "+x.objective,scope:"quest"}))
 ].slice(0,limit),digest:retrieved};
}
export async function recordMemoryFact(gameId,fact){
 const scope=fact.scope==="location"?"place":fact.scope==="relationship"?"character":fact.scope;
 const payload={facts:[{scope,subject:fact.subject,key:fact.predicate,
  value:fact.value,importance:fact.confidence==="confirmed"?4:2}]};
 if(fact.source_message_id){
  const g=await gameGet(gameId);
  if(!g.messages.some(x=>x.id===fact.source_message_id))
   throw Error("Fact source_message_id not present in game transcript");
 }
 return gameMemoryPatch(gameId,payload);
}
export async function gameSetRulesMode(gameId,mode){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  setRulesMode(g,mode);
  g.version++;g.updated_at=new Date().toISOString();
  await save("games",gameId,g);
  return {game_id:gameId,version:g.version,rules:getRuleSummary(g)};
 });
}
export async function gameSkillCheck(gameId,check){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(!g.awaiting_narrator)throw Error("Skill checks are only available during narration of a pending player action");
  const result=resolveCheck(g,check);
  recordEvent(g,{kind:"rule",text:
    "Проверка "+result.stat+": "+result.total+" против "+result.difficulty+
    " — "+(result.success?"успех":"неудача"),turn:ensureMemory(g).turn+1});
  g.version++;g.updated_at=new Date().toISOString();
  await save("games",gameId,g);
  return {game_id:gameId,version:g.version,check:result,rules:getRuleSummary(g)};
 });
}
export async function gameCommand(gameId,input,version){
 const {text,command}=prepareStoryCommand(input);
 return gameAction(gameId,text,version,command);
}
export async function gameAction(gameId,action,version,command=null){
 return serialize(async()=>{const g=await gameGet(gameId);
 if(g.local_scene?.mode==="local")throw Error("Local scene active; use local_turn_begin or exit local scene");
 if(g.awaiting_narrator)throw Error("Previous turn is awaiting narration");
 if(version!==undefined&&version!==g.version)throw Error("Version conflict. Refresh.");
 const input=txt(action,5000);if(!input)throw Error("Empty action");
 g.undo_stack.push({...structuredClone(g),undo_stack:[]});g.undo_stack=g.undo_stack.slice(-10);
 const actionId=randomUUID(),submittedAt=new Date().toISOString();
 g.messages.push({id:actionId,role:"player",speaker:g.hero.name,text:input,at:submittedAt,
  ...(command?{command:structuredClone(command)}:{})});
 g.turn_metrics ||= {recent:[],last:null};
 g.turn_metrics.pending={action_id:actionId,submitted_at:submittedAt};
 recordEvent(g,{kind:"action",text:input,turn:ensureMemory(g).turn+1});
 g.choices=[];g.awaiting_narrator=true;g.version++;g.updated_at=new Date().toISOString();
 await save("games",g.id,g);return g});
}
export async function gameNarrate({game_id,messages,scene={},choices=[],inventory_add=[],
 flags={},relationships={},memory_updates={},expected_action_id}){
 return serialize(async()=>{const narratorCommitStarted=Date.now(),g=await gameGet(game_id);
 if(g.local_scene?.mode==="local")throw Error("Local scene active; ordinary GM narration is paused");
 if(!g.awaiting_narrator)throw Error("No player action pending");
 if(expected_action_id!==undefined&&expected_action_id!==g.turn_metrics?.pending?.action_id)
  throw Error("Ответ относится к прежнему ходу; сохранение уже изменилось.");
 if(!Array.isArray(messages)||messages.length<1||messages.length>12)throw Error("Narration requires 1-12 messages");
 const oldLocation=g.scene.location;
 const oldVisual=new Map((g.scene.sprites||[]).map(x=>[x.name,{
   outfit:x.outfit||"default",pose:x.pose||"standing",emotion:x.emotion||"neutral"
 }]));
 const previousDirection=g.scene.visual_direction||"";
 const turn=++ensureMemory(g).turn;
 for(const m of messages)g.messages.push({id:randomUUID(),role:"narrator",speaker:txt(m.speaker||"Рассказчик",100),text:txt(m.text,10000),at:new Date().toISOString()});
 if(scene.location!==undefined||scene.time_of_day!==undefined||scene.weather!==undefined){
  const next=scene.location!==undefined?txt(scene.location,180):g.scene.location;
  const time=scene.time_of_day!==undefined?txt(scene.time_of_day,40):
   (next===g.scene.location?g.scene.time_of_day||"":"");
  const weather=scene.weather!==undefined?txt(scene.weather,40):
   (next===g.scene.location?g.scene.weather||"":"");
  const changed=next!==g.scene.location||time!==(g.scene.time_of_day||"")||
   weather!==(g.scene.weather||"");
  if(changed){
   // Old image remains available in the cache for revisits.
   rememberScene(g);
   g.scene.background_url="";g.scene.cg_url="";g.scene.cg_basis="";
   g.scene.video_url="";g.scene.mode="layered";
   delete g.scene.environment;
  }
  g.scene.location=next;g.scene.time_of_day=time;g.scene.weather=weather;
  if(changed){
   const known=restoreScene(g,g.scene);
   if(known){
    g.scene.background_url=known.background_url;
    g.scene.background_style=known.background_style;
    if(known.environment)g.scene.environment=known.environment;
   }
  }
 }
 if(scene.environment!==undefined&&scene.environment&&typeof scene.environment==="object"){
  const env=scene.environment;
  const words=x=>Array.isArray(x)?x.slice(0,16).map(v=>txt(String(v),140)):[];
  g.scene.environment={id:txt(String(env.id||"custom"),80),positive:words(env.positive),
    negative:words(env.negative),indoor:env.indoor===true};
 }
 if(typeof scene.visual_direction==="string")
  g.scene.visual_direction=txt(scene.visual_direction,420);
 // A prompt belongs to one visual beat, never an unrelated future pose.
 if(scene.image_prompts&&typeof scene.image_prompts==="object"&&!Array.isArray(scene.image_prompts)){
  const source=scene.image_prompts,art={};
  for(const key of ["background","cg"])
   if(typeof source[key]==="string"&&source[key].trim())
    art[key]=txt(source[key],2000);
  if(source.sprites&&typeof source.sprites==="object"&&!Array.isArray(source.sprites)){
   const sprites={};
   for(const [name,prompt] of Object.entries(source.sprites).slice(0,5))
    if(typeof prompt==="string"&&prompt.trim()&&typeof name==="string"&&name.trim())
     sprites[txt(name,100)]=txt(prompt,1600);
   if(Object.keys(sprites).length)art.sprites=sprites;
  }
  g.scene.image_prompts=art;
 }else if(scene.sprites!==undefined||scene.location!==undefined||
   scene.visual_mode!==undefined||scene.visual_direction!==undefined){
  g.scene.image_prompts={};
 }
 if(scene.background_url!==undefined)g.scene.background_url=urls(scene.background_url);
 if(scene.sprites!==undefined){
 if(!Array.isArray(scene.sprites)||scene.sprites.length>8)throw Error("Too many sprites");
 g.scene.sprites=scene.sprites.map(s=>{
  const name=txt(s.name,100);
  const old=(g.scene.sprites||[]).find(x=>x.name===name)||{};
  const id=g.identities?.[name];
  const url=s.image_url?urls(s.image_url):(old.image_url||id?.base_sprite_url||"");
  const sameImage=assetId(url)===assetId(old.image_url);
  // A character cannot override the global art style by narration.
  const requestedStyle=txt(old.art_style||id?.base_style||g.art_style,40);
  // Desired appearance is driven by narration, not by the last PNG.
  // Preserve image provenance only while the image itself stays the same.
  return {name,image_url:url,
    transparent:sameImage?old.transparent===true:!!(id?.base_sprite_url&&assetId(url)===assetId(id.base_sprite_url)),
    art_style:requestedStyle,
    emotion:txt(s.emotion||old.emotion||"neutral",60),
    outfit:txt(s.outfit||old.outfit||"default",80),
    pose:txt(s.pose||old.pose||"standing",80),
    rendered_image_url:sameImage?old.rendered_image_url||old.image_url:url,
    rendered_variant_key:sameImage?old.rendered_variant_key||"":"",
    rendered_background_asset:sameImage?old.rendered_background_asset||"":""
  };
 });
 }
 // The narrator owns the art direction, but the server decides when it is
 // worth spending GPU time. No CG solely because the dialogue grew.
 const physicalChanged=oldLocation!==g.scene.location||
  oldVisual.size!==(g.scene.sprites||[]).length||
  (g.scene.sprites||[]).some(x=>{
   const prior=oldVisual.get(x.name);
   return !prior||prior.outfit!==x.outfit||prior.pose!==x.pose;
  });
 g.scene.auto_cg_requested=scene.visual_mode==="cg"?true:
  scene.visual_mode==="layers"?false:physicalChanged;
 const changedShot=physicalChanged||(scene.visual_mode==="cg"&&(
  previousDirection!==(g.scene.visual_direction||"")||
  (typeof scene.image_prompts?.cg==="string"&&scene.image_prompts.cg.trim())));
 // Revisions are part of the accepted CG fingerprint. A brand-new camera
 // instruction must not reuse an old CG whose sprite layer assets are unchanged.
 if(changedShot&&g.scene.auto_cg_requested)
  g.scene.cg_revision=(Number.isSafeInteger(g.scene.cg_revision)?
   g.scene.cg_revision:0)+1;
 if(changedShot&&g.scene.cg_url){
  // Keep previous CG if location unchanged and visual_mode is still cg
  if(oldLocation===g.scene.location&&scene.visual_mode==="cg"){
   g.scene.cg_dirty=false;g.scene.mode="cg";
  }else{
   g.scene.cg_dirty=true;g.scene.mode="layered";
  }
 }
 g.choices=(choices||[]).slice(0,6).map(x=>txt(x,200));
 for(const x of inventory_add||[]){
  const v=txt(x,180);if(v&&!g.inventory.includes(v)){
   g.inventory.push(v);
   recordEvent(g,{kind:"item",text:"Получен предмет: "+v,turn});
  }
 }
 for(const [k,v] of Object.entries(flags||{})){if(/^[\w-]{1,80}$/.test(k)&&["number","boolean","string"].includes(typeof v))g.flags[k]=v}
 for(const [k,v] of Object.entries(relationships||{})){
  if(/^[\w-]{1,80}$/.test(k)&&Number.isFinite(v)){
   const old=g.relationships[k]??0;
   g.relationships[k]=Math.max(-100,Math.min(100,old===v?v:v));
   if(old!==v)recordEvent(g,{kind:"relationship",text:"Отношение "+k+": "+old+" → "+v,turn});
  }
 }
 if(oldLocation!==g.scene.location)
  recordEvent(g,{kind:"location",text:"Переход из «"+oldLocation+"» в «"+g.scene.location+"»",turn});
 const lead=messages.filter(x=>x.speaker==="Рассказчик").at(-1)||messages.at(-1);
 recordEvent(g,{kind:"narration",text:lead.text,turn});
 patchMemory(g,memory_updates);
 closeChapterIfNeeded(g);
 g.awaiting_narrator=false;g.version++;g.updated_at=new Date().toISOString();
 g.turn_metrics ||= {recent:[],last:null};
 const pending=g.turn_metrics.pending||{};
 const pendingAt=Date.parse(pending.submitted_at||"");
 const measured={
  action_id:pending.action_id||g.messages.filter(x=>x.role==="player").at(-1)?.id,
  completed_at:g.updated_at,
  // This interval includes ChatGPT generation, scheduling, network & tool use.
  // It is deliberately NOT called pure model inference time.
  action_to_narration_ms:Number.isFinite(pendingAt)?Math.max(0,Date.now()-pendingAt):null,
  server_commit_processing_ms:Math.max(0,Date.now()-narratorCommitStarted),
  message_count:messages.length
 };
 g.turn_metrics.last=measured;
 g.turn_metrics.recent=[...(g.turn_metrics.recent||[]),measured].slice(-40);
 g.turn_metrics.pending=null;
 await save("games",g.id,g);return g});
}
// Local scenes have a deliberately separate transcript in data/local-scenes/.
// This authoritative game object carries only mode, references and a neutral bridge.
// Ordinary ChatGPT gets NO raw local-scene turns via get_game_context.
function requireAdultCast(g){
 const known=new Map((g.story?.characters||[]).map(c=>[c.name,Number(c.age)]));
 const heroAge=String(g.hero?.description||"").match(/(?:Возраст|Age)\s*:\s*(\d{1,3})/iu);
 known.set(g.hero?.name,heroAge?Number(heroAge[1]):Number(g.hero?.age));
 const cast=[...new Set((g.scene?.sprites||[]).map(s=>s.name).filter(Boolean))];
 if(!cast.includes(g.hero.name))cast.unshift(g.hero.name);
 if(cast.length<2)throw Error("At least two adult characters required for a personal scene");
 for(const name of cast){
  const age=known.get(name);
  if(!Number.isFinite(age)||age<18)throw Error("Verified adult age is required for "+name);
 }
 return cast.map(name=>({name,age:known.get(name)}));
}
export async function gameLocalSceneStart(gameId,expectedVersion){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(g.awaiting_narrator)throw Error("Complete current GM turn before changing scene mode");
  if(expectedVersion!==undefined&&expectedVersion!==g.version)throw Error("Version conflict. Refresh.");
  if(g.local_scene?.mode==="local")throw Error("Local scene already active");
  const participants=requireAdultCast(g),session_id=randomUUID(),at=new Date().toISOString();
  g.local_scene={mode:"local",session_id,participants,started_at:at,turns:0,
   pending:null,last_duration_ms:null};
  g.version++;g.updated_at=at;
  await save("games",g.id,g);
  return {game_id:g.id,version:g.version,session_id,participants,mode:"local"};
 });
}
export async function gameLocalTurnBegin(gameId,expectedVersion){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(g.local_scene?.mode!=="local")throw Error("Local scene is not active");
  if(g.local_scene.pending)throw Error("A local response is already generating");
  if(expectedVersion!==undefined&&expectedVersion!==g.version)throw Error("Version conflict. Refresh.");
  const pending={request_id:randomUUID(),submitted_at:new Date().toISOString()};
  g.local_scene.pending=pending;
  g.version++;g.updated_at=pending.submitted_at;
  await save("games",g.id,g);
  return {game_id:g.id,version:g.version,session_id:g.local_scene.session_id,...pending};
 });
}
export async function gameLocalTurnComplete(gameId,requestId,{error="",turnDelta=1}={}){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(g.local_scene?.mode!=="local"||g.local_scene.pending?.request_id!==requestId)
    throw Error("Stale local request; no changes committed");
  const at=new Date().toISOString(),started=Date.parse(g.local_scene.pending.submitted_at);
  g.local_scene.turns=Math.max(0,g.local_scene.turns+(error?0:turnDelta));
  g.local_scene.last_duration_ms=Math.max(0,Date.now()-started);
  g.local_scene.last_error=String(error).slice(0,200);
  g.local_scene.pending=null;
  g.version++;g.updated_at=at;
  await save("games",g.id,g);
  return {game_id:g.id,version:g.version,session_id:g.local_scene.session_id,
    turns:g.local_scene.turns,elapsed_ms:g.local_scene.last_duration_ms,error:g.local_scene.last_error};
 });
}
export async function gameLocalSceneStop(gameId,expectedVersion){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(g.local_scene?.mode!=="local")throw Error("Local scene is not active");
  if(g.local_scene.pending)throw Error("Wait until the local response finishes");
  if(expectedVersion!==undefined&&expectedVersion!==g.version)throw Error("Version conflict. Refresh.");
  const prior=g.local_scene,at=new Date().toISOString();
  const cast=prior.participants?.map(p=>p.name).join(" и ")||"Персонажи";
  const bridge=cast+" завершили отдельный личный эпизод. "+
   "Его подробности хранятся отдельно; основной сюжет, квесты и предметы остались без изменений.";
  g.messages.push({id:randomUUID(),role:"narrator",speaker:"Рассказчик",
   text:bridge,at});
  recordEvent(g,{kind:"narration",text:bridge,turn:ensureMemory(g).turn});
  patchMemory(g,{notes:[{scope:"story",subject:"Личный эпизод",key:prior.session_id,
    text:"Отдельный эпизод между взрослыми персонажами завершён; детали не входят в общую сюжетную память."}]});
  closeChapterIfNeeded(g);
  g.local_scene={mode:"main",last_session_id:prior.session_id,
   last_participants:prior.participants,ended_at:at,turns:prior.turns,
   last_duration_ms:prior.last_duration_ms,last_error:""};
  g.version++;g.updated_at=at;
  await save("games",g.id,g);
  return {game_id:g.id,version:g.version,mode:"main",session_id:prior.session_id,bridge};
 });
}
export async function gameMemoryPatch(gameId,updates,expectedVersion){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(expectedVersion!==undefined&&expectedVersion!==g.version)
   throw Error("Version conflict. Refresh memory before updating.");
  const changed=patchMemory(g,updates);
  g.version++;g.updated_at=new Date().toISOString();
  await save("games",g.id,g);
  return {game_id:g.id,version:g.version,changed,memory:queryMemory(g)};
 });
}
export async function gameMemorySearch(gameId,query){
 const g=await gameGet(gameId);return queryMemory(g,query);
}
// Rebuild an initially empty canonical cast from established NPCs in
// recent narration. Never invent a character or actions for the protagonist.
export async function gameEnsureSceneCast(gameId){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(g.awaiting_narrator||g.local_scene?.mode==="local"||
     (g.scene?.sprites||[]).length)return g;
  const statements=(g.messages||[]).filter(x=>x.role==="narrator").slice(-3);
  const recent=statements.map(m=>String(m.text||"")).join(" ");
  const speakers=new Set(statements.map(m=>m.speaker).filter(Boolean));
  const cast=(g.story?.characters||[]).filter(c=>{
   const name=String(c?.name||"").trim();
   if(!name||name===g.hero?.name)return false;
   if(!speakers.has(name)&&!recent.includes(name))return false;
   if([" ушла"," покинула"," исчезла"].some(s=>recent.includes(name+s)))
    return false;
   return true;
  }).slice(0,3);
  if(!cast.length)return g;
  g.scene.sprites=cast.map(c=>({
   name:c.name,image_url:"",transparent:false,art_style:g.art_style,
   outfit:String(c.description||"travelling outfit").slice(0,80),
   pose:"standing",emotion:"neutral",rendered_variant_key:"",
   rendered_background_asset:""
  }));
  g.version++;g.updated_at=new Date().toISOString();
  await save("games",g.id,g);
  return normalizeVisualState(g);
 });
}
export async function gameRetry(gameId,note="",expectedVersion){
 if(typeof note!=="string"||note.length>2000)throw Error("Уточнение: не более 2000 символов");
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(expectedVersion!==undefined&&expectedVersion!==g.version)throw Error("Версия сохранения изменилась. Обнови историю.");
  if(g.local_scene?.mode==="local"||g.awaiting_narrator)throw Error("Дождись окончания текущего хода.");
  const before=g.undo_stack.at(-1);
  const action=g.messages.filter(x=>x.role==="player").at(-1);
  if(!before||!action)throw Error("Нет завершённого ответа для повтора.");
  const restored=structuredClone(before),at=new Date().toISOString();
  restored.undo_stack=g.undo_stack;
  const next={...structuredClone(action),id:randomUUID(),at,
   command:{...(action.command||{name:"action",argument:""}),retry_note:note.trim()}};
  restored.messages.push(next);
  recordEvent(restored,{kind:"action",text:next.text,turn:ensureMemory(restored).turn+1});
  restored.turn_metrics||={recent:[],last:null};
  restored.turn_metrics.pending={action_id:next.id,submitted_at:at};
  restored.choices=[];restored.awaiting_narrator=true;
  restored.version=g.version+1;restored.updated_at=at;
  await save("games",gameId,restored);return restored;
 });
}
export async function gameUndo(gameId,expectedVersion){
 return serialize(async()=>{const g=await gameGet(gameId);
 if(expectedVersion!==undefined&&expectedVersion!==g.version)throw Error("Версия сохранения изменилась. Обнови историю.");
 if(g.local_scene?.mode==="local")throw Error("Exit local scene before undo");
 if(g.awaiting_narrator)throw Error("Narration pending");
 const before=g.undo_stack.pop();if(!before)throw Error("Nothing to undo");
 before.undo_stack=g.undo_stack;before.version=g.version+1;before.updated_at=new Date().toISOString();
 await save("games",gameId,before);return before});
}
export async function attachImage(gameId,{kind="background",character="",url,style="",
  expected_location=null,face_url="",variant=null,preserve_mode=false,composition=""}){
 return serialize(async()=>{
 const g=await gameGet(gameId);
 if(style&&style!==g.art_style)
  return {applied:false,reason:"Image style does not match game's locked style"};
 if(expected_location!==null&&g.scene.location!==expected_location)
  return {applied:false,reason:"Location changed"};
 if(kind==="background"){
  g.scene.background_url=urls(url);
  g.scene.background_style=txt(style||g.scene.background_style||"realistic",40);
  rememberScene(g);
  g.scene.cg_url="";g.scene.cg_basis="";g.scene.cg_composition="";
  g.scene.cg_dirty=false;g.scene.mode="layered";
 }else if(kind==="scene"){
  normalizeVisualState(g);
  if(composition!=="neural_story"&&g.scene.sprites.some(s=>s.visual_dirty))
   return {applied:false,reason:"Stale character appearance; regenerate affected sprites first"};
  g.scene.cg_url=urls(url);
  g.scene.cg_style=txt(style||"realistic",40);
  g.scene.cg_composition=composition==="neural_story"?"neural_story":"anchored_composite";
  g.scene.cg_basis=g.scene.cg_composition==="neural_story"?
   sceneIntentFingerprint(g.scene):visualFingerprint(g.scene);
  g.scene.cg_dirty=false;
  g.scene.mode="cg";
 }else if(kind==="sprite"){
  const name=txt(character,100);
  if(!name)throw Error("Character required");
  // Preserve order and fixed character placement rather than appending a replaced sprite at the end.
  const current=(g.scene.sprites||[]).find(s=>s.name===name)||{};
  const desired=variant&&typeof variant==="object"?variant:{};
  const expectedOutfit=txt(desired.outfit||current.outfit||"default",80);
  const expectedPose=txt(desired.pose||current.pose||"standing",80);
  const expectedEmotion=txt(desired.emotion||current.emotion||"neutral",60);
  // A queued job cannot undo a later narrative change by publishing late.
  if(current.name&&(current.outfit!==expectedOutfit||current.pose!==expectedPose||
     current.emotion!==expectedEmotion))
   return {applied:false,reason:"Desired character state changed while generating"};
  const item={name,image_url:urls(url),emotion:expectedEmotion,
    pose:expectedPose,outfit:expectedOutfit,art_style:txt(style||"realistic",40),
    transparent:true,rendered_image_url:urls(url),
    rendered_background_asset:assetId(g.scene.background_url)};
  item.rendered_variant_key=variantKey(item);
  item.desired_variant_key=item.rendered_variant_key;
  item.visual_dirty=false;
  item.visual_status="ready";
  g.identities ||= {};
  const identity=g.identities[name]||{name,variants:{},base_sprite_url:"",face_url:""};
  // Canonical anchor is immutable: subsequent clothing/pose changes do not redefine identity.
  if(!identity.base_sprite_url){
   identity.base_sprite_url=urls(url);
   identity.base_style=style||"realistic";
   if(face_url)identity.face_url=urls(face_url);
   identity.created_at=new Date().toISOString();
  }
  identity.last_sprite_url=urls(url);
  identity.last_updated=new Date().toISOString();
  identity.variants ||= {};
  identity.variant_backgrounds ||= {};
  const key=variantKey(item);
  identity.variants[key]=urls(url);
  identity.variant_backgrounds[key]=assetId(g.scene.background_url);
  if(Object.keys(identity.variants).length>50){
   const oldest=Object.keys(identity.variants)[0];
   delete identity.variants[oldest];
   delete identity.variant_backgrounds[oldest];
  }
  g.identities[name]=identity;
  const pos=(g.scene.sprites||[]).findIndex(s=>s.name===name);
  if(pos>=0)g.scene.sprites[pos]=item;
  else (g.scene.sprites||=[]).push(item);
  // Every character revision invalidates the existing CG composition.
  // Transparent layers are not part of an independent neural-CG fingerprint.
  if(g.scene.cg_url&&g.scene.cg_composition!=="neural_story"){
   g.scene.cg_dirty=true;g.scene.cg_basis="";
  }
  if(!preserve_mode)g.scene.mode="layered";
 }else if(kind==="video")g.scene.video_url=urls(url);
 else throw Error("Unknown media kind");
 g.version++;g.updated_at=new Date().toISOString();
 await save("games",gameId,g);return {applied:true,version:g.version};
 });
}

export async function storeBackgroundVariant(gameId,{location,style,url,time_of_day="",weather=""}){
 return serialize(async()=>{
  const g=await gameGet(gameId);
  if(style!==g.art_style)throw Error("Background style differs from this game");
  const saved=rememberScene(g,{location,time_of_day,weather,
    background_url:urls(url),background_style:style});
  g.version++;g.updated_at=new Date().toISOString();
  await save("games",gameId,g);
  return {applied:true,key:saved.key,library_only:true,version:g.version};
 });
}
export async function storeCharacterVariant(gameId,{character,style,variant,url,background_asset}){
 return serialize(async()=>{
  const g=await gameGet(gameId),identity=g.identities?.[character];
  if(!identity?.base_sprite_url)throw Error("Cannot prebuild variants without a canonical character");
  if(g.art_style!==style)throw Error("Character style differs from the game");
  const sprite=(g.scene?.sprites||[]).find(s=>s.name===character);
  if(!sprite)throw Error("Character left the visible scene");
  const key=variantKey({art_style:style,...variant});
  const v=urls(url);
  identity.variants ||= {};
  identity.variant_backgrounds ||= {};
  identity.variants[key]=v;
  identity.variant_backgrounds[key]=String(background_asset||"");
  identity.updated_at=new Date().toISOString();
  g.version++;g.updated_at=new Date().toISOString();
  await save("games",gameId,g);
  return {applied:true,version:g.version,key,asset_url:v,library_only:true};
 });
}
export async function importStory(doc){
 return serialize(async()=>{await init();const x=typeof doc==="string"?JSON.parse(doc):doc;
 if(!x||x.rights_confirmed!==true||!["original","user-owned","licensed"].includes(x.source))throw Error("Reuse rights must be confirmed");
 for(const k of ["title","opening","author"])if(!x[k])throw Error("Missing "+k);
 if((x.characters||[]).some(c=>c.age!==undefined&&Number(c.age)<18||c.age_group==="minor"))throw Error("Minor characters are not permitted in this game library");
 const sid=randomUUID(),s={id:sid,title:txt(x.title,180),opening:txt(x.opening),author:txt(x.author,100),source:x.source,rights_confirmed:true,
 summary:txt(x.summary||"",2000),lore:txt(x.lore||"",25000),scene:x.scene||{location:"Начало",background_url:"",sprites:[]},
 characters:(x.characters||[]).slice(0,60),choices:(x.choices||[]).slice(0,6)};
 await save("stories",sid,s);return{id:sid,title:s.title}});
}
export const dataRoot=root;
