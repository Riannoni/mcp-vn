import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
const root=await fs.mkdtemp(path.join(os.tmpdir(),'vn-engine-catalog-'));
process.env.VN_DATA_DIR=root;
const {ENGINE_POLICY,engineSnapshot,assertEngineSnapshot}=await import('../src/engine-policy.mjs');
const {normalizeStoryPackage}=await import('../src/story-package.mjs');
const store=await import('../src/game-store.mjs');
const {artSnapshot}=await import('../src/art-spec.mjs');
function pack(id){
 return {schema:'mcp-vn.story.v1',id,title:'Test '+id,author:'Test Author',
   source:'user-provided',rights_confirmed:true,summary:'A new test world',
   lore:'Its history and characters are independent of every other world.',
   opening:'A new chapter begins at the forest entrance.',
   scene:{location:'Forest entrance'},
   characters:[{id:'guide',name:'Guide',age:30,description:'Adult guide'}],
   choices:['Continue','Wait']};
}
test('global policy applies to all games',()=>{
 assert.equal(ENGINE_POLICY.render.max_anchored_principals_per_pass,4);
 assert.equal(ENGINE_POLICY.render.qa_policy,'strict-v1');
 assert.ok(assertEngineSnapshot(engineSnapshot()));
 assert.throws(()=>assertEngineSnapshot({...engineSnapshot(),qa_policy:'anything'}));
});
test('two imported worlds and playthroughs remain independent',async()=>{
 await store.importStoryPackage(pack('forest-one'));
 await store.importStoryPackage(pack('forest-two'));
 const catalog=await store.list('stories');
 assert.ok(catalog.some(x=>x.id==='ash-gate'));
 assert.equal(catalog.find(x=>x.id==='forest-one').source,'user-provided');
 const a=await store.gameStart('forest-one','Hero A');
 const b=await store.gameStart('forest-two','Hero B');
 assert.notEqual(a.id,b.id);
 assert.notEqual(a.story_id,b.story_id);
 assert.deepEqual(a.engine_contract,engineSnapshot());
 assert.deepEqual(b.engine_contract,engineSnapshot());
 const art=artSnapshot(a,{kind:'background',style:a.art_style,prompt:'Forest background'});
 assert.deepEqual(art.engine,engineSnapshot());
 assert.equal(art.story_id,'forest-one');
 await store.gameAction(a.id,'Inspect the forest',a.version);
 assert.equal((await store.gameGet(a.id)).awaiting_narrator,true);
 assert.equal((await store.gameGet(b.id)).awaiting_narrator,false);
});
test('import never overwrites a template',async()=>{
 await assert.rejects(()=>store.importStoryPackage(pack('forest-one')),/EEXIST/);
 assert.equal((await store.list('stories')).filter(x=>x.id==='forest-one').length,1);
});
test('external packages cannot override engine policy or execute programs',()=>{
 for(const bad of [
  {...pack('bad-one'),rights_confirmed:false},
  {...pack('bad-two'),engine:{qa_policy:'disabled'}},
  {...pack('bad-three'),scene:{location:'Town',background_url:'https://example.test/asset.png'}},
  {...pack('bad-four'),source:'external',source_url:'http://example.test/story'},
  {...pack('../escape')},
  {...pack('bad-six'),source:'external'},
  {...pack('bad-seven'),characters:[{name:'Twin'},{name:'Twin'}]},
 ])assert.throws(()=>normalizeStoryPackage(bad));
});
