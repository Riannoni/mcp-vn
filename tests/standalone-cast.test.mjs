import test from "node:test";
import assert from "node:assert/strict";
import {mkdtemp,rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import path from "node:path";

const root=await mkdtemp(path.join(tmpdir(),"vn-standalone-cast-"));
process.env.VN_DATA_DIR=root;
const store=await import("../src/game-store.mjs");

test("standalone visual repair only adds an established NPC after narrator names her",async()=>{
 const g=await store.gameStart("ash-gate","Макс Кроу","","anime");
 let current=await store.gameEnsureSceneCast(g.id);
 assert.equal(current.scene.sprites.length,0);
 const turn=await store.gameAction(g.id,"Я обращаюсь к проводнице.",g.version);
 await store.gameNarrate({game_id:g.id,
  messages:[{speaker:"Мира",text:"Мира отвечает путешественнику и показывает арку."}]});
 const before=await store.gameGet(g.id);
 assert.equal(before.scene.sprites.length,0);
 current=await store.gameEnsureSceneCast(g.id);
 assert.equal(current.scene.sprites.length,1);
 assert.equal(current.scene.sprites[0].name,"Мира");
 assert.equal(current.scene.sprites[0].image_url,"");
 assert.equal(current.art_style,"anime");
 assert.equal(current.messages.length,before.messages.length);
 const second=await store.gameEnsureSceneCast(g.id);
 assert.equal(second.version,current.version,"cast repair must be idempotent");
});
test.after(async()=>rm(root,{recursive:true,force:true}));
