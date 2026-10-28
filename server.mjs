import http from "node:http";
import fs from "node:fs/promises";
import crypto from "node:crypto";
import {McpServer} from "@modelcontextprotocol/sdk/server/mcp.js";
import {StreamableHTTPServerTransport} from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import {registerAppTool,registerAppResource,RESOURCE_MIME_TYPE} from "@modelcontextprotocol/ext-apps/server";
import {z} from "zod";
import * as games from "./src/game-store.mjs";
import * as jobs from "./src/jobs.mjs";
import {waitGameEvents,eventStats} from "./src/live-events.mjs";
import {makeNarrationPacket} from "./src/narration-packet.mjs";
import {makeGameDelta,compactJob} from "./src/game-delta.mjs";
import {measureTurnPerformance} from "./src/turn-performance.mjs";
import {appendTrace,makeTraceReport} from "./src/turn-trace.mjs";
import * as local from "./src/local-scene.mjs";
import {scheduleStandaloneVisuals} from "./src/standalone-visuals.mjs";
import {executeStandaloneCommand,standaloneContext} from "./src/standalone-commands.mjs";

const PORT=Number(process.env.VN_PORT||3100),HOST=process.env.VN_HOST||"127.0.0.1";
const WORKER_KEY=process.env.VN_WORKER_TOKEN||"",MCP_KEY=process.env.VN_MCP_TOKEN||"";
const PUBLIC=(process.env.VN_PUBLIC_ORIGIN||"https://xavoks.jo3.org/vn").replace(/\/$/,"");
// UI resource URIs are cache keys for the ChatGPT MCP Apps host.
const UI="ui://mcp-vn/visual-novel-v64.html";
const LEGACY_UI=["ui://mcp-vn/visual-novel.html","ui://mcp-vn/visual-novel-v2.html","ui://mcp-vn/visual-novel-v3.html","ui://mcp-vn/visual-novel-v4.html","ui://mcp-vn/visual-novel-v5.html","ui://mcp-vn/visual-novel-v51.html","ui://mcp-vn/visual-novel-v52.html","ui://mcp-vn/visual-novel-v53.html","ui://mcp-vn/visual-novel-v54.html","ui://mcp-vn/visual-novel-v55.html","ui://mcp-vn/visual-novel-v56.html","ui://mcp-vn/visual-novel-v57.html","ui://mcp-vn/visual-novel-v58.html","ui://mcp-vn/visual-novel-v59.html","ui://mcp-vn/visual-novel-v60.html","ui://mcp-vn/visual-novel-v61.html","ui://mcp-vn/visual-novel-v62.html","ui://mcp-vn/visual-novel-v63.html"];
const UI_META={ui:{csp:{resourceDomains:[new URL(PUBLIC).origin],connectDomains:[]},prefersBorder:false}};
const TOOL_UI_META={ui:{resourceUri:UI},"openai/outputTemplate":UI};
if(HOST!=="127.0.0.1"&&(!WORKER_KEY||!MCP_KEY))throw Error("Both VN_WORKER_TOKEN and VN_MCP_TOKEN required on LAN");
const result=(key,value)=>({content:[{type:"text",text:JSON.stringify({[key]:value})}],structuredContent:{[key]:value}});
const safe=fn=>async a=>{try{return await fn(a||{})}catch(e){return{isError:true,content:[{type:"text",text:e.message||"Unknown error"}]}}};
const Z=z.string();
function mcpServer(){
 const m=new McpServer({name:"mcp-vn",version:"0.7.0"});
 // Serve current and legacy cache keys so pre-refresh snapshots never break.
 for(const [index,uri] of [...LEGACY_UI,UI].entries()){
   registerAppResource(m,"visual-novel-"+index,uri,{mimeType:RESOURCE_MIME_TYPE,_meta:UI_META},
    async()=>({contents:[{uri,mimeType:RESOURCE_MIME_TYPE,
      text:await fs.readFile("./dist/index.html","utf8"),_meta:UI_META}]})
   );
 }
 const openSavedGame=safe(async({game_id})=>{
   if(game_id)return result("game",await games.gameGet(game_id));
   const sessions=await games.list("games");
   const latest=sessions.sort((a,b)=>(b.updated_at||"").localeCompare(a.updated_at||""))[0];
   return result("game",latest?await games.gameGet(latest.id):await games.gameStart());
 });
 registerAppTool(m,"open_game",{
   title:"Visual novel",description:"Open the v4 visual novel with composited transparent sprites, scene CG, art QA and free-text input.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 // Deliberately new tool name to invalidate cached tool/UI metadata after Refresh.
 registerAppTool(m,"open_game_latest",{
   title:"Visual novel — latest UI",description:"Open the latest visual novel v4 UI with coherent art and quality status.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 // Cache bust for clients retaining the former open_game_latest metadata.
 registerAppTool(m,"open_game_v4",{
   title:"Visual novel — cinematic v4",
   description:"Open cinematic v4 UI: common background, transparent character layers, scene CG and art validation.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v5",{
   title:"Visual novel — identity v5",
   description:"Open v5 visual novel with location consistency, canonical character identities, realtime job progress and timing metrics.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 // Fresh cache key for visual-state synchronization and adaptive scene sizing.
 registerAppTool(m,"open_game_v51",{
   title:"Visual novel — live visuals v5.1",
   description:"Open visual novel v5.1 with desired/rendered character state, automatic sprite updates and flexible full-height scene.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v52",{
   title:"Visual novel — consistent playthrough v5.2",
   description:"Open v5.2 with game-locked art style, cached character variants, precise per-attempt timing, and preview generation.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v53",{
   title:"Visual novel — living world v5.3",
   description:"Open v5.3 with episodic story memory, character/world facts and incremental scene updates.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v54",{
   title:"Visual novel — responsive v5.4",
   description:"Open v5.4 with low-latency live game/job events, cached poses and established story memory.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v55",{
   title:"Visual novel — fast narration v5.5",
   description:"Open v5.5 with compact AI narrator packets, turn latency measurements and instant visual progress updates.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v56",{
   title:"Visual novel — turn diagnostics v5.6",
   description:"Open v5.6 with precise host/GM/tool/UI stage instrumentation and live latency diagnostics.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v57",{
   title:"Visual novel — private local episodes v5.7",
   description:"Open v5.7: optional on-device adult romantic scenes with separate transcripts and canonical non-explicit story bridge.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v58",{
   title:"Visual novel — dynamic local CG and improved dialogue v5.8",
   description:"Open v5.8: improved local narrator, independently rendered CG with pose presets, and hide/show illustration.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v59",{
   title:"Visual novel — automatic visual direction v5.9",
   description:"Open v5.9 with automatic on-device scene direction, synchronized local CG in the main stage and a collapsed chat duplicate.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v60",{
   title:"Visual novel — persistent freeform visual state and neural scenes",
   description:"Open v6.0: persistent character clothes, equipment, arbitrary poses and locations, GPU-generated whole-scene CG and optional video.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v61",{
   title:"Visual novel — scene fidelity and validated visual continuity v6.1",
   description:"Open v6.1: independent scene count/location QA, trustworthy CG continuity and verified video source.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v62",{
   title:"Visual novel — enhanced local scene consistency v6.2",
   description:"Open v6.2: specialized CG model, visual reconciliation, advisory pose QA, and visual replan.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v63",{
   title:"Visual novel — distinct anime and animation styles v6.3",
   description:"Open v6.3: Pony realism/semirealism, WAI anime, separate Anima animated-illustration style.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 registerAppTool(m,"open_game_v64",{
   title:"Visual novel — selective local rendering v6.4",
   description:"Open v6.4: Cydonia narrator, Qwen director, portrait CG fit/fill, cached sprites, selective CG.",
   inputSchema:{game_id:Z.optional()},_meta:TOOL_UI_META
 },openSavedGame);
 m.tool("list_stories","List story packs ready to play.",{},safe(async()=>result("stories",await games.list("stories"))));
 m.tool("list_games","List saved game sessions.",{},safe(async()=>result("games",await games.list("games"))));
 m.tool("start_game","Start another game (previous saves stay intact).",
 {story_id:Z.default("ash-gate"),hero_name:Z.default("Макс Кроу"),hero_description:Z.default(""),
  art_style:z.enum(["realistic","semireal","anime","animation","poster"]).default("realistic"),
  rules_mode:z.enum(["narrative","adventure"]).default("narrative")},
 safe(async({story_id,hero_name,hero_description,art_style,rules_mode})=>
  result("game",await games.gameStart(story_id,hero_name,hero_description,art_style,rules_mode))));
 m.tool("set_rules_mode","Switch between free narrative and optional RPG checks; existing state is preserved.",
  {game_id:Z,mode:z.enum(["narrative","adventure"])},
  safe(async({game_id,mode})=>result("rules",await games.gameSetRulesMode(game_id,mode))));
 m.tool("resolve_skill_check","Only for optional adventure mode. Record a d20 roll against a difficulty; narrator should use this result, never invent dice.",
  {game_id:Z,stat:z.enum(["strength","agility","insight","presence","arcana"]),
   difficulty:z.number().int().min(5).max(30).default(12),
   advantage:z.number().int().min(-1).max(1).default(0),
   description:Z.optional()},
  safe(async({game_id,...check})=>result("rule_check",await games.gameSkillCheck(game_id,check))));
 m.tool("get_game","Full game state for scrolling transcript and scene rendering.",
 {game_id:Z},safe(async({game_id})=>result("game",await games.gameGet(game_id))));
 m.tool("wait_for_game_events","Wait up to 10 seconds for compact game/asset events. No direct web connection or exposed credentials.",
 {game_id:Z,boot_id:Z.optional(),after_seq:z.number().int().min(0).default(0),
  wait_ms:z.number().int().min(0).max(12000).default(7500)},
 safe(async({game_id,boot_id,after_seq,wait_ms})=>{
  await games.gameGet(game_id); // Verify game exists without disclosing cross-game events.
  return result("events",await waitGameEvents(game_id,{boot_id,after_seq,wait_ms}));
 }));
 m.tool("get_live_diagnostics","Number of active event subscriptions (no private game data).",{},
 safe(async()=>result("live_stats",eventStats())));
 m.tool("get_game_updates","Lightweight incremental game status; returns only changed state after a known version.",
 {game_id:Z,after_version:z.number().int().min(0).default(0)},
 safe(async({game_id,after_version})=>{
  const g=await games.gameGet(game_id);
  return result("update",g.version>after_version?{changed:true,version:g.version,game:g}:
    {changed:false,version:g.version,awaiting_narrator:g.awaiting_narrator});
 }));
 m.tool("get_live_delta","Incremental state since client cursor, and compact art job summaries. Does not retransmit full transcript on normal updates.",
 {game_id:Z,known_version:z.number().int().min(0).default(0),
  known_messages:z.number().int().min(0).default(0),
  known_last_id:Z.optional(),known_jobs:Z.optional()},
 safe(async({game_id,known_version,known_messages,known_last_id,known_jobs})=>{
   const g=await games.gameGet(game_id);
   const list=(await jobs.jobsForGame(game_id)).slice(0,18).map(compactJob);
   const digest=crypto.createHash("sha256").update(JSON.stringify(list.slice(0,10).map(j=>
    [j.id,j.status,j.stage,j.attempts,j.quality_status,j.applied,j.finished_at,j.timings?.total_ms])))
    .digest("hex").slice(0,16);
   const patch=makeGameDelta(g,{known_version,known_messages,known_last_id:known_last_id||""});
   return result("live_delta",{
     game_patch:patch,version:g.version,
     jobs:digest!==known_jobs?list:null,jobs_digest:digest
   });
 }));
 m.tool("list_art_jobs_ui","Compact image-job progress for the VN interface without prompts or workflow metadata.",
 {game_id:Z},safe(async({game_id})=>
   result("jobs",(await jobs.jobsForGame(game_id)).slice(0,18).map(compactJob))));
 m.tool("get_live_updates","Lightweight merged game-and-art polling: returns unchanged status without the full transcript or jobs payload.",
 {game_id:Z,known_version:z.number().int().min(0).default(0),known_jobs:Z.optional()},
 safe(async({game_id,known_version,known_jobs})=>{
  const g=await games.gameGet(game_id),list=(await jobs.jobsForGame(game_id)).slice(0,15);
  const digest=crypto.createHash("sha256").update(JSON.stringify(list.slice(0,8).map(j=>
    [j.id,j.status,j.stage,j.attempts,j.quality_status,j.applied,j.finished_at,j.timings?.total_ms])))
    .digest("hex").slice(0,16);
  return result("live",{game:g.version!==known_version?g:null,version:g.version,
    jobs:digest!==known_jobs?list:null,jobs_digest:digest});
 }));
 m.tool("update_story_memory","Add/update persistent world facts, character notes, quest states and chapter summaries.",
 {game_id:Z,memory_updates:z.object({
  facts:z.array(z.object({scope:Z.optional(),subject:Z,key:Z.optional(),value:Z,
   importance:z.number().optional(),keywords:z.array(Z).optional(),active:z.boolean().optional()})).optional(),
  quests:z.array(z.object({id:Z.optional(),title:Z,status:Z.optional(),
   description:Z.optional(),objective:Z.optional()})).optional(),
  notes:z.array(z.object({subject:Z,scope:Z.optional(),key:Z.optional(),text:Z})).optional(),
  chapter_summary:Z.optional()}),expected_version:z.number().optional()},
 safe(async({game_id,memory_updates,expected_version})=>result("memory_updated",
   await games.gameMemoryPatch(game_id,memory_updates,expected_version))));
 m.tool("get_story_memory","Retrieve chapter/arc digests, persistent world facts, and relevant past events.",
 {game_id:Z,query:Z.optional(),limit:z.number().int().min(1).max(30).default(8)},
 safe(async({game_id,query,limit})=>
   result("story_memory",await games.gameMemory(game_id,{query:query||"",limit}))));
 m.tool("record_story_fact","Store a verified world/character/quest fact with provenance and revision history.",
 {game_id:Z,subject:Z,predicate:Z,value:Z,
  scope:z.enum(["world","character","quest","location","relationship"]).default("world"),
  confidence:z.enum(["confirmed","inferred","rumor"]).default("confirmed"),
  source_message_id:Z.optional()},
 safe(async({game_id,...fact})=>result("recorded",await games.recordMemoryFact(game_id,fact))));

 m.tool("report_turn_client_event","Record privacy-minimal host-acceptance or UI-render timestamps for a player action. Diagnostic only, does not change game.",
 {game_id:Z,action_id:Z,phase:z.enum(["host_ack","host_error","ui_render"]),
  client_started_at_ms:z.number().optional(),client_finished_at_ms:z.number().optional(),
  submit_rpc_ms:z.number().optional(),host_ack_ms:z.number().optional(),
  ui_render_ms:z.number().optional(),detail:Z.optional(),commit_version:z.number().optional()},
 safe(async({game_id,...event})=>{
  const g=await games.gameGet(game_id);
  if(!g.messages.some(m=>m.id===event.action_id&&m.role==="player"))
    throw Error("Trace action not present in game");
  const saved=await appendTrace(game_id,event);
  return result("trace_ack",{action_id:saved.action_id,phase:saved.phase,server_received_at_ms:saved.server_received_at_ms});
 }));
 m.tool("get_turn_trace","Observe action, host acceptance, GM tool arrival, processing and UI delivery timestamps. No private dialogue content.",
 {game_id:Z,limit:z.number().int().min(1).max(30).default(12)},
 safe(async({game_id,limit})=>{
  const g=await games.gameGet(game_id);
  return result("turn_trace",await makeTraceReport(game_id,g,{limit}));
 }));
 m.tool("get_turn_performance","Observed full-turn latency and accurate recent action-to-narration timings. Does not claim model-only inference timing.",
 {game_id:Z,limit:z.number().int().min(1).max(30).default(12)},
 safe(async({game_id,limit})=>
   result("performance",measureTurnPerformance(await games.gameGet(game_id),{limit}))));
 m.tool("get_narration_packet","Compact authoritative player action, story memory and character context. No art jobs or asset URLs.",
 {game_id:Z},safe(async({game_id})=>result("packet",makeNarrationPacket(await games.gameGet(game_id)))));
 m.tool("get_game_context","Compact narration context by default. Use detail=full only for debugging; a packet supplied by the VN UI already contains this context.",
 {game_id:Z,detail:z.enum(["compact","full"]).default("compact")},
 safe(async({game_id,detail})=>{
  const g=await games.gameGet(game_id);
  if(detail==="compact")return result("context",makeNarrationPacket(g));
  const recall=await games.gameMemorySearch(game_id,g.messages.at(-1)?.text||"");
  return result("context",{id:g.id,version:g.version,art_style:g.art_style,story:g.story,hero:g.hero,scene:g.scene,flags:g.flags,
   inventory:g.inventory,relationships:g.relationships,rules:g.rules,
   awaiting_narrator:g.awaiting_narrator,
   memory_digest:recall,identities:g.identities||{},latest_messages:g.messages.slice(-24),
   art_jobs:await jobs.jobsForGame(game_id)});
 }));
 m.tool("local_model_health","Check the on-device language model and GPU gate without exposing scene text.",
 {},safe(async()=>result("local_model",await local.localHealth())));
 m.tool("local_scene_start","Opt into a separate private-on-server adult romantic scene. Only confirmed adult cast; no inference without player actions.",
 {game_id:Z,expected_version:z.number().optional()},
 safe(async({game_id,expected_version})=>
  result("local_scene",await local.beginLocalScene(game_id,expected_version))));
 m.tool("local_scene_end","Exit a local romantic episode, save only a neutral canonical bridge, and resume normal ChatGPT play.",
 {game_id:Z,expected_version:z.number().optional()},
 safe(async({game_id,expected_version})=>
  result("local_scene",await local.exitLocalScene(game_id,expected_version))));
 m.tool("local_turn_submit","Record local-only player input then generate asynchronously on the user's computer. Never routes content to ChatGPT.",
 {game_id:Z,action:Z,expected_version:z.number().optional()},
 safe(async({game_id,action,expected_version})=>
  result("local_request",await local.submitLocalTurn(game_id,action,expected_version))));
 m.tool("local_scene_replan","Reconcile the most recent visual scene without submitting another player action.",
 {game_id:Z},safe(async({game_id})=>
  result("local_replan",await local.replanLocalScene(game_id))));
 m.tool("local_episode_status","Read separate local episode dialogue and generation status for authorized VN UI. Not part of ChatGPT narrator context.",
 {game_id:Z,session_id:Z.optional()},
 safe(async({game_id,session_id})=>
  result("local_episode",await local.getLocalEpisode(game_id,{session_id}))));
 m.tool("queue_local_cg","Create an independent GPU-generated scene from the persistent freeform visual state. An optional description can override camera framing.",
 {game_id:Z,direction:Z.optional(),
  quality:z.enum(["fast","standard","cinematic"]).default("standard")},
 safe(async({game_id,direction,quality})=>
  result("job",await local.queueLocalCG(game_id,{direction,quality}))));
 m.tool("queue_local_video","Optionally animate the most recent accepted local CG via ComfyUI Wan2.2. Never changes canonical story state.",
 {game_id:Z,motion:Z.optional()},
 safe(async({game_id,motion})=>
  result("job",await local.queueLocalVideo(game_id,{motion}))));
 m.tool("submit_action_fast","Preferred for v5.5 VN UI: save action, return just the accepted action, version, and a compact authoritative narration packet.",
 {game_id:Z,action:Z,expected_version:z.number().optional()},
 safe(async({game_id,action,expected_version})=>{
   const g=await games.gameAction(game_id,action,expected_version);
   return result("submitted",{
     id:g.id,version:g.version,awaiting_narrator:g.awaiting_narrator,
     action:g.messages.at(-1),submitted_at:g.turn_metrics?.pending?.submitted_at,
     undo_count:g.undo_stack?.length||0,
     narration_packet:makeNarrationPacket(g)
   });
 }));
 m.tool("submit_action","Record a free-text user action once. Also return the full game for legacy clients and a compact narration packet for fast VN UI dispatch.",
 {game_id:Z,action:Z,expected_version:z.number().optional()},
 safe(async({game_id,action,expected_version})=>{
   const game=await games.gameAction(game_id,action,expected_version);
   const narration_packet=makeNarrationPacket(game);
   const data={game,narration_packet};
   return {content:[{type:"text",text:JSON.stringify(data)}],structuredContent:data};
 }));
 const narrationSchema = {game_id:Z,messages:z.array(z.object({speaker:Z,text:Z})).min(1).max(12),
 scene:z.object({location:Z.optional(),time_of_day:Z.optional(),weather:Z.optional(),background_url:Z.optional(),
 environment:z.object({id:Z.optional(),positive:z.array(Z),negative:z.array(Z).optional(),
 indoor:z.boolean().optional()}).optional(),
 sprites:z.array(z.object({name:Z,image_url:Z,emotion:Z.optional(),outfit:Z.optional(),pose:Z.optional()})).optional()}).optional(),
 choices:z.array(Z).optional(),inventory_add:z.array(Z).optional(),
 flags:z.record(z.union([Z,z.number(),z.boolean()])).optional(),relationships:z.record(z.number()).optional(),
 memory_updates:z.object({
   facts:z.array(z.object({scope:Z.optional(),subject:Z,key:Z.optional(),value:Z,
     importance:z.number().optional(),keywords:z.array(Z).optional()})).optional(),
   quests:z.array(z.object({id:Z.optional(),title:Z,status:Z.optional(),
     objective:Z.optional(),description:Z.optional()})).optional(),
   notes:z.array(z.object({subject:Z,scope:Z.optional(),key:Z.optional(),text:Z})).optional(),
   chapter_summary:Z.optional()
 }).optional()};
 async function tracedNarration(a){
  const game=await games.gameGet(a.game_id);
  const action_id=game.turn_metrics?.pending?.action_id||
    game.messages.filter(x=>x.role==="player").at(-1)?.id;
  if(action_id)await appendTrace(a.game_id,{action_id,phase:"gm_invoked"});
  const committed=await games.gameNarrate(a);
  if(action_id)await appendTrace(a.game_id,{action_id,phase:"gm_committed",commit_version:committed.version});
  return committed;
 }
 m.tool("gm_continue","Narrator: continue after the pending action. For fast UI narrations, prefer gm_continue_fast. Never choose actions for the player.",
 narrationSchema,
 safe(async(a)=>result("game",await tracedNarration(a))));
 m.tool("gm_continue_fast","Preferred for VN UI: commit narrator text and story facts once. Returns a small acknowledgement instead of the complete game transcript.",
 narrationSchema,
 safe(async(a)=>{
   const g=await tracedNarration(a);
   return result("commit",{
     game_id:g.id,version:g.version,awaiting_narrator:g.awaiting_narrator,
     messages_committed:a.messages.length,
     last_turn:g.turn_metrics?.last||null,
     scene_dirty:!!g.scene?.background_dirty||!!g.scene?.cg_dirty||
       !!g.scene?.sprites?.some(s=>s.visual_dirty)
   });
 }));
 m.tool("undo_last_turn","Undo last complete player/narrator turn.",
 {game_id:Z},safe(async({game_id})=>result("game",await games.gameUndo(game_id))));
 m.tool("queue_art","Create image/video with local ComfyUI on user's own GPU. No ISEKAI credits. Use for new scenes and characters. Style anime/animation/semireal/realistic/poster.",
 {game_id:Z,prompt:Z,kind:z.enum(["background","sprite","scene","video"]).default("background"),
 style:z.enum(["anime","animation","semireal","realistic","poster"]).optional(),
 quality:z.enum(["fast","standard","cinematic"]).default("standard"),
 preview_only:z.boolean().optional(),library_only:z.boolean().optional(),
 target_location:Z.optional(),target_time_of_day:Z.optional(),target_weather:Z.optional(),
 priority:z.number().min(0).max(100).optional(),force:z.boolean().optional(),
 character:Z.optional(),outfit:Z.optional(),pose:Z.optional(),emotion:Z.optional()},
 safe(async(a)=>result("job",await jobs.enqueue(a))));
 m.tool("warm_next_locations","Optionally pre-generate up to two grounded, explicitly known future locations at low GPU priority. Stores assets in scene cache; never moves the player or changes active background.",
 {game_id:Z,scenes:z.array(z.object({location:Z,description:Z.optional(),
    time_of_day:Z.optional(),weather:Z.optional()})).min(1).max(2)},
 safe(async({game_id,scenes})=>result("prefetch",await jobs.warmNextLocations(game_id,scenes))));
 m.tool("warm_character_variants","Quietly prepare 1-3 reusable emotional sprites per visible adult character on the local GPU, low-priority and without changing the current scene.",
 {game_id:Z,characters:z.array(Z).max(4).optional(),
  emotions:z.array(Z).max(3).optional(),
  quality:z.enum(["fast","standard","cinematic"]).default("standard")},
 safe(async({game_id,characters,emotions,quality})=>
  result("warmup",await jobs.warmCharacterVariants(game_id,{characters,emotions,quality}))));
 m.tool("get_character_identities","Return the canonical character image references for a saved game.",
 {game_id:Z},safe(async({game_id})=>result("identities",(await games.gameGet(game_id)).identities||{})));
 m.tool("ensure_character_anchors","Register existing approved transparent sprites as immutable character base references and create face crops. Does not overwrite already registered identities.",
 {game_id:Z},safe(async({game_id})=>result("anchors",await jobs.ensureCharacterAnchors(game_id,PUBLIC))));
 m.tool("list_art_jobs","Get game image and video generation progress.",
 {game_id:Z},safe(async({game_id})=>result("jobs",await jobs.jobsForGame(game_id))));
 m.tool("import_story","Import explicitly user-owned or licensed JSON story pack. No copying other creators' stories without permission.",
 {package_json:Z},safe(async({package_json})=>result("imported",await games.importStory(package_json))));
 return m;
}
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
  // The web frontend never receives WORKER_KEY or MCP_KEY.
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
     id:j.id,kind:j.kind,character:j.character||"",status:j.status,
     stage:j.stage||"",applied:!!j.applied,
     error:String(j.error||"").slice(0,180),
     not_applied_reason:String(j.not_applied_reason||"").slice(0,180),
     quality_status:j.quality_status||"",
     attempts:j.attempts||0,
     timings:j.timings||{},created_at:j.created_at,finished_at:j.finished_at,
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
        visible.push({name,
         pose:String(actor.pose||"standing").slice(0,80),
         outfit:String(actor.outfit||"default").slice(0,80),
         emotion:String(actor.emotion||"neutral").slice(0,60)});
       }
       if(visible.length)safeScene.sprites=visible;
      }
    }
    const committed=await games.gameNarrate({game_id:gameId,expected_action_id:input.action_id,
      messages:input.messages,scene:safeScene,
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
 if(u.pathname!=="/mcp")return json(res,404,{error:"Not found"});
 if(!validBearer(req,MCP_KEY))return json(res,401,{error:"Unauthorized"});
 if(req.method==="OPTIONS"){res.writeHead(204,{"Access-Control-Allow-Headers":"authorization,content-type,mcp-session-id","Access-Control-Allow-Methods":"POST,GET,DELETE,OPTIONS"});return res.end()}
 const m=mcpServer(),t=new StreamableHTTPServerTransport({sessionIdGenerator:undefined,enableJsonResponse:true});
 await m.connect(t);await t.handleRequest(req,res);
 res.once("finish",()=>{t.close().catch(()=>{});m.close().catch(()=>{})});
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
