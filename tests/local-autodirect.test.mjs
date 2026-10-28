import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import http from "node:http";
import {PNG} from "pngjs";

const dir=await fs.mkdtemp(path.join(os.tmpdir(),"vn-auto-ai-director-"));
process.env.VN_DATA_DIR=dir;
process.env.VN_ASSET_SECRET="test-local-director-autovision";
const llm=http.createServer(async(req,res)=>{
 let raw="";
 for await(const part of req)raw+=part.toString();
 res.setHeader("content-type","application/json");
 if(req.url==="/api/tags"){
  res.end(JSON.stringify({models:[{name:"cydonia:24b-v4.3-iq4_xs"}]}));return;
 }
 const msg=JSON.parse(raw);
 const isDirector=msg.messages?.[0]?.content?.includes("You are the visual continuity director");
 const content=isDirector?
  JSON.stringify({location:"Market square",environment:"Colorful stalls at sunset",
   camera:"lateral tracking shot at knee height",lighting:"warm afternoon",
   activity:"The pair walks along the market",
   characters:[
    {name:"Макс Кроу",outfit:"new leather armor",pose:"walking",
     expression:"smiling",equipment:"sword in sheath",action:"walking alongside companion"},
    {name:"Мира",outfit:"green traveling cloak",pose:"walking",
     expression:"smiling",equipment:"satchel",action:"stepping past vendors"}
   ],render:true}):
  "— С удовольствием, — ответила Мира и улыбнулась. Она поправила свой зелёный плащ и пошла рядом по торговой площади. — Тут есть одно тихое место за прилавками, там мы сможем спокойно поговорить.";
 res.end(JSON.stringify({message:{role:"assistant",content},
  total_duration:40000000,load_duration:5000000,prompt_eval_count:155,
  eval_count:isDirector?23:76,eval_duration:25000000}));
});
await new Promise(resolve=>llm.listen(0,"127.0.0.1",resolve));
process.env.VN_LOCAL_MODEL_URL="http://127.0.0.1:"+llm.address().port;
process.env.VN_LOCAL_MODEL_ID="cydonia:24b-v4.3-iq4_xs";

const game=await import("../src/game-store.mjs");
const local=await import("../src/local-scene.mjs");
const jobs=await import("../src/jobs.mjs");
async function waitFor(check,maxMs=4500){
 const until=Date.now()+maxMs;
 while(Date.now()<until){
  const x=await check();if(x)return x;
  await new Promise(r=>setTimeout(r,35));
 }
 throw Error("Auto director did not finish in test time");
}
function png(w,h,alpha=false){
 const im=new PNG({width:w,height:h});
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4;
  im.data[i]=104;im.data[i+1]=86;im.data[i+2]=122;
  im.data[i+3]=alpha&&(x<w*.17||x>w*.83)?0:255;
 }
 return PNG.sync.write(im);
}
async function complete(job){
 const claimed=await jobs.nextJob(job.kind==="scene"?"cpu":"gpu");
 assert.equal(claimed?.id,job.id);
 await jobs.reportQA(job.id,{passed:true,semantic_status:"passed",reasons:[]});
 const [w,h]=job.spec.resolution;
 return jobs.completeJob(job.id,png(w,h,job.kind==="sprite"),
  "image/png","https://example.org/vn");
}
test("local narration is committed before asynchronous AI visual planning, which queues a canonical-safe new frame",async()=>{
 const initial=await game.gameStart("ash-gate","Макс Кроу","Возраст: 34","semireal");
 const bg=await jobs.enqueue({game_id:initial.id,kind:"background",prompt:"market"});
 await complete(bg);
 for(const name of ["Макс Кроу","Мира"]){
  const j=await jobs.enqueue({game_id:initial.id,kind:"sprite",
   character:name,prompt:"approved fictional adult sprite"});
  await complete(j);
 }
 const normal=await jobs.enqueue({game_id:initial.id,kind:"scene",prompt:"normal canonical scene"});
 await complete(normal);
 const before=await game.gameGet(initial.id);
 const started=await local.beginLocalScene(before.id,before.version);
 await local.submitLocalTurn(before.id,"Мира, давай пройдёмся по площади.",started.version);
 const textDone=await waitFor(async()=>{
  const g=await game.gameGet(before.id);
  return !g.local_scene.pending?g:null;
 });
 assert.equal(textDone.messages.length,before.messages.length);
 assert.ok(!JSON.stringify(textDone).includes("С удовольствием"));
 const auto=await waitFor(async()=>{
  const ep=await local.getLocalEpisode(before.id);
  return ep.cg_previews?.length?ep:null;
 });
 assert.equal(auto.transcript.length,2);
 assert.equal(auto.visual_pending,null);
 assert.equal(auto.visual_state.camera,"lateral tracking shot at knee height");
 assert.equal(auto.visual_state.characters[0].outfit,"new leather armor");
 assert.equal(auto.visual_state.characters[0].equipment,"sword in sheath");
 assert.equal(auto.visual_state.source,"ai_director");
 assert.equal(auto.cg_previews.at(-1).source,"ai");
 const parent=await jobs.getJob(auto.cg_previews.at(-1).job_id);
 assert.equal(parent.kind,"local_cg");
 assert.equal(parent.spec.composition,"neural_story");
 assert.equal(parent.spec.local_visual_state.characters[0].outfit,"new leather armor");
 assert.equal(parent.spec.local_variant_jobs.length,0,
  "CG uses canonical character anchors and does not spawn duplicate renders");
 assert.equal(auto.visual_decision.mode,"cg");
 assert.match(auto.visual_decision.reason,/physical_state_changed/);
 const after=await game.gameGet(before.id);
 assert.equal(after.scene.cg_url,before.scene.cg_url);
 assert.deepEqual(after.scene.sprites,before.scene.sprites);
 assert.equal(after.art_style,"semireal");
});
test.after(async()=>{
 await new Promise(done=>llm.close(done));
 await fs.rm(dir,{recursive:true,force:true});
});
