import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
const root=await fs.mkdtemp(path.join(os.tmpdir(),"vn-memory-"));
process.env.VN_DATA_DIR=root;
const store=await import("../src/game-store.mjs");
const {ensureMemory,patchMemory,queryMemory,closeChapterIfNeeded,contextGuide}=await import("../src/story-memory.mjs");
test("persistent facts, quests and notes survive save/load",async()=>{
 const g=await store.gameStart();
 await store.gameMemoryPatch(g.id,{facts:[{subject:"Мира",key:"mark",scope:"character",
   value:"Носит серебряную метку",importance:5,keywords:["врата","часы"]}],
   quests:[{id:"gate",title:"Пепельные врата",status:"active",objective:"Исследовать часы"}],
   notes:[{scope:"character",subject:"Мира",key:"behavior",text:"Осторожная проводница"}]});
 const read=await store.gameGet(g.id);
 assert.equal(read.memory.facts.length,1);
 assert.equal(read.memory.quests.length,1);
 assert.equal(read.memory.notes.length,1);
 const queried=queryMemory(read,"Мира врата");
 assert.equal(queried.facts[0].value,"Носит серебряную метку");
 assert.equal(queried.quests[0].key,"gate");
 const viaApi=await store.gameMemory(g.id,{query:"Мира"});
 assert.ok(viaApi.retrieved.some(x=>x.kind==="fact"));
});
test("facts update without duplication and rules validate expected version",async()=>{
 const g=await store.gameStart();
 const first=await store.gameMemoryPatch(g.id,{facts:[{subject:"Мира",key:"mark",value:"Серебряный"}]});
 const second=await store.gameMemoryPatch(g.id,{facts:[{subject:"Мира",key:"mark",value:"Сияющий"}]});
 assert.equal(second.memory.facts.length,1);
 assert.equal(second.memory.facts[0].value,"Сияющий");
 await assert.rejects(()=>store.gameMemoryPatch(g.id,{facts:[{subject:"Мира",key:"mark",value:"x"}]},first.version),/Version conflict/);
});
test("narration records action, events, memories and chapter progress",async()=>{
 const g=await store.gameStart();
 for(let i=0;i<10;i++){
  await store.gameAction(g.id,"Проверить руны "+i);
  await store.gameNarrate({game_id:g.id,messages:[
   {speaker:"Мира",text:"Руна "+i},
   {speaker:"Рассказчик",text:"Мира указывает на врата "+i}],
   memory_updates:i===0?{facts:[{scope:"world",subject:"Врата",key:"time",
     value:"Часы движутся вспять"}]}:{}});
 }
 const after=await store.gameGet(g.id);
 assert.equal(after.memory.turn,10);
 assert.ok(after.memory.chapters.length>=1);
 assert.ok(after.memory.events.length>=10);
 assert.equal(after.memory.facts[0].value,"Часы движутся вспять");
 const context=contextGuide(after,"врата");
 assert.ok(context.chapters.length);
 assert.ok(context.recent_events.length);
});
test("undo rolls back memory along with timeline",async()=>{
 const g=await store.gameStart();
 await store.gameAction(g.id,"Открыть дверь");
 await store.gameNarrate({game_id:g.id,messages:[{speaker:"Рассказчик",text:"Ключ найден"}],
  memory_updates:{facts:[{subject:"Ключ",key:"found",value:"Найден"}]}});
 await store.gameUndo(g.id);
 const x=await store.gameGet(g.id);
 assert.equal(x.memory.facts.length,0);
 assert.equal(x.memory.turn,0);
});
test("legacy transcript is backfilled idempotently without invented facts",async()=>{
 const g=await store.gameStart();
 const file=path.join(root,"games",g.id+".json");
 const raw=JSON.parse(await fs.readFile(file,"utf8"));
 delete raw.memory;
 const time=new Date().toISOString();
 for(let i=0;i<24;i++)raw.messages.push({id:"legacy-"+i,
   role:i%2===0?"player":"narrator",speaker:i%2===0?"Макс":"Рассказчик",
   text:i%2===0?"Проверяю врата "+i:"Врата отзываются на шаги "+i,at:time});
 await fs.writeFile(file,JSON.stringify(raw));
 const first=await store.migrateLegacyStoryMemories();
 assert.ok(first.some(x=>x.id===g.id&&x.turns===12));
 const again=await store.migrateLegacyStoryMemories();
 assert.equal(again.some(x=>x.id===g.id),false);
 const saved=await store.gameGet(g.id);
 assert.ok(saved.memory.events.length>=12);
 assert.ok(saved.memory.chapters.length>=1);
 assert.equal(saved.memory.facts.length,0);
});
test("scene cache reuses exact location/time/weather backgrounds without repainting",async()=>{
 const g=await store.gameStart();
 const bg="https://example.org/vn/assets/11111111-2222-3333-4444-555555555555.png";
 await store.attachImage(g.id,{kind:"background",url:bg,style:g.art_style});
 await store.gameAction(g.id,"Иду в лес");
 await store.gameNarrate({game_id:g.id,messages:[{speaker:"Рассказчик",text:"Дошли до леса"}],
  scene:{location:"Лес",time_of_day:"night",weather:"rain"}});
 await store.gameAction(g.id,"Возвращаюсь в город");
 await store.gameNarrate({game_id:g.id,messages:[{speaker:"Рассказчик",text:"Вернулись"}],
  scene:{location:g.scene.location}});
 const returned=await store.gameGet(g.id);
 assert.equal(returned.scene.background_url,bg);
 assert.ok(Object.keys(returned.scene_catalog||{}).length>=1);
});
test("optional adventure mode rolls are audited, narrative mode remains deterministic",async()=>{
 const g=await store.gameStart("ash-gate","Макс Кроу","","realistic","adventure");
 assert.equal(g.rules.mode,"adventure");
 await store.gameAction(g.id,"Осматриваю загадочный проход");
 const result=await store.gameSkillCheck(g.id,{stat:"insight",difficulty:12,description:"Найти проход"});
 assert.equal(typeof result.check.success,"boolean");
 assert.ok(result.check.selected>=1&&result.check.selected<=20);
 assert.equal(result.rules.recent_checks.length,1);
 await store.gameSetRulesMode(g.id,"narrative");
 await assert.rejects(()=>store.gameSkillCheck(g.id,{stat:"insight",difficulty:12}),/disabled/);
});
test.after(async()=>fs.rm(root,{recursive:true,force:true}));
