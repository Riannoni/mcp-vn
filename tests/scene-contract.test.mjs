import test from "node:test";
import assert from "node:assert/strict";
import {buildSceneContract} from "../src/scene-contract.mjs";
const actor=(name,region=null)=>({name,actor_region:region,outfit:"green cloak",pose:"standing"});
test("public market includes optional extras without inventing third protagonist",()=>{
 const c=buildSceneContract({kind:"scene",environment:{id:"outdoor_market_square"},
  location:"Tirren market",characters:[actor("Mira"),actor("Devon")]});
 assert.equal(c.principals.length,2);
 assert.equal(c.crowd.policy,"ambient");
 assert.deepEqual(c.principals.map(x=>x.region),[null,null]);
 assert.deepEqual(c.contacts,[]);
});
test("explicit normalized blocking and contact must name an existing actor",()=>{
 const c=buildSceneContract({kind:"local_cg",location:"Room",environment:{id:"indoor_room"},
  characters:[actor("Mira",[.1,.1,.3,.75])],
  state:{characters:[{name:"Mira",pose:"standing",outfit:"blue cape"}],
    camera:"left three-quarter",crowd_policy:"none",contacts:[
     {actor:"Mira",target:"stone wall",kind:"touch",body_part:"hands",target_region:[.4,.1,.2,.5]},
     {actor:"Ghost",target:"stone wall",kind:"hold"}]}});
 assert.equal(c.contacts.length,1);
 assert.equal(c.contacts[0].actor,"Mira");
 assert.deepEqual(c.principals[0].region,[.1,.1,.3,.75]);
 assert.equal(c.crowd.policy,"none");
});
test("narrator cannot smuggle invalid actor regions or bogus crowd policy",()=>{
 const c=buildSceneContract({kind:"scene",environment:{id:"outdoor_forest"},
  characters:[actor("Mira",[.9,.9,.3,.5])],scene:{crowd_policy:"EVERYONE"}});
 assert.equal(c.principals[0].region,null);
 assert.equal(c.crowd.policy,"unspecified");
});
test("actor state changes are part of authoritative CG intent fingerprint",async()=>{
 const {sceneIntentFingerprint}=await import("../src/visual-state.mjs");
 const scene={location:"street",sprites:[{name:"Ada",outfit:"cloak",pose:"standing"}]};
 const baseline=sceneIntentFingerprint(scene);
 scene.sprites[0].actor_region=[.1,.15,.3,.7];
 assert.notEqual(sceneIntentFingerprint(scene),baseline);
 const withRegion=sceneIntentFingerprint(scene);
 scene.crowd_policy="none";
 assert.notEqual(sceneIntentFingerprint(scene),withRegion);
});
