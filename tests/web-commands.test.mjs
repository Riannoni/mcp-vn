import test from 'node:test';
import assert from 'node:assert/strict';
import {matchingCommands,latencyText} from '../standalone-web/web/vn/commands.js';
test('command filtering never treats arguments or normal prose as autocomplete',()=>{
 assert.equal(matchingCommands('/').length,11);
 assert.deepEqual(matchingCommands('/re').map(x=>x.name),['recap','retry']);
 assert.deepEqual(matchingCommands('/roll d20'),[]);
 assert.deepEqual(matchingCommands('hello /'),[]);
});
test('latency uses seconds and Russian labels without exposing IDs or JSON',()=>{
 const text=latencyText({count:1,median_roundtrip_ms:1234,shortest_roundtrip_ms:1234,longest_roundtrip_ms:1234,game_id:'secret-id',observations:[{action_preview:'Осмотреться',observed_roundtrip_ms:1234,action_id:'private-id'}]},2);
 assert.match(text,/1,2 с/);assert.match(text,/Осмотреться/);
 assert.doesNotMatch(text,/game_id|private-id|secret-id|\{|roundtrip/);
 assert.match(latencyText(),/Пока нет/);
});
