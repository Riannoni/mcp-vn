import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
const root=await fs.mkdtemp(path.join(os.tmpdir(),'vn-retry-classifier-'));
process.env.VN_DATA_DIR=root;
const store=await import('../src/game-store.mjs');
const jobs=await import('../src/jobs.mjs');

test('unrepairable render setup failure is terminal after one attempt',async()=>{
 const game=await store.gameStart();
 const task=await jobs.enqueue({game_id:game.id,kind:'sprite',character:'Мира',
   prompt:'Neutral full-body design reference, adult in blue travel clothes'});
 const claimed=await jobs.nextJob('gpu');
 assert.equal(claimed.id,task.id);
 assert.equal(claimed.attempts,1);
 const result=await jobs.failJob(task.id,
    'Required wall-contact DWPose unavailable: camera_missing',
    {permanent:true});
 assert.equal(result.status,'failed');
 assert.equal(result.attempts,1);
 assert.equal((await jobs.getJob(task.id)).status,'failed');
 assert.equal(await jobs.nextJob('gpu'),null);
});

test('temporary infrastructure failure still schedules bounded retry',async()=>{
 const game=await store.gameStart();
 const task=await jobs.enqueue({game_id:game.id,kind:'sprite',character:'Мира',
   prompt:'Another neutral full-length character study, wearing a blue coat'});
 const first=await jobs.nextJob('gpu');
 assert.equal(first.id,task.id);
 const retry=await jobs.failJob(task.id,'HTTP Error 503',{permanent:false});
 assert.equal(retry.status,'queued');
 const second=await jobs.nextJob('gpu');
 assert.equal(second.id,task.id);
 assert.equal(second.attempts,2);
});
