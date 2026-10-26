import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
const root=await fs.mkdtemp(path.join(os.tmpdir(),"mcp-vn-"));
process.env.VN_DATA_DIR=root;
process.env.VN_ASSET_SECRET="test-only-secret";
const store=await import("../src/game-store.mjs");
const jobs=await import("../src/jobs.mjs");
test("start, free-text action, narration, undo and persistence",async()=>{
 await store.init();
 const s=await store.list("stories");
 assert.ok(s.find(x=>x.id==="ash-gate"));
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
test("queue and finish local image job",async()=>{
 const g=await store.gameStart();
 const j=await jobs.enqueue({game_id:g.id,prompt:"A fantasy castle",style:"semireal",kind:"background"});
 const next=await jobs.nextJob();
 assert.equal(next.id,j.id);
 const png=Buffer.from("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000b49444154789c636000020000050001a5f645400000000049454e44ae426082","hex");
 const done=await jobs.completeJob(j.id,png,"image/png","https://example.org/vn");
 assert.equal(done.status,"done");
 assert.match((await store.gameGet(g.id)).scene.background_url,/assets\/.*\.png\?sig=[0-9a-f]+$/);
});
test("story import forbids minor characters and missing reuse rights",async()=>{
 await assert.rejects(()=>store.importStory({title:"x",opening:"x",author:"x",source:"original",rights_confirmed:true,characters:[{age:15}]}));
 await assert.rejects(()=>store.importStory({title:"x",opening:"x",author:"x",source:"original"}));
 const s=await store.importStory({title:"Original",opening:"Hello",author:"Me",source:"original",rights_confirmed:true,characters:[{age:28}]});
 assert.ok(s.id);
});
test("public model styles",()=>{
 assert.deepEqual(jobs.styleList(),["anime","semireal","realistic","poster"]);
});
test.after(async()=>fs.rm(root,{recursive:true,force:true}));
