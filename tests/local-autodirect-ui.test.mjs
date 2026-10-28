import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
const root=new URL("../web/",import.meta.url);
test("local CG is AI-directed by default and rendered on the left stage",async()=>{
 const html=await fs.readFile(new URL("index.html",root),"utf8");
 const js=await fs.readFile(new URL("game.js",root),"utf8");
 const css=await fs.readFile(new URL("style.css",root),"utf8");
 assert.match(html,/id="local-scene-cg"/);
 assert.match(html,/id="local-cg-advanced"/);
 assert.match(html,/Дополнительный ракурс \(необязательно\)/);
 assert.match(html,/id="render-decision"/);
 assert.match(html,/id="cg-fit-mode"/);
 assert.match(css,/object-fit:contain/);
 assert.match(js,/left\.hidden=!ready\|\|localVideoShowing/);
 assert.match(js,/localCgHidden=true/);
 assert.match(js,/stage\.hidden=!ready\|\|localCgHidden/);
 assert.match(js,/if\(advanced\)\s*\{\s*const direction=/);
 assert.match(js,/const args=\{game_id:game\.id,quality:"standard"\}/);
 assert.match(css,/\.local-scene-cg\[hidden\]/);
 assert.match(html,/id="local-scene-video"/);
});
test("local illustration presentation never changes main story scene or CG URLs",async()=>{
 const js=await fs.readFile(new URL("game.js",root),"utf8");
 const segment=js.split("function drawLocalCgVisibility(){")[1].split("let transcriptState=")[0];
 assert.ok(!segment.includes("game.scene.cg_url="));
 assert.ok(!segment.includes("game.scene.sprites="));
 assert.ok(segment.includes("local-scene-cg"));
 assert.ok(segment.includes("local-cg-stage"));
});
test("completed local video opens as MP4 rather than as a broken image",async()=>{
 const html=await fs.readFile(new URL("index.html",root),"utf8");
 const js=await fs.readFile(new URL("game.js",root),"utf8");
 assert.ok(html.includes('id="preview-video"'));
 assert.match(js,/j\.kind==="video"\?"Открыть видео"/);
 assert.match(js,/openArtPreview\(j\.asset_url,j\.kind\)/);
 assert.match(js,/if\(kind==="video"\)/);
 assert.match(js,/clip\.pause\(\);clip\.removeAttribute\("src"\)/);
});

test("the local stage hides frames that did not pass independent scene verification",async()=>{
 const js=await fs.readFile(new URL("game.js",root),"utf8");
 assert.match(js,/scene_count_verified===true/);
 assert.match(js,/scene_location_verified===true/);
 assert.match(js,/localCgReadyUrl="";drawLocalCgVisibility\(\)/);
 assert.match(js,/CG не принят:/);
});
