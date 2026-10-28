import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
const root=await fs.mkdtemp(path.join(os.tmpdir(),"mcp-vn-v55-"));
process.env.VN_DATA_DIR=root;
const store=await import("../src/game-store.mjs");
const {makeNarrationPacket}=await import("../src/narration-packet.mjs");
const {measureTurnPerformance}=await import("../src/turn-performance.mjs");
test("narrator packet is bounded and excludes artwork jobs, URLs and undo snapshots",async()=>{
 const g=await store.gameStart();
 g.hero.description=("Внешность: внимательные глаза, тёмные волосы, лёгкая борода.\n"
  +"Характер: спокойный, рассудительный.\nМанера речи: кратко и уверенно.\n"+
  "История: "+"прочие детали ".repeat(1000)).slice(0,5000);
 g.art_jobs=Array.from({length:40},()=>({prompt:"Unrelated image metadata ".repeat(1000)}));
 g.identities={Мира:{face_url:"https://sensitive.example/photo.png",
  variants:{"realistic|default|standing|neutral":"https://sensitive.example/asset.png"}}};
 g.flags={mira_met:true};
 for(let i=0;i<42;i++)g.messages.push({id:String(i),role:i%2?"narrator":"player",
   speaker:i%2?"Мира":"Макс Кроу",text:"Короткий разговор о вратах и руне "+i+".".repeat(6)});
 const packet=makeNarrationPacket(g);
 const rendered=JSON.stringify(packet);
 assert.ok(rendered.length<11600,"Packet exceeded max chars");
 assert.ok(rendered.includes("mira_met"));
 assert.equal(packet.story.title,g.title);
 assert.equal(packet.recent_dialogue.length<=10,true);
 assert.equal(packet.protagonist.appearance.includes("тёмные волосы"),true);
 assert.ok(!rendered.includes("sensitive.example"));
 assert.ok(!rendered.includes("Unrelated image metadata"));
 assert.ok(!rendered.includes("undo_stack"));
});
test("pending user action travels with packet and includes current canon/quest context",async()=>{
 const g=await store.gameStart();
 const pending=await store.gameAction(g.id,"Осмотреть руны");
 const packet=makeNarrationPacket(pending);
 assert.equal(packet.pending_narration,true);
 assert.equal(packet.pending_action.text,"Осмотреть руны");
 assert.equal(packet.expected_version,pending.version);
 assert.equal(packet.scene.location,pending.scene.location);
 assert.equal(packet.rules.mode,"narrative");
 assert.ok(packet.recent_dialogue.at(-1).text.includes("Осмотреть руны"));
});
test("turn metrics separate external narration round trip from server commit processing",async()=>{
 const g=await store.gameStart();
 const pending=await store.gameAction(g.id,"Прислушаться");
 assert.ok(pending.turn_metrics.pending.submitted_at);
 await new Promise(r=>setTimeout(r,30));
 const next=await store.gameNarrate({game_id:g.id,messages:[
   {speaker:"Мира",text:"Слышишь эхо?"},
   {speaker:"Рассказчик",text:"Врата отзываются."}
 ]});
 const t=next.turn_metrics.last;
 assert.equal(next.turn_metrics.pending,null);
 assert.ok(t.action_to_narration_ms>=25);
 assert.ok(t.server_commit_processing_ms>=0);
 assert.equal(t.message_count,2);
 assert.equal(next.turn_metrics.recent.length,1);
 const game=await store.gameGet(g.id);
 assert.equal(game.turn_metrics.last.action_id,pending.messages.at(-1).id);
});
test("historic message timestamps yield honest roundtrip measurements",async()=>{
 const g=await store.gameStart();
 g.messages.push({id:"action1",role:"player",speaker:"Hero",text:"Привет",at:"2026-01-01T00:00:00.000Z"});
 g.messages.push({id:"narrator1",role:"narrator",speaker:"Мира",text:"Здравствуй",at:"2026-01-01T00:01:21.000Z"});
 const metrics=measureTurnPerformance(g);
 assert.equal(metrics.count,1);
 assert.equal(metrics.median_roundtrip_ms,81000);
 assert.ok(metrics.explanation.includes("not pure model inference"));
});
test.after(async()=>fs.rm(root,{recursive:true,force:true}));
