import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
const dir=await fs.mkdtemp(path.join(os.tmpdir(),"vn-trace-"));
process.env.VN_DATA_DIR=dir;
const store=await import("../src/game-store.mjs");
const {appendTrace,getTraces,makeTraceReport}=await import("../src/turn-trace.mjs");
test("host acknowledgement, tool invocation and UI-render delivery are separately traceable",async()=>{
 const g=await store.gameStart();
 const submitted=await store.gameAction(g.id,"Наблюдаю",g.version);
 const a=submitted.messages.at(-1),start=Date.parse(a.at);
 await appendTrace(g.id,{action_id:a.id,phase:"host_ack",
  client_started_at_ms:start+8,client_finished_at_ms:start+15,
  host_ack_ms:7,submit_rpc_ms:10});
 await appendTrace(g.id,{action_id:a.id,phase:"gm_invoked"});
 const complete=await store.gameNarrate({game_id:g.id,messages:[
  {speaker:"Мира",text:"Похоже, приближается рассвет."}
 ]});
 await appendTrace(g.id,{action_id:a.id,phase:"gm_committed",commit_version:complete.version});
 await appendTrace(g.id,{action_id:a.id,phase:"ui_render",
  client_finished_at_ms:Date.now(),commit_version:complete.version});
 const traces=await getTraces(g.id);
 assert.equal(traces.length,1);
 assert.deepEqual(traces[0].events.map(e=>e.phase),[
  "host_ack","gm_invoked","gm_committed","ui_render"]);
 const metrics=await makeTraceReport(g.id,complete);
 assert.equal(metrics[0].host_message_ack_ms,7);
 assert.equal(metrics[0].client_submit_rpc_ms,10);
 assert.ok(metrics[0].gm_tool_processing_ms>=0);
 assert.ok(metrics[0].ui_delivery_after_commit_ms>=0);
});
test("trace records are privacy-limited and reject malformed IDs and invalid phases",async()=>{
 const g=await store.gameStart();
 const action=await store.gameAction(g.id,"Test");
 const id=action.messages.at(-1).id;
 await assert.rejects(()=>appendTrace(g.id,{action_id:id,phase:"password"}),/phase/);
 await assert.rejects(()=>appendTrace("../../etc",{action_id:id,phase:"host_ack"}),/game ID/);
 const trace=await appendTrace(g.id,{action_id:id,phase:"host_error",
  detail:"Connection failed. ".repeat(30),submit_rpc_ms:-14});
 assert.ok(trace.detail.length<=90);
 assert.equal(trace.submit_rpc_ms,null);
 const raw=await fs.readFile(path.join(dir,"turn-traces",g.id+".jsonl"),"utf8");
 assert.ok(!raw.includes("Connection failed. ".repeat(10)));
});
test.after(async()=>fs.rm(dir,{recursive:true,force:true}));
