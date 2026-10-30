import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
const root=await fs.mkdtemp(path.join(os.tmpdir(),"mcp-vn-storyboard-"));
process.env.VN_DATA_DIR=root;
const store=await import("../src/game-store.mjs");
const {sceneIntentFingerprint}=await import("../src/visual-state.mjs");
test("narration preserves actor region and contact without mutating another game",async()=>{
 const g=await store.gameStart();
 const extra=await store.gameStart();
 await store.gameAction(g.id,"Watch the wall");
 const a=await store.gameNarrate({game_id:g.id,messages:[{speaker:"Narrator",text:"Mira approaches the wall."}],
  scene:{visual_mode:"cg",crowd_policy:"none",
    required_visuals:[{kind:"landmark",description:"stone wall"}],
    sprites:[{name:"Мира",
    actor_region:[.1,.1,.4,.8],outfit:"cloak",pose:"standing"}],
    contacts:[{actor:"Мира",target:"wall",body_part:"hands",
      kind:"touch",target_region:[.5,.05,.14,.88]}]}});
 assert.equal(a.scene.crowd_policy,"none");
 assert.deepEqual(a.scene.sprites[0].actor_region,[.1,.1,.4,.8]);
 assert.equal(a.scene.contacts[0].target,"wall");
 assert.equal(a.scene.required_visuals[0].description,"stone wall");
 assert.equal((await store.gameGet(extra.id)).scene.required_visuals,undefined);
 assert.equal((await store.gameGet(extra.id)).scene.contacts,undefined);
 const before=sceneIntentFingerprint(a.scene);
 await store.gameAction(g.id,"Mira moves away");
 const b=await store.gameNarrate({game_id:g.id,messages:[{speaker:"Narrator",text:"She departs."}],
  scene:{sprites:[{name:"Мира",pose:"walking"}],visual_mode:"cg"}});
 assert.deepEqual(b.scene.contacts,[]);
 assert.deepEqual(b.scene.required_visuals,[],"outdated required objects must clear on a new shot");
 assert.equal(b.scene.sprites[0].actor_region,null);
 assert.notEqual(sceneIntentFingerprint(b.scene),before);
 const {artSnapshot}=await import("../src/art-spec.mjs");
 const snap=artSnapshot(b,{kind:"scene",style:b.art_style,
   prompt:"Mira walks alone",neural_scene:true});
 assert.equal(snap.visual_contract.principals.length,1);
 assert.equal(snap.visual_contract.principals[0].region,null);
 assert.equal(snap.max_attempts,2,"interactive neural CG should not do a third blind GPU retry");
 const layered=artSnapshot(b,{kind:"scene",style:b.art_style,
   prompt:"Mira walks alone",neural_scene:false});
 assert.equal(layered.max_attempts,3,"non-neural composition retains standard retries");
});
test.after(async()=>fs.rm(root,{recursive:true,force:true}));
