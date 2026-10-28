import test from "node:test";
import assert from "node:assert/strict";
import {peekGameEvents,waitGameEvents,pushGameEvent,serverBootId,eventStats} from "../src/live-events.mjs";
import crypto from "node:crypto";
test("event wait wakes on game mutation much faster than periodic polling",async()=>{
 const id=crypto.randomUUID();
 const start=peekGameEvents(id);
 assert.equal(start.boot_id,serverBootId);
 const t=performance.now();
 const pending=waitGameEvents(id,{boot_id:start.boot_id,after_seq:start.seq,wait_ms:2000});
 setTimeout(()=>pushGameEvent(id,"game",{version:4,location:"Тиррен"}),45);
 const update=await pending;
 assert.ok(performance.now()-t<450,"event dispatch should not wait 2 seconds");
 assert.equal(update.reset,false);
 assert.equal(update.events.length,1);
 assert.equal(update.events[0].detail.version,4);
});
test("job stage and game changes can be delivered in one batch",async()=>{
 const id=crypto.randomUUID();
 pushGameEvent(id,"job",{stage:"generated",status:"working"});
 pushGameEvent(id,"game",{version:2});
 const entries=peekGameEvents(id,{boot_id:serverBootId,after_seq:0});
 assert.deepEqual(entries.events.map(e=>e.kind),["job","game"]);
 assert.equal(entries.seq,2);
});
test("boot changes and stale cursors reset safely",async()=>{
 const id=crypto.randomUUID();
 const old=peekGameEvents(id,{boot_id:"old_boot",after_seq:20});
 assert.equal(old.reset,true);
 assert.equal(old.events.length,0);
 const ahead=peekGameEvents(id,{boot_id:serverBootId,after_seq:999});
 assert.equal(ahead.reset,true);
});
test("idle wait terminates without permanent listeners",async()=>{
 const id=crypto.randomUUID(),seen=peekGameEvents(id);
 const result=await waitGameEvents(id,{boot_id:seen.boot_id,after_seq:seen.seq,wait_ms:125});
 assert.equal(result.events.length,0);
 assert.equal(eventStats().listeners,0);
});
