import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import http from "node:http";
import path from "node:path";

const dir=await fs.mkdtemp(path.join(os.tmpdir(),"vn-local-lane-"));
process.env.VN_DATA_DIR=dir;
const server=http.createServer(async(req,res)=>{
 let body="";
 for await(const c of req)body+=c.toString();
 res.setHeader("Content-Type","application/json");
 if(req.url==="/api/tags"){
  res.end(JSON.stringify({models:[{name:"cydonia:24b-v4.3-iq4_xs"}]}));return;
 }
 if(req.url==="/api/chat"){
  await new Promise(r=>setTimeout(r,70));
  res.end(JSON.stringify({message:{role:"assistant",
   content:"Мира спокойно улыбнулась и ответила, что ей важно взаимное доверие. Вечер продолжился тихим разговором."},
   total_duration:80000000,load_duration:5000000,
   prompt_eval_count:178,eval_count:29,eval_duration:33000000}));return;
 }
 res.statusCode=404;res.end("{}");
});
await new Promise(r=>server.listen(0,"127.0.0.1",r));
process.env.VN_LOCAL_MODEL_URL="http://127.0.0.1:"+server.address().port;
process.env.VN_LOCAL_MODEL_ID="cydonia:24b-v4.3-iq4_xs";
const game=await import("../src/game-store.mjs");
const local=await import("../src/local-scene.mjs");
const {makeNarrationPacket}=await import("../src/narration-packet.mjs");
const {withLocalGpu,isLocalGpuReserved}=await import("../src/gpu-coordinator.mjs");
async function preparedGame(){
 const g=await game.gameStart("ash-gate","Макс Кроу","Возраст: 34\nХарактер: сдержанный","semireal");
 const action=await game.gameAction(g.id,"Знакомство",g.version);
 return game.gameNarrate({game_id:g.id,
  messages:[{speaker:"Мира",text:"Рада знакомству."}],
  scene:{sprites:[
   {name:"Макс Кроу",image_url:"https://example.org/max.png",outfit:"default"},
   {name:"Мира",image_url:"https://example.org/mira.png",outfit:"default"}
  ]}});
}
async function waitUntil(fn,timeout=2400){
 const end=Date.now()+timeout;
 while(Date.now()<end){
  const r=await fn();if(r)return r;
  await new Promise(resolve=>setTimeout(resolve,30));
 }
 throw Error("Test local inference did not finish in time");
}
test("local command retry preserves dice and undo restores episode transcript",async()=>{
 const g=await preparedGame();
 const opened=await local.beginLocalScene(g.id,g.version);
 const first=await local.submitLocalCommand(g.id,"/roll d20 dc 10 осмотреться",opened.version);
 await waitUntil(async()=>(await local.getLocalEpisode(g.id)).transcript.some(x=>x.role==="narrator"));
 await waitUntil(async()=>!(await game.gameGet(g.id)).local_scene.pending);
 const before=await local.getLocalEpisode(g.id);
 let current=await game.gameGet(g.id);
 const roll=before.transcript[0].command.roll;
 await local.reviseLocalTurn(g.id,{retry:true,note:"короче",version:current.version});
 await waitUntil(async()=>!(await game.gameGet(g.id)).local_scene.pending);
 const retried=await local.getLocalEpisode(g.id);
 assert.equal(retried.transcript.filter(x=>x.role==="player").length,1);
 assert.deepEqual(retried.transcript[0].command.roll,roll);
 current=await game.gameGet(g.id);
 await local.reviseLocalTurn(g.id,{version:current.version});
 assert.equal((await local.getLocalEpisode(g.id)).transcript.length,0);
 assert.equal((await game.gameGet(g.id)).local_scene.turns,0);
});
test("local scene text stays out of main ChatGPT context, but a neutral bridge remains",async()=>{
 const g=await preparedGame(),count=g.messages.length;
 const opened=await local.beginLocalScene(g.id,g.version);
 assert.equal(opened.mode,"local");
 assert.equal(opened.participants.find(x=>x.name==="Мира").age,26);
 const health=await local.localHealth();
 assert.equal(health.online,true);
 assert.equal(health.model_ready,true);
 const secret="ЛИЧНОЕ_СОДЕРЖИМОЕ_НЕ_ДЛЯ_ОСНОВНОГО_СЮЖЕТА";
 const request=await local.submitLocalTurn(g.id,secret,opened.version);
 assert.equal(request.status,"generating");
 await assert.rejects(()=>game.gameAction(g.id,"Попытка отправить второй GM-ход"),/Local scene active/);
 const done=await waitUntil(async()=>{
  const state=await game.gameGet(g.id);
  return state.local_scene.pending?null:state;
 });
 assert.equal(done.local_scene.turns,1);
 const episode=await local.getLocalEpisode(g.id);
 assert.equal(episode.transcript.length,2);
 assert.equal(episode.transcript[0].text,secret);
 assert.match(episode.transcript[1].text,/Мира/);
 assert.equal(episode.last_metrics.eval_count,29);
 assert.equal(done.messages.length,count);
 assert.ok(!JSON.stringify(makeNarrationPacket(done)).includes(secret));
 assert.ok(!JSON.stringify(done).includes(secret));
 const closed=await local.exitLocalScene(g.id,done.version);
 assert.equal(closed.mode,"main");
 const restored=await game.gameGet(g.id);
 assert.equal(restored.messages.length,count+1);
 assert.equal(restored.local_scene.mode,"main");
 assert.equal(restored.memory.notes.at(-1).scope,"story");
 assert.ok(!JSON.stringify(restored).includes(secret));
 assert.ok(!JSON.stringify(restored).includes("Мира спокойно улыбнулась"));
 assert.equal((await local.getLocalEpisode(g.id)).status,"complete");
 assert.equal((await local.getLocalEpisode(g.id)).total_messages,2);
});
test("local scenes require explicitly confirmed adult ages",async()=>{
 const g=await game.gameStart("ash-gate","Unknown Hero","","semireal");
 await assert.rejects(()=>local.beginLocalScene(g.id,g.version),
  /At least two adult characters/);
 const again=await game.gameGet(g.id);
 assert.equal(again.version,g.version);
});
test("GPU coordinator blocks concurrent reservations and releases on error",async()=>{
 let entered=false,done=false;
 const first=withLocalGpu({
  activeArtJobs:async()=>false,
  infer:async()=>{
   entered=true;await new Promise(r=>setTimeout(r,70));done=true;return 11;
  }
 });
 await waitUntil(async()=>entered);
 assert.equal(isLocalGpuReserved(),true);
 const second=withLocalGpu({activeArtJobs:async()=>false,infer:async()=>{
  assert.equal(done,true);return 22;
 }});
 assert.equal(await first,11);
 assert.equal(await second,22);
 assert.equal(isLocalGpuReserved(),false);
 await assert.rejects(()=>withLocalGpu({
  activeArtJobs:async()=>false,infer:async()=>{throw Error("simulated GPU failure")}
 }),/simulated/);
 assert.equal(isLocalGpuReserved(),false);
});
test.after(async()=>{
 await new Promise(resolve=>server.close(resolve));
 await fs.rm(dir,{recursive:true,force:true});
});
