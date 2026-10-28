import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

test('late video response does not populate a replaced information dialog',async()=>{
 const nodes=new Map();
 const node=id=>{
  if(!nodes.has(id))nodes.set(id,{hidden:false,textContent:'',src:'',pause(){},removeAttribute(){},replaceChildren(){}});
  return nodes.get(id);
 };
 let finish;
 const response=new Promise(resolve=>{finish=resolve});
 const source=(await readFile(new URL('../standalone-web/web/vn/app.js',import.meta.url),'utf8')).replace(/^import .*;\n/,'');
 const context={document:{getElementById:node,addEventListener(){}},
  fetch:()=>response,console,setTimeout,clearTimeout};
 vm.createContext(context);
 vm.runInContext(source+'\ncurrentGame={id:"game-a"}; globalThis.testHooks={showVideoJob,displayInfo};',context);
 const pending=context.testHooks.showVideoJob('game-a','video-a');
 context.testHooks.displayInfo('История','Текст истории');
 finish({ok:true,json:async()=>({jobs:[{id:'video-a',status:'done',asset_url:'/api/vn/assets/video.mp4'}]})});
 await pending;
 assert.equal(node('info-body').textContent,'Текст истории');
 assert.equal(node('info-video').hidden,true);
});
