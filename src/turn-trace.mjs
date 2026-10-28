// v5.6 privacy-minimal turn stage tracing.
// A sidecar file avoids mutating the playable game state for diagnostics.
import fs from "node:fs/promises";
import path from "node:path";
import {dataRoot} from "./game-store.mjs";

const validId=s=>typeof s==="string"&&/^[0-9a-f-]{36}$/.test(s);
const phases=new Set(["host_ack","host_error","ui_render","gm_invoked","gm_committed"]);
const dest=id=>{
 if(!validId(id))throw Error("Invalid game ID");
 return path.join(dataRoot,"turn-traces",id+".jsonl");
};
const ms=x=>Number.isFinite(x)&&x>=0&&x<=300000?Math.round(x):null;
const epoch=x=>Number.isFinite(x)&&x>1_600_000_000_000&&x<2_300_000_000_000?Math.round(x):null;
export async function appendTrace(gameId,{action_id,phase,
 client_started_at_ms,client_finished_at_ms,submit_rpc_ms,host_ack_ms,ui_render_ms,
 commit_version,detail}){
 if(!validId(action_id))throw Error("Invalid action ID");
 if(!phases.has(phase))throw Error("Invalid trace phase");
 const payload={
  action_id,phase,server_received_at_ms:Date.now(),
  client_started_at_ms:epoch(client_started_at_ms),
  client_finished_at_ms:epoch(client_finished_at_ms),
  submit_rpc_ms:ms(submit_rpc_ms),
  host_ack_ms:ms(host_ack_ms),
  ui_render_ms:ms(ui_render_ms),
  commit_version:Number.isInteger(commit_version)?commit_version:null,
  detail:typeof detail==="string"?detail.slice(0,90):null
 };
 const file=dest(gameId);
 await fs.mkdir(path.dirname(file),{recursive:true});
 await fs.appendFile(file,JSON.stringify(payload)+"\n",{mode:0o600,flag:"a"});
 return payload;
}
export async function getTraces(gameId,{limit=20}={}){
 let lines;
 try{lines=(await fs.readFile(dest(gameId),"utf8")).trim().split("\n")}
 catch(e){if(e.code==="ENOENT")return [];throw e}
 const rows=[];
 for(const line of lines.slice(-500)){
  try{rows.push(JSON.parse(line))}catch{}
 }
 const grouped=new Map();
 for(const row of rows){
  if(!validId(row.action_id))continue;
  if(!grouped.has(row.action_id))grouped.set(row.action_id,[]);
  grouped.get(row.action_id).push(row);
 }
 return [...grouped].slice(-Math.max(1,Math.min(50,limit))).map(([action_id,events])=>({
  action_id,events
 }));
}
export async function makeTraceReport(gameId,g,options={}){
 const entries=await getTraces(gameId,options);
 const actions=(g.messages||[]).filter(m=>m.role==="player");
 const responses=new Map();
 for(const a of actions){
  const index=g.messages.indexOf(a),next=g.messages.slice(index+1).find(m=>m.role==="player"||m.role==="narrator");
  responses.set(a.id,{
   submitted_at_ms:Date.parse(a.at),
   completed_at_ms:next?.role==="narrator"?Date.parse(next.at):null
  });
 }
 return entries.map(({action_id,events})=>{
  const phases=Object.fromEntries(events.map(e=>[e.phase,e]));
  const times=responses.get(action_id)||{};
  const started=times.submitted_at_ms||null;
  const invoked=phases.gm_invoked?.server_received_at_ms||null;
  const committed=phases.gm_committed?.server_received_at_ms||times.completed_at_ms||null;
  const host=phases.host_ack;
  const render=phases.ui_render;
  const diff=(a,b)=>a!=null&&b!=null?Math.max(0,a-b):null;
  return {
   action_id,
   submitted_at_ms:started,
   host_message_ack_ms:host?.host_ack_ms??null,
   client_submit_rpc_ms:host?.submit_rpc_ms??null,
   action_to_host_ack_ms:host&&started?diff(host.server_received_at_ms,started):null,
   action_to_gm_call_ms:diff(invoked,started),
   gm_tool_processing_ms:diff(committed,invoked),
   action_to_committed_ms:diff(committed,started),
   ui_delivery_after_commit_ms:render&&committed?diff(render.server_received_at_ms,committed):null,
   host_message_error:phases.host_error?.detail||null,
   stages_recorded:events.map(e=>e.phase)
  };
 });
}
