import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {PNG} from "pngjs";
const root=await fs.mkdtemp(path.join(os.tmpdir(),"mcp-vn-v4-"));
process.env.VN_DATA_DIR=root;
process.env.VN_ASSET_SECRET="test-only-secret";
const store=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");

function png(w,h,transparent=false){
 const image=new PNG({width:w,height:h,colorType:6});
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4,visible=!transparent||(x>w*.23&&x<w*.78&&y>h*.05&&y<h*.94);
  image.data[i]=105;image.data[i+1]=85;image.data[i+2]=130;
  image.data[i+3]=visible?255:0;
 }
 return PNG.sync.write(image);
}
const good=()=>({passed:true,reasons:[],semantic_status:"unavailable",metrics:{test_pass:true}});
test("start, free-text action, narration, undo and persistence",async()=>{
 await store.init();
 assert.ok((await store.list("stories")).find(x=>x.id==="ash-gate"));
 const g=await store.gameStart("ash-gate","Макс Кроу");
 assert.equal(g.messages.length,1);
 const t=await store.gameAction(g.id,"Я осматриваю врата",g.version);
 assert.equal(t.awaiting_narrator,true);
 await assert.rejects(()=>store.gameAction(g.id,"repeated"));
 const n=await store.gameNarrate({game_id:g.id,messages:[{speaker:"Мира",text:"Осторожнее, путник."}],choices:["Подойти"]});
 assert.equal(n.messages.length,3);
 assert.equal(n.awaiting_narrator,false);
 assert.equal((await store.gameGet(g.id)).messages.length,3);
 const u=await store.gameUndo(g.id);
 assert.equal(u.messages.length,1);
});
test("background, sprite alpha and scene CG publish independently",async()=>{
 const g=await store.gameStart();
 const bg=await jobs.enqueue({game_id:g.id,prompt:"A fantasy castle",style:"realistic",kind:"background"});
 assert.equal(bg.spec.output,"background");
 assert.equal((await jobs.nextJob()).id,bg.id);
 await jobs.reportQA(bg.id,{...good(),warnings:["Potential palette mismatch"]});
 const ready=await jobs.completeJob(bg.id,png(1216,704),"image/png","https://example.org/vn");
 assert.deepEqual(ready.qa.warnings,["Potential palette mismatch"]);
 assert.equal(ready.status,"done");
 assert.equal(ready.applied,true);
 assert.match((await store.gameGet(g.id)).scene.background_url,/assets\/.*\.png\?sig=[0-9a-f]+$/);
 const char=await jobs.enqueue({game_id:g.id,prompt:"A guide",kind:"sprite",style:"realistic",character:"Мира"});
 assert.equal(char.spec.background_asset,ready.file);
 await jobs.nextJob();
 await jobs.reportQA(char.id,good());
 const made=await jobs.completeJob(char.id,png(832,1216,true),"image/png","https://example.org/vn");
 assert.equal(made.qa.server_alpha_ratio>0.1,true);
 assert.equal((await store.gameGet(g.id)).scene.sprites[0].transparent,true);
 assert.equal((await store.gameGet(g.id)).scene.sprites[0].art_style,"realistic");
 const cg=await jobs.enqueue({game_id:g.id,prompt:"Integrated characters",kind:"scene",style:"realistic"});
 assert.equal(cg.spec.composition,"anchored_composite");
 await jobs.nextJob();await jobs.reportQA(cg.id,good());
 await jobs.completeJob(cg.id,png(1216,704),"image/png","https://example.org/vn");
 const after=await store.gameGet(g.id);
 assert.equal(after.scene.mode,"cg");
 assert.equal(after.scene.background_url,ready.asset_url);
 assert.ok(after.scene.cg_url);
 assert.equal(after.scene.sprites.length,1);
});
test("opaque sprite is blocked server-side even if worker claimed it passed",async()=>{
 const g=await store.gameStart();
 const job=await jobs.enqueue({game_id:g.id,prompt:"Guide",kind:"sprite",character:"Мира"});
 await jobs.nextJob();await jobs.reportQA(job.id,good());
 await assert.rejects(()=>jobs.completeJob(job.id,png(832,1216),"image/png","https://example.org/vn"),/Alpha quality rejected/);
 assert.equal((await store.gameGet(g.id)).scene.sprites.length,0);
 await jobs.failJob(job.id,"alpha failed");
 assert.equal((await jobs.getJob(job.id)).status,"queued");
 for(let attempt=2;attempt<=3;attempt++){
  assert.equal((await jobs.nextJob()).id,job.id);
  await jobs.failJob(job.id,"alpha failed");
 }
 assert.equal((await jobs.getJob(job.id)).status,"failed");
});
test("worker rejection schedules bounded retries and retains last good asset",async()=>{
 const g=await store.gameStart();
 const job=await jobs.enqueue({game_id:g.id,prompt:"A guide",kind:"sprite",character:"Мира"});
 for(let i=1;i<=3;i++){
  const claimed=await jobs.nextJob();
  assert.equal(claimed.id,job.id);
  assert.equal(claimed.attempts,i);
  const response=await jobs.reportQA(job.id,{passed:false,reasons:["Subject cropped"],semantic_status:"unavailable"});
  assert.equal(response.status,i===3?"failed":"queued");
 }
 assert.equal((await store.gameGet(g.id)).scene.sprites.length,0);
});
test("successful retry clears stale failure errors and preserves QA warnings",async()=>{
 const g=await store.gameStart();
 const j=await jobs.enqueue({game_id:g.id,prompt:"castle",kind:"background"});
 await jobs.nextJob();
 let result=await jobs.reportQA(j.id,{passed:false,reasons:["Color mismatch"],semantic_status:"failed"});
 assert.equal(result.status,"queued");
 assert.match(result.error,/Color mismatch/);
 assert.equal((await jobs.nextJob()).attempts,2);
 result=await jobs.reportQA(j.id,{...good(),warnings:["Lighting differs slightly"]});
 assert.equal(result.status,"working");
 assert.equal(result.error,undefined);
 assert.deepEqual(result.qa.warnings,["Lighting differs slightly"]);
 await jobs.completeJob(j.id,png(1216,704),"image/png","https://example.org/vn");
 assert.equal((await jobs.getJob(j.id)).error,undefined);
});
test("art from a previous location is not silently attached",async()=>{
 const g=await store.gameStart();
 const job=await jobs.enqueue({game_id:g.id,prompt:"Town",kind:"background"});
 await jobs.nextJob();
 await store.gameAction(g.id,"Иду в лес",g.version);
 await store.gameNarrate({game_id:g.id,messages:[{speaker:"Рассказчик",text:"Лес."}],scene:{location:"Тёмный лес"}});
 await jobs.reportQA(job.id,good());
 const ready=await jobs.completeJob(job.id,png(1216,704),"image/png","https://example.org/vn");
 assert.equal(ready.status,"done");
 assert.equal(ready.applied,false);
 assert.equal((await store.gameGet(g.id)).scene.background_url,"");
});
test("character generated for an old background cannot overwrite current scene",async()=>{
 const g=await store.gameStart();
 const char=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",prompt:"Guide"});
 await jobs.nextJob();
 const bg=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"Moonlit old town"});
 // Replace the backdrop while character art is still calculating.
 await store.attachImage(g.id,{kind:"background",url:"https://example.org/vn/assets/11111111-2222-3333-4444-555555555555.png",style:"realistic"});
 await jobs.reportQA(char.id,good());
 const publish=await jobs.completeJob(char.id,png(832,1216,true),"image/png","https://example.org/vn");
 assert.equal(publish.applied,false);
 assert.equal((await store.gameGet(g.id)).scene.sprites.length,0);
 // A queued future background remains independently usable.
 assert.equal((await jobs.getJob(bg.id)).status,"queued");
});
test("story import rejects minors and missing reuse rights",async()=>{
 await assert.rejects(()=>store.importStory({title:"x",opening:"x",author:"x",source:"original",rights_confirmed:true,characters:[{age:15}]}));
 await assert.rejects(()=>store.importStory({title:"x",opening:"x",author:"x",source:"original"}));
 assert.ok((await store.importStory({title:"Original",opening:"Hello",author:"Me",source:"original",rights_confirmed:true,characters:[{age:28}]})).id);
});
test("the animation style is distinct from Japanese anime and selectable for new games",async()=>{
 const game=await store.gameStart("ash-gate","Тест героя","","animation");
 assert.equal(game.art_style,"animation");
 const background=await jobs.enqueue({game_id:game.id,prompt:"A 2D animated fantasy village",
  kind:"background",style:"animation"});
 assert.equal(background.style,"animation");
 assert.equal(background.model,"BASNSFWBetterAnimeStyleForNSFWHentai_baseV10.safetensors");
 const anime=await store.gameStart("ash-gate","Тест героя","","anime");
 const animeBg=await jobs.enqueue({game_id:anime.id,prompt:"A Japanese anime village",
  kind:"background",style:"anime"});
 assert.equal(animeBg.model,"waiIllustriousSDXL_v170.safetensors");
 assert.notEqual(animeBg.model,background.model);
 const realistic=await store.gameStart("ash-gate","Тест героя","","realistic");
 const realBg=await jobs.enqueue({game_id:realistic.id,prompt:"A realistic village",
  kind:"background",style:"realistic"});
 assert.equal(realBg.model,"CyberRealisticPony_V18.0_F16.safetensors");
});
test("available model styles",()=>{
 assert.deepEqual(jobs.styleList(),["anime","semireal","realistic","poster","animation"]);
});
test.after(async()=>fs.rm(root,{recursive:true,force:true}));
