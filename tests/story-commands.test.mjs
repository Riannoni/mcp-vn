import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {parseCommand,rollDice,commandInstruction} from '../src/story-commands.mjs';

const root=await mkdtemp(path.join(tmpdir(),'vn-commands-'));
process.env.VN_DATA_DIR=root;
const store=await import('../src/game-store.mjs');
const {makeNarrationPacket}=await import('../src/narration-packet.mjs');
test.after(()=>rm(root,{recursive:true,force:true}));

test('commands validate exact names, arguments and bounded dice',()=>{
 assert.deepEqual(parseCommand('/continue'),{name:'continue',argument:''});
 assert.equal(parseCommand(' /cut гавань на рассвете ').argument,'гавань на рассвете');
 for(const raw of ['/unknown','/skip','/cut','/ooc','/improvise','/undo now','/recap now','/roll 0d6','/roll 101d6','/roll d1','/roll d1001','/roll 2d6 adv','/roll d20 adv dis'])
  assert.throws(()=>parseCommand(raw),undefined,raw);
 assert.equal(parseCommand('/roll').name,'roll');
});
test('dice modifier, advantage, disadvantage and DC use actual bounded rolls',()=>{
 let values=[2,5];
 const a=rollDice('2d6+3 dc 9 открыть дверь',()=>values.shift());
 assert.equal(a.total,10);assert.equal(a.success,true);assert.deepEqual(a.rolls,[2,5]);
 assert.equal(a.purpose,'открыть дверь');
 values=[4,17];assert.equal(rollDice('d20 adv dc 15',()=>values.shift()).total,17);
 values=[4,17];assert.equal(rollDice('d20 dis',()=>values.shift()).total,4);
 for(let i=0;i<30;i++){const r=rollDice('d20');assert.ok(r.total>=1&&r.total<=20);}
});
test('retry restores pre-turn state, keeps action and dice, and undo restores original snapshot',async()=>{
 const initial=await store.gameStart();
 let pending=await store.gameCommand(initial.id,'/roll d20 dc 12 поиск',initial.version);
 const roll=pending.messages.at(-1).command.roll;
 const action=pending.messages.at(-1).text;
 let done=await store.gameNarrate({game_id:initial.id,messages:[{text:'Старый ответ.'}],scene:{location:'Новое место'},inventory_add:['ключ'],flags:{found:true}});
 pending=await store.gameRetry(initial.id,'короче',done.version);
 assert.equal(pending.scene.location,initial.scene.location);
 assert.deepEqual(pending.inventory,initial.inventory);
 assert.equal(pending.messages.at(-1).text,action);
 assert.deepEqual(pending.messages.at(-1).command.roll,roll);
 assert.equal(pending.messages.filter(m=>m.role==='player').length,1);
 const packet=makeNarrationPacket(pending);
 assert.equal(packet.command.retry_note,'короче');
 assert.deepEqual(packet.command.roll,roll);
 assert.match(packet.command.instruction,/кубик/i);
 done=await store.gameNarrate({game_id:initial.id,messages:[{text:'Новый ответ.'}]});
 const undone=await store.gameUndo(initial.id,done.version);
 assert.deepEqual(undone.messages,initial.messages);
 assert.equal(undone.undo_stack.length,0);
});
test('rejected commands, pending and stale operations do not change the save',async()=>{
 const g=await store.gameStart();
 await assert.rejects(store.gameCommand(g.id,'/bad',g.version));
 assert.equal((await store.gameGet(g.id)).version,g.version);
 const pending=await store.gameCommand(g.id,'/continue',g.version);
 await assert.rejects(store.gameRetry(g.id,'',pending.version));
 await assert.rejects(store.gameUndo(g.id,pending.version));
 const done=await store.gameNarrate({game_id:g.id,messages:[{text:'Дальше.'}]});
 await assert.rejects(store.gameRetry(g.id,'',g.version));
 await assert.rejects(store.gameUndo(g.id,g.version));
 assert.equal((await store.gameGet(g.id)).version,done.version);
 const outcomes=await Promise.allSettled([store.gameUndo(g.id,done.version),store.gameUndo(g.id,done.version)]);
 assert.equal(outcomes.filter(x=>x.status==='fulfilled').length,1);
});
test('improvise is the only command that delegates protagonist narration',()=>{
 assert.match(commandInstruction({name:'improvise',argument:'поздороваться'}),/героя/);
 assert.match(commandInstruction({name:'end',argument:''}),/финал/);
});
test('late narration cannot commit over the new pending retry',async()=>{
 const g=await store.gameStart();
 const old=await store.gameAction(g.id,'Тест',g.version);
 const oldId=old.messages.at(-1).id;
 const done=await store.gameNarrate({game_id:g.id,messages:[{text:'Первый ответ.'}]});
 const retry=await store.gameRetry(g.id,'',done.version);
 await assert.rejects(store.gameNarrate({game_id:g.id,expected_action_id:oldId,messages:[{text:'Запоздалый ответ.'}]}));
 assert.equal((await store.gameGet(g.id)).version,retry.version);
});
test('video does not accept a frame without scene provenance',async()=>{
 const {verifiedVideoFrame}=await import('../src/standalone-commands.mjs');
 const g={scene:{cg_url:'https://example.org/frame.png'}};
 assert.throws(()=>verifiedVideoFrame(g,[{kind:'scene',status:'done',asset_url:g.scene.cg_url,qa:{passed:true}}]));
});
