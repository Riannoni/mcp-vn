import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";

const root=await fs.mkdtemp(path.join(os.tmpdir(),"web-vn-receipt-test-"));
process.env.VN_DATA_DIR=root;
process.env.VN_CREATION_RECEIPT_HMAC_KEY="1".repeat(64); // disposable test key, never production
const store=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");
const digest=b=>crypto.createHash("sha256").update(b).digest("hex");
const url=n=>"https://example.invalid/assets/"+n+"?sig=test";
async function fixture(){
 const g=await store.gameStart("ash-gate","Test hero","","realistic");
 const bg=crypto.randomUUID()+".png",actor=crypto.randomUUID()+".png";
 await fs.writeFile(path.join(root,"assets",bg),Buffer.from("immutable background plate bytes"));
 await fs.writeFile(path.join(root,"assets",actor),Buffer.from("immutable actor reference bytes"));
 g.scene={location:"Private disposable courtyard",cg_revision:1,
  background_url:url(bg),background_style:"realistic",background_dirty:false,
  sprites:[{name:"Мира",outfit:"navy jacket",pose:"standing",emotion:"neutral",
   transparent:true,visual_dirty:false}]};
 g.identities={"Мира":{name:"Мира",base_sprite_url:url(actor),base_style:"realistic"}};
 g.version=7;
 await fs.writeFile(path.join(root,"games",g.id+".json"),JSON.stringify(g));
 return {g,bg,actor};
}
async function queue(g,priority=50){
 return jobs.enqueue({game_id:g.id,kind:"scene",neural_scene:true,priority,
  prompt:"Disposable source-only contract test"});
}
test("creation receipt binds actual queued scene, save version and asset bytes",async()=>{
 const {g,bg,actor}=await fixture(),j=await queue(g);
 const r=j.creation_receipt_v1;
 assert.ok(r,"must persist a creation-time producer receipt, not a synthetic posthoc manifest");
 assert.equal(r.game_version,7);
 assert.equal(r.scene_revision,1);
 assert.equal(r.job_id,j.id);
 assert.equal(r.source_assets.find(x=>x.role==="background").sha256,
  digest(await fs.readFile(path.join(root,"assets",bg))));
 assert.equal(r.source_assets.find(x=>x.role==="actor_anchor").sha256,
  digest(await fs.readFile(path.join(root,"assets",actor))));
 assert.equal(r.output_binding,"pending_not_verified");
 assert.equal((await jobs.verifyCreationReceipt(j)).verified,true);
});
test("missing producer signing key fails closed before enqueue",async()=>{
 const {g}=await fixture();
 const saved=process.env.VN_CREATION_RECEIPT_HMAC_KEY;
 delete process.env.VN_CREATION_RECEIPT_HMAC_KEY;
 try{await assert.rejects(()=>queue(g),/receipt.*key|signing.*key/i)}
 finally{process.env.VN_CREATION_RECEIPT_HMAC_KEY=saved}
});
test("forged receipt and cross-scene job cannot verify",async()=>{
 const {g}=await fixture(),j=await queue(g);
 assert.equal((await jobs.verifyCreationReceipt(j)).verified,true);
 const forged=structuredClone(j);
 forged.creation_receipt_v1.game_version=999;
 await assert.rejects(()=>jobs.verifyCreationReceipt(forged),/receipt|signature|mismatch/i);
 const wrongScene=structuredClone(j);
 wrongScene.spec.expected_location="another scene";
 await assert.rejects(()=>jobs.verifyCreationReceipt(wrongScene),/receipt|scene|mismatch/i);
 const raw=JSON.parse(await fs.readFile(path.join(root,"games",g.id+".json"),"utf8"));
 raw.version++;
 await fs.writeFile(path.join(root,"games",g.id+".json"),JSON.stringify(raw));
 await assert.rejects(()=>jobs.verifyCreationReceipt(j),/scene|save|version|mismatch/i);
});
test("altered source plate fails closed, never treated as a G2 proof",async()=>{
 const {g,bg}=await fixture(),j=await queue(g);
 await fs.writeFile(path.join(root,"assets",bg),Buffer.from("replaced plate"));
 await assert.rejects(()=>jobs.verifyCreationReceipt(j),/asset|plate|mismatch/i);
});
test("missing source plate refuses enqueue without leaving a queued job",async()=>{
 const {g,bg}=await fixture();
 await fs.unlink(path.join(root,"assets",bg));
 const before=(await fs.readdir(path.join(root,"jobs"))).length;
 await assert.rejects(()=>queue(g),/ENOENT|source asset/i);
 assert.equal((await fs.readdir(path.join(root,"jobs"))).length,before);
});
test("coalesced request keeps the same authenticated creation receipt",async()=>{
 const {g}=await fixture(),first=await queue(g);
 const again=await queue(g);
 assert.equal(again.id,first.id);
 assert.equal(again.deduplicated,true);
 assert.deepEqual(again.creation_receipt_v1,first.creation_receipt_v1);
});
test("tampered queued receipt is blocked before GPU worker claim",async()=>{
 const {g}=await fixture(),j=await queue(g);
 const jobFile=path.join(root,"jobs",j.id+".json");
 const forged=JSON.parse(await fs.readFile(jobFile,"utf8"));
 forged.creation_receipt_v1.source_assets[0].sha256="0".repeat(64);
 forged.priority=100;
 await fs.writeFile(jobFile,JSON.stringify(forged));
 const next=await jobs.nextJob("gpu");
 assert.notEqual(next?.id,j.id,"forged job must never be offered to a GPU worker");
 const stored=await jobs.getJob(j.id);
 assert.equal(stored.status,"failed");
 assert.match(stored.error,/receipt/i);
});
test("source mutation after claim blocks publish before any PNG or QA handling",async()=>{
 const {g,bg}=await fixture(),j=await queue(g,100);
 const claimed=await jobs.nextJob("gpu");
 assert.equal(claimed.id,j.id);
 await fs.writeFile(path.join(root,"assets",bg),Buffer.from("mutated after claim"));
 await assert.rejects(
  ()=>jobs.completeJob(j.id,Buffer.from("not a PNG"),"image/png","https://example.invalid"),
  /source asset|receipt|mismatch/i);
 const still=await jobs.getJob(j.id);
 assert.equal(still.status,"working","failed publish must not publish or accept a PNG");
 assert.equal(still.asset_url,undefined);
});
test("legacy unsigned neural job is refused before GPU claim",async()=>{
 const {g}=await fixture(),j=await queue(g,100);
 const jobFile=path.join(root,"jobs",j.id+".json");
 const unsigned=JSON.parse(await fs.readFile(jobFile,"utf8"));
 delete unsigned.creation_receipt_v1;
 await fs.writeFile(jobFile,JSON.stringify(unsigned));
 const next=await jobs.nextJob("gpu");
 assert.notEqual(next?.id,j.id);
 assert.equal((await jobs.getJob(j.id)).status,"failed");
});
