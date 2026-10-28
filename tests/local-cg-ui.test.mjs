import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs/promises";

test("local chat CG is a collapsible, independent region with explicit hide/show control",async()=>{
 const html=await fs.readFile(new URL("../web/index.html",import.meta.url),"utf8");
 const js=await fs.readFile(new URL("../web/game.js",import.meta.url),"utf8");
 const css=await fs.readFile(new URL("../web/style.css",import.meta.url),"utf8");
 assert.ok(html.includes('id="local-cg-stage"'));
 assert.ok(html.includes('id="local-cg-toggle"'));
 assert.ok(html.includes('id="local-cg-direction"'));
 assert.ok(html.includes('id="local-video"'));
 assert.ok(html.includes('id="local-scene-video"'));
 assert.match(js,/\$\("local-cg-toggle"\)\.onclick=\(\)=>\{/);
 assert.match(js,/localCgHidden=!localCgHidden/);
 assert.match(js,/stage\.hidden=!ready\|\|localCgHidden/);
 assert.match(js,/call\("queue_local_cg"/);
 assert.match(js,/call\("queue_local_video"/);
 assert.match(css,/\.local-cg-stage\[hidden\]\{display:none!important\}/);
});
