import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {PNG} from "pngjs";
const dir=await fs.mkdtemp(path.join(os.tmpdir(),"vn-v52-"));
process.env.VN_DATA_DIR=dir;
process.env.VN_ASSET_SECRET="only-testing";
const games=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");
const {claimAttempt,recordStage,finishAttempt,aggregateTimings}=await import("../src/job-timing.mjs");
function png(w,h,cutout=false){
 const o=new PNG({width:w,height:h});
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4,visible=!cutout||(x>w*.22&&x<w*.78&&y>h*.04&&y<h*.95);
  o.data[i]=125;o.data[i+1]=95;o.data[i+2]=150;o.data[i+3]=visible?255:0;
 }
 return PNG.sync.write(o);
}
async function finish(job,preview=false){
 assert.equal((await jobs.nextJob(job.kind==="scene"?"cpu":"gpu")).id,job.id);
 await jobs.stageJob(job.id,{stage:"generating",timings:{prepare_ms:40}});
 await jobs.stageJob(job.id,{stage:"generated",timings:{generation_ms:250}});
 await jobs.stageJob(job.id,{stage:"postprocess",timings:{}});
 const ready=await jobs.reportQA(job.id,{passed:true,semantic_status:"passed",reasons:[],
  timings:{postprocess_ms:50,qa_ms:100}});
 assert.equal(ready.status,"working");
 const w=job.spec.resolution[0],h=job.spec.resolution[1];
 return jobs.completeJob(job.id,png(w,h,job.kind==="sprite"),"image/png","https://example.org/vn");
}
test("new game records immutable style and queue_art inherits it",async()=>{
 const g=await games.gameStart("ash-gate","Test hero","","anime");
 assert.equal(g.art_style,"anime");
 await assert.rejects(()=>jobs.enqueue({game_id:g.id,kind:"background",prompt:"forest",
     style:"realistic"}),/locked/i);
 const j=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"forest"});
 assert.equal(j.style,"anime");
 assert.equal(j.spec.style,"anime");
 const out=await finish(j);
 assert.equal(out.applied,true);
 const current=await games.gameGet(g.id);
 assert.equal(current.art_style,"anime");
 assert.equal(current.scene.background_style,"anime");
 const blocked=await games.attachImage(g.id,{kind:"background",style:"poster",
   url:"https://example.org/vn/assets/11111111-2222-3333-4444-555555555555.png"});
 assert.equal(blocked.applied,false);
});
test("legacy style is inferred from immutable identity, not a recently changed background",async()=>{
 const g=await games.gameStart();
 const file=path.join(dir,"games",g.id+".json");
 const old=JSON.parse(await fs.readFile(file,"utf8"));
 delete old.art_style;delete old.art_style_locked_at;delete old.art_style_origin;
 old.scene.background_style="poster";
 old.scene.background_url="https://example.org/vn/assets/11111111-2222-3333-4444-555555555555.png";
 old.scene.sprites=[{name:"Мира",art_style:"semireal",image_url:"",transparent:false}];
 old.identities={"Мира":{base_style:"semireal",variants:{}}};
 await fs.writeFile(file,JSON.stringify(old));
 const migrated=await games.migrateLegacyGameStyles();
 assert.ok(migrated.some(x=>x.id===g.id&&x.art_style==="semireal"));
 const after=await games.gameGet(g.id);
 assert.equal(after.art_style,"semireal");
 assert.equal(after.scene.background_dirty,true);
 assert.ok(after.scene.background_url.includes("11111111"));
});
test("legacy save uses first accepted artwork even when later identity is in another style",async()=>{
 const g=await games.gameStart();
 const f=path.join(dir,"games",g.id+".json");
 const old=JSON.parse(await fs.readFile(f,"utf8"));
 delete old.art_style;delete old.art_style_locked_at;delete old.art_style_origin;
 old.scene.background_style="poster";
 old.scene.background_url="https://example.org/vn/assets/11111111-2222-3333-4444-555555555555.png";
 old.scene.sprites=[{name:"Мира",art_style:"realistic",image_url:"",transparent:false}];
 old.identities={"Мира":{base_style:"realistic",variants:{}}};
 await fs.writeFile(f,JSON.stringify(old));
 await fs.writeFile(path.join(dir,"jobs","11111111-1111-4111-8111-111111111111.json"),JSON.stringify({
  id:"11111111-1111-4111-8111-111111111111",game_id:g.id,kind:"background",style:"semireal",status:"done",
  created_at:"2020-01-01T00:00:00.000Z"}));
 const migration=await games.migrateLegacyGameStyles();
 assert.ok(migration.some(x=>x.id===g.id&&x.art_style==="semireal"));
 const updated=await games.gameGet(g.id);
 assert.equal(updated.art_style,"semireal");
 assert.equal(updated.art_style_origin,"legacy_first_art");
 assert.equal(updated.scene.background_dirty,true);
});
test("idempotent enqueue and a newer intent supersede stale queued work",async()=>{
 const g=await games.gameStart();
 const one=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"square",force:true});
 const duplicate=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"square",force:true});
 assert.equal(duplicate.id,one.id);
 assert.equal(duplicate.deduplicated,true);
 const newer=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"different angle",force:true});
 assert.equal((await jobs.getJob(one.id)).status,"superseded");
 assert.equal((await jobs.nextJob("gpu")).id,newer.id);
});
test("preview is lower resolution, preserves scene, and does not become canonical reference",async()=>{
 const g=await games.gameStart();
 const base=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"town"});
 const original=await finish(base);
 const preview=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"thumbnail town",
   preview_only:true,quality:"fast"});
 assert.deepEqual(preview.spec.resolution,[896,512]);
 const made=await finish(preview,true);
 assert.equal(made.applied,false);
 assert.ok(made.asset_url);
 assert.match(made.not_applied_reason,/Preview only/);
 const after=await games.gameGet(g.id);
 assert.equal(after.scene.background_url,original.asset_url);
});
test("attempt timing aggregates all retries with explicit queue and residual stage time",()=>{
 const at=n=>new Date(Date.parse("2026-01-01T00:00:00.000Z")+n*1000);
 const j={created_at:at(0).toISOString(),attempts:0};
 claimAttempt(j,at(10));
 recordStage(j,{prepare_ms:400,generation_ms:4000,postprocess_ms:600,qa_ms:2000});
 finishAttempt(j,"rejected",at(20));
 claimAttempt(j,at(30));
 recordStage(j,{prepare_ms:500,generation_ms:5000,postprocess_ms:700,qa_ms:2500,publish_ms:100});
 j.finished_at=at(45).toISOString();
 finishAttempt(j,"done",at(45));
 const t=aggregateTimings(j,at(45));
 assert.equal(t.total_ms,45000);
 assert.equal(t.queue_wait_ms,10000);
 assert.equal(t.retry_wait_ms,10000);
 assert.equal(t.generation_ms,9000);
 assert.equal(t.qa_ms,4500);
 assert.equal(t.attempts,2);
 const keys=["queue_wait_ms","retry_wait_ms","prepare_ms","generation_ms","compose_ms",
   "cpu_wait_ms","postprocess_ms","qa_ms","publish_ms","other_ms"];
 assert.equal(keys.reduce((v,k)=>v+(t[k]||0),0),t.total_ms);
});
test.after(async()=>fs.rm(dir,{recursive:true,force:true}));
