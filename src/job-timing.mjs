// Wall-clock job accounting with immutable per-attempt stage samples.
// The aggregate is always drawn from every attempt, never only the last retry.
const STAGE_KEYS=["prepare_ms","generation_ms","compose_ms","cpu_wait_ms","postprocess_ms","qa_ms","publish_ms"];
const valid=n=>Number.isFinite(n)&&n>=0&&n<=3600000;
export function recordStage(j,values={}){
 const current=j.attempt_history?.at(-1);
 if(!current)return;
 current.timings ||= {};
 for(const key of STAGE_KEYS){
  if(valid(values[key]))current.timings[key]=Math.round(values[key]);
 }
 aggregateTimings(j);
}
export function claimAttempt(j,at=new Date()){
 const now=at.toISOString();
 j.attempt_history ||= [];
 const last=j.attempt_history.at(-1);
 if(last&&!last.finished_at){last.finished_at=now;last.outcome="timed_out"}
 const wait=j.attempt_history.length?
   Math.max(0,Date.parse(now)-Date.parse(last?.finished_at||last?.claimed_at||now)):
   Math.max(0,Date.parse(now)-Date.parse(j.created_at));
 j.attempt_history.push({number:(j.attempts||0)+1,claimed_at:now,
   wait_ms:wait,timings:{},outcome:"working"});
 j.claimed_at=now;
 j.attempts=(j.attempts||0)+1;
 aggregateTimings(j,at);
}
export function finishAttempt(j,outcome,at=new Date()){
 const last=j.attempt_history?.at(-1);
 if(last&&!last.finished_at){
  last.finished_at=at.toISOString();last.outcome=outcome;
 }
 aggregateTimings(j,at);
}
export function aggregateTimings(j,at=new Date()){
 const history=j.attempt_history||[];
 if(!history.length)return j.timings||{};
 const total=Math.max(0,Date.parse(j.finished_at||at.toISOString())-Date.parse(j.created_at));
 const result={queue_wait_ms:history[0]?.wait_ms||0,retry_wait_ms:0,
   attempts:history.length,total_ms:total};
 for(const stage of STAGE_KEYS)result[stage]=0;
 for(let i=0;i<history.length;i++){
  const attempt=history[i];
  if(i>0)result.retry_wait_ms+=attempt.wait_ms||0;
  for(const stage of STAGE_KEYS)result[stage]+=attempt.timings?.[stage]||0;
 }
 const accounted=result.queue_wait_ms+result.retry_wait_ms+
    STAGE_KEYS.reduce((a,s)=>a+result[s],0);
 result.other_ms=total-accounted; // signed if samples overlap
 j.timings=result;
 return result;
}
