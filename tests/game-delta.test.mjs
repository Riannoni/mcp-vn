import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
const dir=await fs.mkdtemp(path.join(os.tmpdir(),"vn-delta-"));
process.env.VN_DATA_DIR=dir;
const store=await import("../src/game-store.mjs");
const {makeGameDelta,compactJob}=await import("../src/game-delta.mjs");
test("new messages are sent incrementally, keeping the canonical scene state",async()=>{
 const g=await store.gameStart();
 const checkpoint={known_version:g.version,known_messages:g.messages.length,
  known_last_id:g.messages.at(-1).id};
 const submitted=await store.gameAction(g.id,"Проверяю врата",g.version);
 const delta=makeGameDelta(submitted,checkpoint);
 assert.equal(delta.full_reload_required,undefined);
 assert.equal(delta.new_messages.length,1);
 assert.equal(delta.new_messages[0].text,"Проверяю врата");
 assert.equal(delta.awaiting_narrator,true);
 assert.equal(delta.undo_count,1);
 const reloaded=await store.gameNarrate({game_id:g.id,
   messages:[{speaker:"Мира",text:"Тише, они слышат."}]});
 const next=makeGameDelta(reloaded,{known_version:submitted.version,
   known_messages:submitted.messages.length,known_last_id:submitted.messages.at(-1).id});
 assert.equal(next.new_messages.length,1);
 assert.equal(next.awaiting_narrator,false);
 assert.ok(next.turn_metrics.last.action_to_narration_ms>=0);
});
test("undo and mismatched message cursors trigger full reload, never a malformed splice",async()=>{
 const g=await store.gameStart();
 await store.gameAction(g.id,"идти дальше");
 await store.gameNarrate({game_id:g.id,messages:[{speaker:"Мира",text:"Пошли."}]});
 const undone=await store.gameUndo(g.id);
 const patch=makeGameDelta(undone,{known_version:1,known_messages:3,
  known_last_id:"wrong"});
 assert.equal(patch.full_reload_required,true);
});
test("unchanged version does not retransmit game payload",async()=>{
 const g=await store.gameStart();
 const patch=makeGameDelta(g,{known_version:g.version,
  known_messages:g.messages.length,known_last_id:g.messages.at(-1).id});
 assert.equal(patch,null);
});
test("compact job omits large prompts while keeping QA, preview and timing fields",()=>{
 const job={id:"job1",game_id:"game1",kind:"sprite",status:"done",style:"realistic",
  character:"Мира",prompt:"image generation secret metadata ".repeat(1000),
  spec:{variant:{outfit:"travel"},preview_only:true},
  timings:{total_ms:12000,qa_ms:2000},
  qa:{passed:true,semantic_status:"passed",metrics:{identity_similarity:0.89,vlm_caption:"green cloak"}},
  asset_url:"https://example.org/result.png"};
 const small=compactJob(job);
 assert.ok(JSON.stringify(small).length<1500);
 assert.equal(small.qa.metrics.identity_similarity,0.89);
 assert.equal(small.asset_url,job.asset_url);
 assert.equal(small.timings.total_ms,12000);
 assert.ok(!JSON.stringify(small).includes("secret metadata"));
});
test.after(async()=>fs.rm(dir,{recursive:true,force:true}));
