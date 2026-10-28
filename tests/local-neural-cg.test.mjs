import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {PNG} from "pngjs";
const root=await fs.mkdtemp(path.join(os.tmpdir(),"vn-story-neural-"));
process.env.VN_DATA_DIR=root;
process.env.VN_ASSET_SECRET="isolated-neural-story-tests";
const game=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");
const local=await import("../src/local-scene.mjs");
function png(w,h,cut=false){
 const im=new PNG({width:w,height:h});
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4;
  im.data[i]=106;im.data[i+1]=91;im.data[i+2]=114;
  im.data[i+3]=cut&&(x<w*.2||x>w*.82)?0:255;
 }
 return PNG.sync.write(im);
}
async function publish(j){
 const cpu=j.kind==="scene"||(j.kind==="local_cg"&&j.spec?.composition!=="neural_story");
 const claimed=await jobs.nextJob(cpu?"cpu":"gpu");
 assert.equal(claimed?.id,j.id);
 await jobs.reportQA(j.id,{passed:true,semantic_status:"passed",
  metrics:j.kind==="local_cg"?{
   scene_count_verified:true,scene_location_verified:true
  }:{}});
 const [w,h]=j.spec.resolution;
 return jobs.completeJob(j.id,png(w,h,j.kind==="sprite"),
  "image/png","https://example.org/vn");
}
async function setup(){
 const g=await game.gameStart("ash-gate","Макс Кроу","Возраст: 34","semireal");
 const bg=await jobs.enqueue({game_id:g.id,kind:"background",prompt:"market square"});
 await publish(bg);
 for(const name of ["Макс Кроу","Мира"]){
  const s=await jobs.enqueue({game_id:g.id,kind:"sprite",character:name,prompt:"canonical"});
  await publish(s);
 }
 const main=await jobs.enqueue({game_id:g.id,kind:"scene",prompt:"main scene"});
 await publish(main);
 const before=await game.gameGet(g.id);
 const localStart=await local.beginLocalScene(g.id,before.version);
 return {game_id:g.id,before,localStart};
}
test("local CG performs neural GPU full-frame render, without canonical mutation",async()=>{
 const {game_id,before,localStart}=await setup();
 const generated=await local.queueLocalCG(game_id,{direction:"dramatic low camera, diagonal framing",quality:"cinematic"});
 assert.equal(generated.kind,"local_cg");
 const j=await jobs.getJob(generated.id);
 assert.equal(j.spec.composition,"neural_story");
 assert.equal(j.spec.preview_only,true);
 assert.equal(j.spec.local_session_id,localStart.session_id);
 assert.equal(j.spec.local_fresh_composition,false);
 assert.equal(j.spec.quality,"cinematic");
 assert.equal(j.spec.local_visual_state.camera,"dramatic low camera, diagonal framing");
 assert.equal(j.spec.local_variant_jobs.length,0,
  "A full-frame CG must not generate separate unrelated sprite previews");
 assert.equal(await jobs.nextJob("cpu"),null,"Neural CG must not use the CPU compositor");
 const claimed=await jobs.nextJob("gpu");
 assert.equal(claimed.id,j.id);
 assert.equal(claimed.spec.local_variant_jobs.length,0);
 assert.deepEqual(j.spec.resolution,[896,1152]);
 await jobs.reportQA(j.id,{passed:true,semantic_status:"passed",
  metrics:{scene_count_verified:true,scene_location_verified:true}});
 const applied=await jobs.completeJob(j.id,png(896,1152),"image/png","https://example.org/vn");
 assert.equal(applied.status,"done");
 assert.equal(applied.applied,false);
 const after=await game.gameGet(game_id);
 assert.equal(after.scene.cg_url,before.scene.cg_url);
 assert.deepEqual(after.scene.sprites,before.scene.sprites);
 const ep=await local.getLocalEpisode(game_id);
 assert.equal(ep.cg_previews.at(-1).job_id,j.id);
 assert.equal(ep.video_previews.length,0);
});
test("visual replan does not create a player action from an empty episode",async()=>{
 const {game_id}=await setup();
 await assert.rejects(()=>local.replanLocalScene(game_id),/No completed local turn/);
});
test("video generation is opt-in, references a finished local CG, and remains preview-only",async()=>{
 const {game_id,before}=await setup();
 await assert.rejects(()=>local.queueLocalVideo(game_id),/finish a local CG/i);
 const cg=await local.queueLocalCG(game_id,{quality:"fast"});
 const j=await jobs.getJob(cg.id);
 assert.equal(j.spec.local_variant_jobs.length,0);
 await publish(j);
 const epBefore=await local.getLocalEpisode(game_id);
 assert.equal(epBefore.video_previews.length,0);
 const video=await local.queueLocalVideo(game_id,{motion:"A slow tracking shot, cloak waving"});
 assert.equal(video.kind,"video");
 const task=await jobs.getJob(video.id);
 assert.equal(task.spec.preview_only,true);
 assert.equal(task.spec.composition,"story_video");
 assert.equal(task.spec.video_start_asset.length,40);
 assert.match(task.prompt,/slow tracking shot/i);
 assert.equal(task.spec.local_session_id,epBefore.session_id);
 const queued=await jobs.nextJob("gpu");
 assert.equal(queued.id,video.id);
 const after=await game.gameGet(game_id);
 assert.equal(after.scene.cg_url,before.scene.cg_url);
 assert.equal(after.scene.video_url,before.scene.video_url);
});
test("a legacy unverified preview cannot seed the next CG or produce a video",async()=>{
 const {game_id}=await setup();
 const first=await local.queueLocalCG(game_id,{quality:"fast"});
 const job=await jobs.getJob(first.id);
 assert.equal(job.spec.local_variant_jobs.length,0);
 const claimed=await jobs.nextJob("gpu");
 assert.equal(claimed.id,first.id);
 // Old image metadata: accepted by a generic caption but never checked
 // independently for both characters or the requested location.
 await jobs.reportQA(first.id,{passed:true,semantic_status:"passed"});
 await jobs.completeJob(first.id,png(896,1152),"image/png","https://example.org/vn");
 await assert.rejects(()=>local.queueLocalVideo(game_id),/verified current CG/i);
 const next=await local.queueLocalCG(game_id,{quality:"fast"});
 const shot=await jobs.getJob(next.id);
 assert.equal(shot.spec.local_basis_asset,"");
 assert.equal(shot.spec.local_basis_verified,false);
 // Leave no queued CG behind for the next test sharing the same temp root.
 await publish(shot);
});

test("identical accepted local CG is reused, not regenerated",async()=>{
 const {game_id,before}=await setup();
 const first=await local.queueLocalCG(game_id,{quality:"standard",auto:true});
 const job=await jobs.getJob(first.id);
 assert.equal(job.spec.local_variant_jobs.length,0);
 await publish(job);
 const second=await local.queueLocalCG(game_id,{
  quality:"standard",auto:true,allowCache:true});
 assert.equal(second.id,first.id);
 assert.equal(second.cache_hit,true);
 assert.equal((await local.getLocalEpisode(game_id)).cg_previews.length,2);
 const ep=await local.getLocalEpisode(game_id);
 assert.equal(ep.visual_display.mode,"cg");
 assert.equal(ep.visual_display.cg_job_id,job.id);
 assert.equal((await game.gameGet(game_id)).scene.cg_url,before.scene.cg_url);
});
test("dialogue sprites use cached previews and never mutate canonical game sprites",async()=>{
 const {game_id,before}=await setup();
 const first=await local.queueLocalSprites(game_id,["Мира"]);
 assert.equal(first.generated.length,1);
 const job=await jobs.getJob(first.generated[0]);
 assert.equal(job.kind,"sprite");
 assert.equal(job.spec.preview_only,true);
 const saved=await publish(job);
 const cached=await local.queueLocalSprites(game_id,["Мира"]);
 assert.deepEqual(cached.generated,[]);
 assert.equal(cached.sprite_jobs["Мира"],job.id);
 const ep=await local.getLocalEpisode(game_id);
 assert.equal(ep.visual_display.mode,"layers");
 assert.equal(ep.visual_display.sprite_urls["Мира"],saved.asset_url);
 assert.deepEqual((await game.gameGet(game_id)).scene.sprites,before.scene.sprites);
});
test("local CG is unavailable outside the adult local episode",async()=>{
 const g=await game.gameStart();
 await assert.rejects(()=>jobs.enqueue({game_id:g.id,kind:"local_cg",
  prompt:"scene",preview_only:true}),/local episode/i);
 await assert.rejects(()=>jobs.enqueue({game_id:g.id,kind:"local_cg",
  prompt:"scene",preview_only:false}),/preview/i);
});
test.after(async()=>fs.rm(root,{recursive:true,force:true}));
