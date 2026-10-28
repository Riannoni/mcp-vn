// Historic turn timings use already persisted message timestamps. They measure
// the full model/tool/UI round trip, NOT pure neural inference time.
const finite=ms=>Number.isFinite(ms)&&ms>=0?Math.round(ms):null;
export function measureTurnPerformance(g,{limit=12}={}){
 const messages=g.messages||[],items=[];
 for(let i=0;i<messages.length;i++){
  const action=messages[i];
  if(action.role!=="player")continue;
  const next=messages.slice(i+1).find(x=>x.role==="player"||x.role==="narrator");
  if(!next||next.role!=="narrator")continue;
  const duration=finite(Date.parse(next.at)-Date.parse(action.at));
  if(duration===null)continue;
  items.push({
    action_id:action.id,
    action_preview:String(action.text||"").replace(/\s+/g," ").slice(0,95),
    submitted_at:action.at,narrated_at:next.at,
    observed_roundtrip_ms:duration,
    source:"message_timestamps"
  });
 }
 const observed=items.slice(-Math.max(1,Math.min(30,Number(limit)||12)));
 const durations=observed.map(x=>x.observed_roundtrip_ms).sort((a,b)=>a-b);
 const median=durations.length?durations[Math.floor((durations.length-1)/2)]:null;
 return {
  game_id:g.id,count:observed.length,
  median_roundtrip_ms:median,
  shortest_roundtrip_ms:durations[0]??null,
  longest_roundtrip_ms:durations.at(-1)??null,
  observations:observed,
  measured_after_v55:(g.turn_metrics?.recent||[]).slice(-20),
  explanation:"Interval from accepted player action to first saved narrator message. Includes model generation, tool calls, network and scheduling; not pure model inference."
 };
}
