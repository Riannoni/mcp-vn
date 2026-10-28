import test from "node:test";
import assert from "node:assert/strict";
import {planStandaloneVisuals,sceneCGPrompt,sceneCGRequired} from "../src/standalone-visuals.mjs";
import {sceneIntentFingerprint,normalizeVisualState} from "../src/visual-state.mjs";
import {currentSceneMatches} from "../src/art-spec.mjs";

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
 const wanted=planStandaloneVisuals(g,{retry:true});
 assert.equal(wanted.length,1);
 assert.equal(wanted[0].kind,"sprite");
 assert.equal(wanted[0].character,"Мира");
 assert.match(wanted[0].prompt,/fully undressed/);
 assert.equal(g.scene.sprites[0].visual_dirty,false);
});

test("substantial narrator visual change schedules neural CG only after accepted sprites",()=>{
 const scene={sprites:[{name:"Мира",outfit:"green cloak",pose:"kneeling",emotion:"serious",
  image_url:"https://example.test/a.png",transparent:true,visual_dirty:false,
  rendered_variant_key:"anime|green cloak|kneeling|serious"}],
  auto_cg_requested:true,visual_direction:"Mira kneels by the ancient gate, side view",
  cg_url:"",cg_dirty:false};
 const g=game(scene,{identities:{"Мира":{base_sprite_url:"https://example.test/anchor.png"}},messages:[{role:"narrator",text:"Мира опускается на колено."}]});
 assert.equal(sceneCGRequired(g),true);
 const jobs=planStandaloneVisuals(g);
 assert.equal(jobs.length,1);
 assert.equal(jobs[0].kind,"scene");
 assert.equal(jobs[0].neural_scene,true);
 assert.match(jobs[0].prompt,/side view/);
 assert.match(sceneCGPrompt(g),/Мира/);
 assert.equal(planStandaloneVisuals(game({...scene,auto_cg_requested:false})).length,0);
 assert.equal(planStandaloneVisuals(game({...scene,
  sprites:scene.sprites.map(p=>({...p,visual_dirty:true}))},
  {identities:g.identities}))[0].kind,"scene");
});
test("narrator pending turn never launches visual jobs even when CG requested",()=>{
 assert.deepEqual(planStandaloneVisuals(game({auto_cg_requested:true,sprites:[{
  name:"Мира",image_url:"https://example.test/a.png",visual_dirty:false}]},
  {awaiting_narrator:true})),[]);
});

test("narrator-authored visual prompts are passed intact as job positive text",()=>{
 const sprites=[{name:"Мира",outfit:"traveller outfit",pose:"leaning against wall",
  emotion:"calm",image_url:"https://example.test/accepted.png",visual_dirty:false}];
 const cg="One adult character leaning against an old brick wall at sunset, eye-level side shot.";
 const g=game({auto_cg_requested:true,visual_direction:"old directions",
  sprites,image_prompts:{cg,sprites:{"Мира":"A single adult character in a traveller outfit, leaning against a wall."},
   background:"An empty stone town square at dawn."}},
   {identities:{"Мира":{face_url:"https://example.test/face.png"}}});
 const cgJob=planStandaloneVisuals(g);
 assert.equal(cgJob.length,1);
 assert.equal(cgJob[0].narrator_prompt,true);
 assert.equal(cgJob[0].prompt,cg);
 const sp=planStandaloneVisuals(game({...g.scene,auto_cg_requested:false,sprites:[{...sprites[0],visual_dirty:true}]}));
 assert.equal(sp[0].kind,"sprite");
 assert.equal(sp[0].narrator_prompt,true);
 assert.equal(sp[0].prompt,g.scene.image_prompts.sprites["Мира"]);
 const bg=planStandaloneVisuals(game({...g.scene,background_url:""}));
 assert.equal(bg[0].kind,"background");
 assert.equal(bg[0].narrator_prompt,true);
 assert.equal(bg[0].prompt,g.scene.image_prompts.background);
});
test("missing full prompt falls back without falsely claiming narrator authorship",()=>{
 const j=planStandaloneVisuals(game({background_url:""}))[0];
 assert.equal(j.narrator_prompt,false);
 assert.match(j.prompt,/Cinematic establishing/);
});

test("direct neural CG skips even dirty intermediate sprites once a canonical face exists",()=>{
 const image="https://example.test/old.png";
 const sprite={name:"Мира",outfit:"different outfit",pose:"new pose",
  emotion:"tense",image_url:image,visual_dirty:true};
 const g=game({sprites:[sprite],auto_cg_requested:true,cg_url:"",
   image_prompts:{cg:"new shot"}},{identities:{
    "Мира":{face_url:"https://example.test/face.png"}}});
 assert.deepEqual(planStandaloneVisuals(g).map(x=>x.kind),["scene"]);
 assert.equal(planStandaloneVisuals(g)[0].prompt,"new shot");
 const intent=sceneIntentFingerprint(g.scene);
 const g2=game({...g.scene,cg_url:"https://example.test/cg.png",
  cg_composition:"neural_story",cg_basis:intent,cg_dirty:false},
  {identities:g.identities});
 assert.deepEqual(planStandaloneVisuals(g2),[]);
 const g3=game({...g.scene,cg_url:"https://example.test/cg.png",
  cg_composition:"neural_story",cg_basis:intent,cg_dirty:false,
  sprites:[{...sprite,image_url:"https://example.test/new_sprite.png"}]},
  {identities:g.identities});
 assert.equal(sceneIntentFingerprint(g3.scene),intent);
 assert.deepEqual(planStandaloneVisuals(g3),[]);
 assert.deepEqual(planStandaloneVisuals(g,{retry:true}).map(x=>x.kind),["sprite"]);
});
test("without canonical identity, fall back to initial sprite before CG",()=>{
 const g=game({auto_cg_requested:true,sprites:[{name:"Мира",outfit:"cloak",
  pose:"standing",visual_dirty:true,image_url:""}]});
 assert.deepEqual(planStandaloneVisuals(g).map(j=>j.kind),["sprite"]);
});

test("neural CG integrity is independent of sprite PNG but rejects changed wardrobe",()=>{
 const sprite={name:"Мира",outfit:"cloak",pose:"standing",emotion:"calm",
  image_url:"https://example.test/sprite.png",transparent:true,
  visual_dirty:true};
 const scene={location:"Tirren market",background_url:"https://example.test/bg.png",
  background_style:"anime",cg_style:"anime",sprites:[sprite],
  cg_composition:"neural_story",cg_url:"https://example.test/cg.png"};
 const g=game(scene);
 g.scene.cg_basis=sceneIntentFingerprint(g.scene);
 const spec={kind:"scene",style:"anime",composition:"neural_story",
  expected_location:"Tirren market",background_asset:"bg.png",
  cg_basis_snapshot:g.scene.cg_basis,characters:[{name:"Мира",sprite_asset:"sprite.png"}]};
 assert.equal(currentSceneMatches(g,spec),true);
 normalizeVisualState(g);
 assert.equal(g.scene.cg_dirty,false);
 g.scene.sprites[0].pose="kneeling";
 assert.equal(currentSceneMatches(g,spec),false);
});
