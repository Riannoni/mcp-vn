import {randomUUID} from "node:crypto";

/** File-native, deterministic bounded story memory inspired by World Info + openovel. */
const tidy=(v,n=500)=>String(v??"").replace(/\s+/g," ").trim().slice(0,n);
const tokens=s=>new Set((tidy(s,4000).normalize("NFKC").toLowerCase().match(/[\p{L}\p{N}]{3,}/gu)||[]));
const now=()=>new Date().toISOString();
const max=(array,limit)=>array.slice(-limit);
const legit=v=>v&&typeof v==="object"&&!Array.isArray(v);
const arr=v=>Array.isArray(v)?v:[];
const safeKey=s=>tidy(s,90).toLowerCase().replace(/[^\p{L}\p{N}_.-]+/gu,"-");
const VALID_SCOPES=new Set(["world","character","place","location","item","quest","story","relationship"]);
const VALID_QUEST_STATUSES=new Set(["active","completed","failed","paused"]);
const eventKinds=new Set(["action","narration","location","item","relationship","quest","rule"]);

export function ensureMemory(game){
 game.memory ||= {};
 const m=game.memory;
 if(!Number.isInteger(m.schema_version))m.schema_version=1;
 for(const key of ["facts","quests","events","chapters","notes"])
  if(!Array.isArray(m[key]))m[key]=[];
 m.turn=Number.isInteger(m.turn)&&m.turn>=0?m.turn:0;
 m.next_chapter_at=Number.isInteger(m.next_chapter_at)&&m.next_chapter_at>=1?m.next_chapter_at:20;
 return m;
}
function normalizeFact(raw){
 if(!legit(raw))return null;
 const scope=VALID_SCOPES.has(raw.scope)?raw.scope:"story";
 const subject=tidy(raw.subject,100),key=safeKey(raw.key||raw.title||raw.subject);
 const value=tidy(raw.value||raw.text,650);
 if(!key||!value)return null;
 return {scope,subject,key,value,importance:Math.max(1,Math.min(5,Number(raw.importance)||3)),
  keywords:arr(raw.keywords).slice(0,12).map(x=>tidy(x,60)).filter(Boolean),
  source_message_id:tidy(raw.source_message_id,100)||null,
  active:raw.active!==false};
}
export function patchMemory(game,updates={}){
 const m=ensureMemory(game);
 if(!legit(updates))return {facts:0,quests:0,notes:0,chapters:0};
 const count={facts:0,quests:0,notes:0,chapters:0},stamp=now();
 const source=(game.messages||[]).filter(x=>x.role==="narrator").at(-1)?.id||null;
 for(const raw of arr(updates.facts).slice(0,12)){
  const fact=normalizeFact(raw);
  if(!fact)continue;
  if(!fact.source_message_id)fact.source_message_id=source;
  const existing=m.facts.find(x=>x.scope===fact.scope&&x.subject===fact.subject&&x.key===fact.key);
  if(existing){
   if(existing.value!==fact.value){
    existing.history ||= [];
    existing.history.push({value:existing.value,updated_at:existing.updated_at,
      source_message_id:existing.source_message_id});
    existing.history=max(existing.history,12);
   }
   Object.assign(existing,fact,{updated_at:stamp});
  }else m.facts.push({id:randomUUID(),...fact,history:[],created_at:stamp,updated_at:stamp});
  count.facts++;
 }
 for(const raw of arr(updates.quests).slice(0,8)){
  if(!legit(raw))continue;
  const key=safeKey(raw.id||raw.title),title=tidy(raw.title||raw.id,120);
  if(!key||!title)continue;
  const status=VALID_QUEST_STATUSES.has(raw.status)?raw.status:"active";
  const q={key,title,status,description:tidy(raw.description,450),
   objective:tidy(raw.objective,250),updated_at:stamp};
  const old=m.quests.find(x=>x.key===key);
  if(old){
   old.history ||= [];
   if(old.status!==q.status||old.objective!==q.objective){
    old.history.push({at:stamp,status:old.status,objective:old.objective});
    old.history=max(old.history,15);
   }
   Object.assign(old,q);
  }else m.quests.push({id:randomUUID(),...q,history:[],created_at:stamp});
  count.quests++;
 }
 for(const raw of arr(updates.notes).slice(0,12)){
  if(!legit(raw))continue;
  const subject=tidy(raw.subject,100),scope=VALID_SCOPES.has(raw.scope)?raw.scope:"character";
  const text=tidy(raw.text,350);
  if(!subject||!text)continue;
  const key=safeKey(raw.key||text.slice(0,60));
  const found=m.notes.find(x=>x.scope===scope&&x.subject===subject&&x.key===key);
  if(found)Object.assign(found,{text,updated_at:stamp});
  else m.notes.push({id:randomUUID(),scope,subject,key,text,created_at:stamp,updated_at:stamp});
  count.notes++;
 }
 if(updates.chapter_summary){
  const summary=tidy(updates.chapter_summary,1000);
  const last=m.chapters.at(-1);
  if(last&&summary&&last.status==="draft"){
   last.summary=summary;last.synopsis=summary;
   last.status="confirmed";last.updated_at=stamp;count.chapters++;
  }
 }
 m.facts=max(m.facts,180);
 m.quests=max(m.quests,70);
 m.notes=max(m.notes,130);
 m.chapters=max(m.chapters,35);
 return count;
}
export function recordEvent(game,{kind,text,location,turn}){
 const m=ensureMemory(game);
 const value=tidy(text,400);
 if(!value)return;
 m.events.push({id:randomUUID(),turn:turn??m.turn,
   kind:eventKinds.has(kind)?kind:"narration",
   location:tidy(location||game.scene?.location,130),
   text:value,at:now()});
 m.events=max(m.events,260);
}
export function closeChapterIfNeeded(game){
 const m=ensureMemory(game),messages=game.messages||[];
 let added=null;
 while(messages.length>=m.next_chapter_at){
  const from=m.next_chapter_at-20,to=m.next_chapter_at;
  const batch=messages.slice(from,to);
  if(batch.length!==20)break;
  const text=batch.map(x=>x.text||"");
  const meaningful=batch.filter(x=>/(ключ|ворот|тайн|памят|узнал|наш[её]л|решил|обещ|маг|смерт|клятв|вест|откры|побед|след|clue|secret|promise|key)/iu.test(x.text||""));
  const highlights=max(meaningful.map(x=>tidy(x.text,160)),6);
  if(!highlights.length)highlights.push(...max(batch.filter(x=>x.role!=="player").map(x=>tidy(x.text,160)),3));
  const decisions=batch.filter(x=>x.role==="player").map(x=>tidy(x.text,200));
  const summary=tidy([highlights[0],highlights.at(-1)].filter(Boolean).join(" → "),650);
  added={id:randomUUID(),index:m.chapters.length+1,number:m.chapters.length+1,
   from_message:from,to_message:to,
   first_message_id:batch[0].id,last_message_id:batch.at(-1).id,
   message_count:20,highlights,player_decisions:decisions,
   start_location:tidy(m.events.find(e=>e.turn>=m.turn-8)?.location||game.scene?.location,120),
   end_location:tidy(game.scene?.location,120),
   summary,synopsis:summary,status:"draft",created_at:now()};
  m.chapters.push(added);
  m.next_chapter_at+=20;
 }
 m.chapters=max(m.chapters,35);
 m.arcs ||= [];
 if(m.chapters.length>=4&&m.chapters.length%4===0){
  const part=m.chapters.slice(-4);
  const number=m.chapters.length/4;
  if(!m.arcs.some(x=>x.index===number)){
   m.arcs.push({id:randomUUID(),index:number,
    from_chapter:part[0].index,to_chapter:part.at(-1).index,
    synopsis:tidy(part.map(x=>x.synopsis).join(" → "),1100),
    created_at:now(),status:"draft"});
  }
 }
 m.arcs=max(m.arcs,10);
 return added;
}
export function updateMemory(game){
 const m=ensureMemory(game);
 closeChapterIfNeeded(game);
 return m;
}
export function addFact(game,{subject,predicate,value,scope="world",
 confidence="confirmed",source_message_id}={}){
 const fact=normalizeFact({scope,subject,key:predicate,value,importance:confidence==="confirmed"?4:2});
 if(!fact)throw Error("Fact requires subject, predicate and value");
 const m=ensureMemory(game),stamp=now();
 const prior=m.facts.find(x=>x.scope===fact.scope&&x.subject===fact.subject&&x.key===fact.key);
 if(prior){
  prior.history ||= [];
  prior.history.push({value:prior.value,updated_at:prior.updated_at,
   source_message_id:prior.source_message_id});
  prior.history=max(prior.history,12);
  prior.value=fact.value;prior.updated_at=stamp;prior.source_message_id=source_message_id||null;
  prior.confidence=confidence;
  return prior;
 }
 const created={...fact,id:randomUUID(),predicate:fact.key,
  confidence,source_message_id:source_message_id||null,
  history:[],created_at:stamp,updated_at:stamp};
 m.facts.push(created);m.facts=max(m.facts,180);
 return created;
}
function scoreRecord(x,queryTokens,sceneTokens,actorNames){
 const content=[x.key,x.title,x.subject,x.value,x.text,x.description,...arr(x.keywords)].filter(Boolean).join(" ");
 const wordSet=tokens(content);
 let hits=0;
 for(const t of queryTokens)if(wordSet.has(t))hits+=4;
 for(const t of sceneTokens)if(wordSet.has(t))hits+=2;
 if(x.subject&&actorNames.some(n=>n.toLowerCase()===x.subject.toLowerCase()))hits+=7;
 if(x.importance)hits+=x.importance;
 if(x.scope==="world")hits+=1;
 return hits;
}
export function queryMemory(game,query="",opts={}){
 const m=ensureMemory(game),location=tidy(game.scene?.location,200);
 const actors=(game.scene?.sprites||[]).map(x=>x.name).filter(Boolean);
 const actions=(game.messages||[]).filter(x=>x.role==="player").slice(-2).map(x=>x.text);
 const queryTokens=tokens([query,...actions].join(" "));
 const sceneTokens=tokens([location,...actors].join(" "));
 const facts=m.facts.filter(x=>x.active!==false)
  .map(x=>({x,score:scoreRecord(x,queryTokens,sceneTokens,actors)}))
  .sort((a,b)=>b.score-a.score||b.x.updated_at.localeCompare(a.x.updated_at))
  .slice(0,Math.min(18,Number(opts.facts)||10)).map(a=>a.x);
 const notes=m.notes
  .map(x=>({x,score:scoreRecord(x,queryTokens,sceneTokens,actors)}))
  .sort((a,b)=>b.score-a.score||b.x.updated_at.localeCompare(a.x.updated_at))
  .slice(0,8).map(a=>a.x);
 const open=m.quests.filter(x=>x.status==="active"||x.status==="paused").slice(-8);
 return {location,actors,facts,notes,quests:open,
  chapters:m.chapters.slice(-4),recent_events:m.events.slice(-12),
  turns:m.turn,chapter_progress:(game.messages||[]).length};
}
export function contextGuide(game,query=""){
 const m=queryMemory(game,query);
 return {
  ...m,
  instruction:"Treat canon facts, completed quests and established character details as persistent. Never change game state from prose alone; use gm_continue memory_updates and validated tools for durable changes. Respect player agency.",
 };
}


export function searchMemory(game,{query="",limit=8,include_chapters=true}={}){
 const m=updateMemory(game),queryWords=tokens(query),sceneWords=tokens(game.scene?.location||"");
 const actors=(game.scene?.sprites||[]).map(s=>s.name);
 const result=[];
 for(const f of m.facts.filter(x=>x.active!==false)){
  result.push({kind:"fact",id:f.id,scope:f.scope,subject:f.subject,key:f.key,
   text:tidy([f.subject,f.key,f.value].filter(Boolean).join(": "),750),
   score:scoreRecord(f,queryWords,sceneWords,actors)+4,
   created_at:f.updated_at||f.created_at});
 }
 for(const c of include_chapters?m.chapters:[]){
  const topic=[...(c.highlights||[]),...(c.player_decisions||[])].join(" ");
  const record={subject:c.end_location,text:topic,value:c.synopsis,key:c.number};
  result.push({kind:"chapter",id:"chapter-"+c.index,
   text:tidy(c.synopsis+" | "+topic,900),
   score:scoreRecord(record,queryWords,sceneWords,actors)+1,
   created_at:c.created_at});
 }
 for(const q of m.quests){
  result.push({kind:"quest",id:q.id,subject:q.title,
   text:tidy(q.title+": "+q.description+" ["+q.status+"]",600),
   score:scoreRecord(q,queryWords,sceneWords,actors)+6,
   created_at:q.updated_at||q.created_at});
 }
 for(const n of m.notes){
  result.push({kind:"note",id:n.id,scope:n.scope,subject:n.subject,
   text:tidy(n.subject+": "+n.text,550),score:scoreRecord(n,queryWords,sceneWords,actors),
   created_at:n.updated_at||n.created_at});
 }
 return result.sort((a,b)=>b.score-a.score||
  String(b.created_at||"").localeCompare(String(a.created_at||"")))
  .slice(0,Math.max(1,Math.min(30,Number(limit)||8)))
  .map(({score,created_at,...rest})=>rest);
}
export function contextDigest(game,{query="",maxChars=6200}={}){
 const m=updateMemory(game);
 const relevant=searchMemory(game,{query,limit:10});
 const digest={
  location:game.scene?.location||"",
  style:game.art_style,
  story_title:game.title,
  active_quests:m.quests.filter(x=>x.status==="active").slice(-8)
   .map(x=>({title:x.title,objective:x.objective,description:x.description})),
  relevant_memories:relevant,
  recent_chapters:m.chapters.slice(-4).map(x=>({index:x.index,
    synopsis:x.synopsis,decisions:x.player_decisions.slice(-4)})),
  latest_messages:(game.messages||[]).slice(-20).map(x=>({id:x.id,speaker:x.speaker,
    role:x.role,text:tidy(x.text,700)})),
  recent_events:m.events.slice(-10)
 };
 const cap=Math.max(1500,Math.min(14000,Number(maxChars)||6200));
 while(JSON.stringify(digest).length>cap&&digest.relevant_memories.length)
  digest.relevant_memories.pop();
 while(JSON.stringify(digest).length>cap&&digest.latest_messages.length>7)
  digest.latest_messages.shift();
 return digest;
}
