import http from "node:http";
import fs from "node:fs/promises";
import crypto from "node:crypto";
import {McpServer} from "@modelcontextprotocol/sdk/server/mcp.js";
import {StreamableHTTPServerTransport} from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import {registerAppTool,registerAppResource,RESOURCE_MIME_TYPE} from "@modelcontextprotocol/ext-apps/server";
import {z} from "zod";
import * as games from "./src/game-store.mjs";
import * as jobs from "./src/jobs.mjs";

const PORT=Number(process.env.VN_PORT||3100),HOST=process.env.VN_HOST||"127.0.0.1";
const WORKER_KEY=process.env.VN_WORKER_TOKEN||"",MCP_KEY=process.env.VN_MCP_TOKEN||"";
const PUBLIC=(process.env.VN_PUBLIC_ORIGIN||"https://xavoks.jo3.org/vn").replace(/\/$/,"");
const UI="ui://mcp-vn/visual-novel.html";
if(HOST!=="127.0.0.1"&&(!WORKER_KEY||!MCP_KEY))throw Error("Both VN_WORKER_TOKEN and VN_MCP_TOKEN required on LAN");
const result=(key,value)=>({content:[{type:"text",text:JSON.stringify({[key]:value})}],structuredContent:{[key]:value}});
const safe=fn=>async a=>{try{return await fn(a||{})}catch(e){return{isError:true,content:[{type:"text",text:e.message||"Unknown error"}]}}};
const Z=z.string();
function mcpServer(){
 const m=new McpServer({name:"mcp-vn",version:"0.2.0"});
 registerAppResource(m,"visual-novel",UI,{mimeType:RESOURCE_MIME_TYPE,
  _meta:{ui:{csp:{resourceDomains:[new URL(PUBLIC).origin],connectDomains:[]},prefersBorder:false}}},
  async()=>({contents:[{uri:UI,mimeType:RESOURCE_MIME_TYPE,text:await fs.readFile("./dist/index.html","utf8")}]})
 );
 registerAppTool(m,"open_game",{
 title:"Visual novel",description:"Open the interactive visual novel with scrollback and free-text actions.",
 inputSchema:{game_id:Z.optional()},_meta:{ui:{resourceUri:UI}}},
 safe(async({game_id})=>{
   if(game_id)return result("game",await games.gameGet(game_id));
   const sessions=await games.list("games");
   const latest=sessions.sort((a,b)=>(b.updated_at||"").localeCompare(a.updated_at||""))[0];
   return result("game",latest?await games.gameGet(latest.id):await games.gameStart())
 }));
 m.tool("list_stories","List story packs ready to play.",{},safe(async()=>result("stories",await games.list("stories"))));
 m.tool("list_games","List saved game sessions.",{},safe(async()=>result("games",await games.list("games"))));
 m.tool("start_game","Start another game (previous saves stay intact).",
 {story_id:Z.default("ash-gate"),hero_name:Z.default("Макс Кроу"),hero_description:Z.default("")},
 safe(async({story_id,hero_name,hero_description})=>result("game",await games.gameStart(story_id,hero_name,hero_description))));
 m.tool("get_game","Full game state for scrolling transcript and scene rendering.",
 {game_id:Z},safe(async({game_id})=>result("game",await games.gameGet(game_id))));
 m.tool("get_game_context","Narrator must read this before responding to a pending player action.",
 {game_id:Z},safe(async({game_id})=>{
  const g=await games.gameGet(game_id);
  return result("context",{id:g.id,version:g.version,story:g.story,hero:g.hero,scene:g.scene,flags:g.flags,
   inventory:g.inventory,relationships:g.relationships,awaiting_narrator:g.awaiting_narrator,
   latest_messages:g.messages.slice(-42),art_jobs:await jobs.jobsForGame(game_id)});
 }));
 m.tool("submit_action","Record a free-text user action. Don't call a second time for a UI-submitted turn.",
 {game_id:Z,action:Z,expected_version:z.number().optional()},
 safe(async({game_id,action,expected_version})=>result("game",await games.gameAction(game_id,action,expected_version))));
 m.tool("gm_continue","Narrator: continue the story after get_game_context. Never narrate the player's choices for them. Scenes may request artwork separately; choices are optional.",
 {game_id:Z,messages:z.array(z.object({speaker:Z,text:Z})).min(1).max(12),
 scene:z.object({location:Z.optional(),background_url:Z.optional(),
 sprites:z.array(z.object({name:Z,image_url:Z,emotion:Z.optional()})).optional()}).optional(),
 choices:z.array(Z).optional(),inventory_add:z.array(Z).optional(),
 flags:z.record(z.union([Z,z.number(),z.boolean()])).optional(),relationships:z.record(z.number()).optional()},
 safe(async(a)=>result("game",await games.gameNarrate(a))));
 m.tool("undo_last_turn","Undo last complete player/narrator turn.",
 {game_id:Z},safe(async({game_id})=>result("game",await games.gameUndo(game_id))));
 m.tool("queue_art","Create image/video with local ComfyUI on user's own GPU. No ISEKAI credits. Use for new scenes and characters. Style anime/semireal/realistic/poster.",
 {game_id:Z,prompt:Z,kind:z.enum(["background","sprite","scene","video"]).default("background"),
 style:z.enum(["anime","semireal","realistic","poster"]).default("semireal"),character:Z.optional()},
 safe(async(a)=>result("job",await jobs.enqueue(a))));
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
 if(u.pathname==="/healthz")return json(res,200,{ok:true,name:"mcp-vn",version:"0.2.0"});
 if(u.pathname.startsWith("/worker/")){
  if(!validBearer(req,WORKER_KEY))return json(res,401,{error:"Unauthorized"});
  if(req.method==="GET"&&u.pathname==="/worker/next")return json(res,200,{job:await jobs.nextJob()});
  const match=u.pathname.match(/^\/worker\/(complete|fail)\/([a-f0-9-]{36})$/);
  if(req.method!=="POST"||!match)return json(res,404,{error:"Not found"});
  if(match[1]==="fail"){const b=await body(req,8192);const d=JSON.parse(b.toString());return json(res,200,{job:await jobs.failJob(match[2],d.error)})}
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
service.listen(PORT,HOST,()=>console.log("mcp-vn http://"+HOST+":"+PORT));
