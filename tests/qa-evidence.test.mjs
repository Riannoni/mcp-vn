import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
const dir=await fs.mkdtemp(path.join(os.tmpdir(),"vn-qa-evidence-"));
process.env.VN_DATA_DIR=dir;
process.env.VN_ASSET_SECRET="test-only";
const store=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");
test("QA retains critical metrics and typed evidence",async()=>{
 const game=await store.gameStart();
 const job=await jobs.enqueue({game_id:game.id,kind:"background",prompt:"forest"});
 assert.equal((await jobs.nextJob("gpu")).id,job.id);
 const metrics={};
 for(let n=0;n<36;n++)metrics["metric_"+n]=n;
 metrics.scene_location_verified=true;
 metrics.scene_count_verified=false;
 const out=await jobs.reportQA(job.id,{passed:true,semantic_status:"passed",reasons:[],metrics,
  evidence:{location:{verdict:"verified",confidence:.72},action:{verdict:"unobservable",
  features:{wall_touch:false,uncertain:true,secret:true}},secret:{credential:"do not save"}}});
 assert.equal(out.qa.metrics.scene_location_verified,true);
 assert.equal(out.qa.metrics.scene_count_verified,false);
 assert.ok(Object.keys(out.qa.metrics).length<=32);
 assert.equal(out.qa.evidence.location.confidence,.72);
 assert.equal(out.qa.evidence.action.features.uncertain,true);
 assert.equal(out.qa.evidence.action.features.secret,undefined);
 assert.equal(out.qa.evidence.secret,undefined);
});
