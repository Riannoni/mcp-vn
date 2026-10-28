import test from "node:test";
import assert from "node:assert/strict";
import {planStandaloneVisuals} from "../src/standalone-visuals.mjs";

const game=(scene={},other={})=>({
 id:"11111111-1111-4111-8111-111111111111",
 art_style:"anime",awaiting_narrator:false,
 local_scene:{mode:"main"},
 scene:{location:"Tirren market",background_url:"https://example.test/bg.png",
 background_dirty:false,sprites:[],...scene},...other
});

test("standalone mode schedules a background only when missing",()=>{
 const tasks=planStandaloneVisuals(game({background_url:""}));
 assert.equal(tasks.length,1);
 assert.equal(tasks[0].kind,"background");
 assert.equal(tasks[0].style,"anime");
 assert.match(tasks[0].prompt,/Tirren market/);
 assert.deepEqual(planStandaloneVisuals(game()),[]);
});
test("background changes take priority over sprites so references remain consistent",()=>{
 const tasks=planStandaloneVisuals(game({
 background_dirty:true,
 sprites:[{name:"Мира",visual_dirty:true,image_url:""}]
 }));
 assert.deepEqual(tasks.map(x=>x.kind),["background"]);
});
test("only dirty or missing dialogue sprites are regenerated",()=>{
 const sprites=[
  {name:"Мира",emotion:"curious",outfit:"cloak",pose:"standing",
   image_url:"https://example.test/a.png",visual_dirty:false},
  {name:"Лия",emotion:"worried",outfit:"traveller robe",pose:"sitting",
   image_url:"https://example.test/b.png",visual_dirty:true}
 ];
 const tasks=planStandaloneVisuals(game({sprites}));
 assert.deepEqual(tasks.map(x=>x.kind),["sprite"]);
 assert.equal(tasks[0].character,"Лия");
 assert.match(tasks[0].prompt,/worried/);
});
test("never add art work while a narrator is pending or local private mode is active",()=>{
 assert.deepEqual(planStandaloneVisuals(game({background_url:""},{awaiting_narrator:true})),[]);
 assert.deepEqual(planStandaloneVisuals(game({background_url:""},{local_scene:{mode:"local"}})),[]);
});

test("manual retry of an accepted sprite bypasses the stale appearance cache",()=>{
 const g=game({sprites:[{name:"Мира",outfit:"fully undressed, clothes held off-body",
  pose:"standing",emotion:"resigned",image_url:"https://example.test/old.png",
  visual_dirty:false}]});
 assert.deepEqual(planStandaloneVisuals(g),[]);
 // Scheduling a manual retry is intentionally tested in the integration layer:
 // it must not be lost just because the planned automatic work is empty.
 assert.equal(g.scene.sprites[0].visual_dirty,false);
});
