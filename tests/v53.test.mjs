import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {PNG} from "pngjs";
const root=await fs.mkdtemp(path.join(os.tmpdir(),"vn-v53-"));
process.env.VN_DATA_DIR=root;
process.env.VN_ASSET_SECRET="tests-only-secret";
const game=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");
const {resolveCheck}=await import("../src/game-rules.mjs");
const image=(w,h,cut=false)=>{
 const im=new PNG({width:w,height:h});
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4,visible=!cut||(x>w*.2&&x<w*.8&&y>h*.04&&y<h*.95);
  im.data[i]=85;im.data[i+1]=95;im.data[i+2]=110;im.data[i+3]=visible?255:0;
 }
 return PNG.sync.write(im);
};
async function publish(j){
 const next=await jobs.nextJob(j.kind==="scene"?"cpu":"gpu");
 assert.equal(next.id,j.id);
 await jobs.reportQA(j.id,{passed:true,semantic_status:"passed",reasons:[]});
 const [w,h]=j.spec.resolution;
 return jobs.completeJob(j.id,image(w,h,j.kind==="sprite"),"image/png","https://example.org/vn");
}
test("background revisit uses cached location/time/style without GPU",async()=>{
 const g=await game.gameStart();
 const bg=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"medieval square"});
 const accepted=await publish(bg);
 let previous=await game.gameGet(g.id);
 await game.gameAction(g.id,"Walk to forest",previous.version);
 await game.gameNarrate({game_id:g.id,messages:[{speaker:"Guide",text:"Forest arrives"}],
  scene:{location:"Dark forest"}});
 previous=await game.gameGet(g.id);
 assert.equal(previous.scene.background_url,"");
 await game.gameAction(g.id,"Return",previous.version);
 const arrived=await game.gameNarrate({game_id:g.id,
  messages:[{speaker:"Guide",text:"We returned."}],scene:{location:"Площадь Тиррена"}});
 assert.equal(arrived.scene.background_url,accepted.asset_url);
 assert.equal(arrived.scene.background_style,"realistic");
 assert.ok(Object.keys(arrived.scene_catalog).length>0);
});
test("adventure mode rolls are server-verified and narrative is opt-in",async()=>{
 const g=await game.gameStart();
 const saved=await game.gameGet(g.id);
 assert.equal(saved.rules.mode,"narrative");
 assert.throws(()=>resolveCheck(saved,{stat:"insight",difficulty:13},()=>20),/disabled/);
 const changed=await game.gameSetRulesMode(g.id,"adventure");
 assert.equal(changed.rules.mode,"adventure");
 await game.gameAction(g.id,"Inspect magic glyph");
 const rolled=await game.gameSkillCheck(g.id,{stat:"insight",difficulty:15,description:"Study glyphs"});
 assert.equal(rolled.check.rolls.length,1);
 assert.ok(rolled.check.rolls[0]>=1&&rolled.check.rolls[0]<=20);
 assert.equal(rolled.check.total,rolled.check.selected+1);
 const finished=await game.gameNarrate({game_id:g.id,messages:[{speaker:"Narrator",text:"Glyphs unfold"}]});
 assert.equal(finished.rules.history.length,1);
 assert.equal(finished.memory.turn,1);
});
test("background library warmup does not replace visible sprite",async()=>{
 const g=await game.gameStart();
 const bg=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"market"});
 await publish(bg);
 const base=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",prompt:"neutral"});
 const acceptedSprite=await publish(base);
 const prepped=await jobs.warmCharacterVariants(g.id,{emotions:["smile","concerned"]});
 assert.equal(prepped.queued.length,2);
 assert.notEqual(prepped.queued[0].job_id,prepped.queued[1].job_id);
 for(const record of prepped.queued){
  const queued=await jobs.getJob(record.job_id);
  assert.equal(queued.spec.library_only,true);
  assert.equal(queued.priority,12);
  const accepted=await publish(queued);
  assert.equal(accepted.applied,true);
  assert.equal(accepted.library_stored,true);
 }
 const state=await game.gameGet(g.id);
 assert.equal(state.scene.sprites[0].image_url,acceptedSprite.asset_url);
 assert.equal(state.scene.sprites[0].emotion,"neutral");
 for(const emotion of ["smile","concerned"]){
  const key="realistic|default|standing|"+emotion;
  assert.ok(state.identities["Мира"].variants[key]);
  assert.ok(state.identities["Мира"].variant_backgrounds[key]);
 }
});
test("prefetched next location is cataloged without changing the active scene",async()=>{
 const g=await game.gameStart();
 const result=await jobs.warmNextLocations(g.id,[{
   location:"Тёмный лес",time_of_day:"night",weather:"mist",
   description:"Outdoor dark misty pine woodland under pale moonlight"
 }]);
 assert.equal(result.queued.length,1);
 const j=await jobs.getJob(result.queued[0].job_id);
 assert.equal(j.spec.library_only,true);
 assert.equal(j.spec.location,"Тёмный лес");
 assert.equal(j.priority,8);
 const published=await publish(j);
 assert.equal(published.status,"done");
 assert.equal(published.library_stored,true);
 const before=await game.gameGet(g.id);
 assert.equal(before.scene.location,"Площадь Тиррена");
 assert.equal(before.scene.background_url,"");
 await game.gameAction(g.id,"Travel to dark forest");
 const arrived=await game.gameNarrate({game_id:g.id,
   messages:[{speaker:"Narrator",text:"The forest appears"}],
   scene:{location:"Тёмный лес",time_of_day:"night",weather:"mist"}});
 assert.equal(arrived.scene.background_url,published.asset_url);
 assert.equal(arrived.scene.background_style,"realistic");
});
test.after(async()=>fs.rm(root,{recursive:true,force:true}));
