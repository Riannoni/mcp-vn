import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {PNG} from "pngjs";

const dir=await fs.mkdtemp(path.join(os.tmpdir(),"vn-local-cg-preview-"));
process.env.VN_DATA_DIR=dir;
process.env.VN_ASSET_SECRET="local-preview-only-test-key";
const game=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");
function image(w,h,alpha=false){
 const im=new PNG({width:w,height:h});
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const i=(y*w+x)*4;
  im.data[i]=108;im.data[i+1]=89;im.data[i+2]=111;
  im.data[i+3]=alpha&&(x<w*0.18||x>w*.83)?0:255;
 }
 return PNG.sync.write(im);
}
async function publish(j){
 const claimed=await jobs.nextJob(j.kind==="scene"?"cpu":"gpu");
 assert.equal(claimed?.id,j.id,"Expected queued job to be claimed");
 await jobs.reportQA(j.id,{passed:true,semantic_status:"passed",reasons:[]});
 const [w,h]=j.spec.resolution;
 return jobs.completeJob(j.id,image(w,h,j.kind==="sprite"),
   "image/png","https://example.org/vn");
}
test("local romantic CG is preview-only and cannot replace canonical scene, sprites or saved story",async()=>{
 const init=await game.gameStart("ash-gate","Макс Кроу","Возраст: 34","semireal");
 const bg=await jobs.enqueue({game_id:init.id,kind:"background",prompt:"fantasy square"});
 await publish(bg);
 const hero=await jobs.enqueue({game_id:init.id,kind:"sprite",
  character:"Макс Кроу",prompt:"hero",outfit:"default",pose:"standing",emotion:"neutral"});
 await publish(hero);
 const mira=await jobs.enqueue({game_id:init.id,kind:"sprite",
  character:"Мира",prompt:"adult guide",outfit:"default",pose:"standing",emotion:"neutral"});
 await publish(mira);
 const beforeCG=await game.gameGet(init.id);
 assert.ok(beforeCG.scene.sprites.every(s=>s.visual_dirty===false));
 const canonical=await jobs.enqueue({game_id:init.id,kind:"scene",prompt:"canonical hero scene"});
 const accepted=await publish(canonical);
 assert.equal(accepted.applied,true);
 const before=await game.gameGet(init.id);
 assert.equal(before.scene.mode,"cg");
 assert.ok(before.scene.cg_url);
 const preview=await jobs.enqueue({game_id:init.id,kind:"scene",
  prompt:"Non-explicit private romantic cinematic shot, fully clothed adults",
  preview_only:true,quality:"fast"});
 const result=await publish(preview);
 assert.equal(result.status,"done");
 assert.equal(result.applied,false);
 assert.equal(result.spec.preview_only,true);
 assert.ok(result.asset_url);
 const after=await game.gameGet(init.id);
 assert.equal(after.scene.cg_url,before.scene.cg_url);
 assert.equal(after.scene.mode,before.scene.mode);
 assert.deepEqual(after.scene.sprites,before.scene.sprites);
 assert.deepEqual(after.messages,before.messages);
 assert.equal(after.version,before.version);
});
test.after(async()=>fs.rm(dir,{recursive:true,force:true}));
