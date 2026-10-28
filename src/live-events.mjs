import crypto from "node:crypto";

// Short-lived per-session event cursors. No user secrets or image bytes in events.
// Persistent canonical state remains game-store and jobs; reconnect always re-reads it.
export const serverBootId=crypto.randomUUID();
const MAX_EVENTS=35;
const rooms=new Map();
const allowedKinds=new Set(["game","job","memory","reset"]);
function room(id){
 if(!rooms.has(id))rooms.set(id,{seq:0,events:[],listeners:new Set(),lastAccess:Date.now()});
 const r=rooms.get(id);r.lastAccess=Date.now();return r;
}
export function pushGameEvent(gameId,kind="game",detail={}){
 if(!gameId||!allowedKinds.has(kind))return;
 const r=room(gameId);
 const event={seq:++r.seq,kind,at:new Date().toISOString(),
  detail:Object.fromEntries(Object.entries(detail||{}).filter(([key,val])=>
   /^[a-z_]{1,35}$/.test(key) && (typeof val==="string"||typeof val==="number"||typeof val==="boolean")).
   map(([k,v])=>[k,typeof v==="string"?v.slice(0,160):v]))};
 r.events.push(event);
 if(r.events.length>MAX_EVENTS)r.events.shift();
 for(const listener of [...r.listeners])listener();
}
export function peekGameEvents(gameId,{boot_id="",after_seq=0}={}){
 const r=room(gameId);
 const mismatch=boot_id&&boot_id!==serverBootId;
 const ahead=after_seq>r.seq;
 const reset=!!(mismatch||ahead);
 const events=reset?[]:r.events.filter(e=>e.seq>after_seq);
 return {boot_id:serverBootId,seq:r.seq,reset,events};
}
export async function waitGameEvents(gameId,{boot_id="",after_seq=0,wait_ms=8000}={}){
 const current=peekGameEvents(gameId,{boot_id,after_seq});
 if(!boot_id||current.reset||current.events.length||wait_ms===0)return current;
 const r=room(gameId);
 const bounded=Math.max(100,Math.min(12000,Number(wait_ms)||8000));
 return new Promise(resolve=>{
  let timer;
  const settle=()=>{
   clearTimeout(timer);
   r.listeners.delete(settle);
   resolve(peekGameEvents(gameId,{boot_id,after_seq}));
  };
  r.listeners.add(settle);
  timer=setTimeout(settle,bounded);
  // Close the race between peek and registering listener.
  if(r.seq>after_seq)settle();
 });
}
// Diagnostic only: no expensive periodic timer or separate DB.
export function eventStats(){
 return {rooms:rooms.size,listeners:[...rooms.values()].reduce((n,r)=>n+r.listeners.size,0)};
}
