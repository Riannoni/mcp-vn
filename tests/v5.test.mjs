import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {PNG} from "pngjs";
const root=await fs.mkdtemp(path.join(os.tmpdir(),"mcp-vn-v5-"));
process.env.VN_DATA_DIR=root;
process.env.VN_ASSET_SECRET="v5-test-secret";
const store=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");
const {environmentFor}=await import("../src/environment.mjs");
function png(w,h,alpha=false){
 const im=new PNG({width:w,height:h,colorType:6});
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4,visible=!alpha||(x>w*.2&&x<w*.8&&y>h*.05&&y<h*.93);
  im.data[i]=90;im.data[i+1]=90;im.data[i+2]=90;im.data[i+3]=visible?255:0;
 }
 return PNG.sync.write(im);
}
async function publish(j,payload=png(832,1216,true)){
 assert.equal((await jobs.nextJob(j.kind==="scene"?"cpu":"gpu")).id,j.id);
 await jobs.reportQA(j.id,{passed:true,reasons:[],semantic_status:"passed",
   timings:{generation_ms:123,qa_ms:23,postprocess_ms:40}});
 return jobs.completeJob(j.id,payload,"image/png","https://example.org/vn");
}
test("outdoor market is classified into distinct prompt/negative constraints",()=>{
 const env=environmentFor({location:"Рыночная площадь Тиррена"});
 assert.equal(env.id,"outdoor_market_square");
 assert.ok(env.positive.some(s=>s.includes("sky")));
 assert.ok(env.negative.includes("bedroom"));
 assert.equal(environmentFor({location:"Кабинет астролога"}).id,"indoor_room");
});
test("canonical identity remains unchanged when another outfit is accepted",async()=>{
 const g=await store.gameStart();
 const base=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",prompt:"base portrait",force:true});
 const first=await publish(base);
 assert.ok(first.applied);
 const state=await store.gameGet(g.id);
 assert.equal(state.identities["Мира"].base_sprite_url,first.asset_url);
 assert.ok(state.identities["Мира"].face_url);
 // The narrative must first request the new wardrobe and emotion.
 const before=await store.gameGet(g.id);
 await store.gameAction(g.id,"Put on a winter coat",before.version);
 await store.gameNarrate({game_id:g.id,messages:[{speaker:"Narrator",text:"The outfit changes."}],
  scene:{sprites:[{name:"Мира",image_url:first.asset_url,outfit:"winter coat",
                    pose:"standing",emotion:"smile"}]}});
 const job=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",prompt:"winter coat",
   outfit:"winter coat",pose:"standing",emotion:"smile",force:true});
 assert.equal(job.spec.anchor_asset,first.file);
 const second=await publish(job);
 const newer=await store.gameGet(g.id);
 assert.equal(newer.identities["Мира"].base_sprite_url,first.asset_url);
 assert.equal(newer.identities["Мира"].last_sprite_url,second.asset_url);
 assert.ok(newer.identities["Мира"].variants["realistic|winter coat|standing|smile"]);
 assert.equal(newer.scene.sprites[0].outfit,"winter coat");
 assert.equal(newer.scene.sprites[0].emotion,"smile");
 assert.equal(second.timings.generation_ms,123);
 assert.ok(second.timings.total_ms>=0);
});
test("variant cache reuses previous accepted image without GPU",async()=>{
 const g=await store.gameStart();
 const a=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",prompt:"guide"});
 const done=await publish(a);
 const cache=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",prompt:"guide"});
 assert.equal(cache.cache_hit,true);
 assert.equal(cache.asset_url,done.asset_url);
});
test("CPU and GPU pools are separated and priorities are ordered",async()=>{
 const lowGame=await store.gameStart(), highGame=await store.gameStart();
 const a=await jobs.enqueue({game_id:lowGame.id,kind:"background",prompt:"low",priority:1});
 const b=await jobs.enqueue({game_id:highGame.id,kind:"background",prompt:"high",priority:99});
 assert.equal((await jobs.nextJob("gpu")).id,b.id);
 assert.equal((await jobs.nextJob("gpu")).id,a.id);
});
test("CG cannot run unless background and all visible characters are accepted alpha sprites",async()=>{
 const g=await store.gameStart();
 await assert.rejects(()=>jobs.enqueue({game_id:g.id,kind:"scene",prompt:"cg"}),/background/);
 const bg=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"square"});
 await publish(bg,png(1216,704));
 await assert.rejects(()=>jobs.enqueue({game_id:g.id,kind:"scene",prompt:"cg"}),/characters/);
 const a=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",prompt:"guide"});
 await publish(a);
 const cg=await jobs.enqueue({game_id:g.id,kind:"scene",prompt:"scene"});
 assert.equal(cg.spec.visible_count,1);
 assert.equal((await jobs.nextJob("cpu")).id,cg.id);
});
test("location change resets outdated background but preserves identity and cache",async()=>{
 const g=await store.gameStart();
 const sprite=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",prompt:"guide"});
 await publish(sprite);
 let fresh=await store.gameGet(g.id);
 await store.attachImage(g.id,{kind:"background",
   url:"https://example.org/vn/assets/11111111-2222-3333-4444-555555555555.png"});
 fresh=await store.gameGet(g.id);
 await store.gameAction(g.id,"Иду в лес",fresh.version);
 await store.gameNarrate({game_id:g.id,messages:[{speaker:"Рассказчик",text:"Теперь лес"}],
  scene:{location:"Тёмный лес",sprites:[{name:"Мира",image_url:""}]}});
 const after=await store.gameGet(g.id);
 assert.equal(after.scene.background_url,"");
 assert.ok(after.scene.sprites[0].image_url);
 assert.ok(after.identities["Мира"].base_sprite_url);
});
test("legacy transparent sprites are promoted into canonical identity anchors",async()=>{
 const g=await store.gameStart();
 const s=await jobs.enqueue({game_id:g.id,kind:"sprite",character:"Мира",
  prompt:"portrait",force:true});
 const accepted=await publish(s);
 assert.equal(accepted.applied,true);
 const file=path.join(root,"games",g.id+".json");
 const snapshot=JSON.parse(await fs.readFile(file,"utf8"));
 snapshot.identities={}; // simulate a previously saved v4 game
 await fs.writeFile(file,JSON.stringify(snapshot));
 const promoted=await jobs.ensureCharacterAnchors(g.id,"https://example.org/vn");
 assert.deepEqual(promoted.seeded,["Мира"]);
 assert.equal(promoted.identities["Мира"].base_sprite_url,accepted.asset_url);
 assert.ok(promoted.identities["Мира"].face_url);
 assert.deepEqual((await jobs.ensureCharacterAnchors(g.id,"https://example.org/vn")).seeded,[]);
});
test.after(async()=>fs.rm(root,{recursive:true,force:true}));
