import * as games from './game-store.mjs';
import * as local from './local-scene.mjs';
import * as jobs from './jobs.mjs';
import {parseCommand} from './story-commands.mjs';
import {makeNarrationPacket} from './narration-packet.mjs';
import {currentSceneMatches} from './art-spec.mjs';

const modelName=id=>({'local-cydonia-24b':'cydonia:24b-v4.3-iq4_xs','local-qwen-9b':'qwen3.5:9b-q4_K_M'}[id]||id||'');
export async function standaloneContext(id){
 const g=await games.gameGet(id),packet=makeNarrationPacket(g);
 if(g.local_scene?.mode==='local'){
  const ep=await local.getLocalEpisode(id);
  packet.recent_dialogue=(ep.transcript||[]).slice(-30).map(({role,speaker,text})=>({role,speaker,text:String(text).slice(0,2200)}));
  packet.scene=ep.visual_state||packet.scene;
 }
 return packet;
}
export function verifiedVideoFrame(g,allJobs){
 if(g.awaiting_narrator||g.scene?.cg_dirty||!g.scene?.cg_url)
  throw Error('Сначала дождись готового кадра сцены: нажми «Собрать CG».');
 const frame=allJobs.find(j=>j.kind==='scene'&&j.status==='done'&&
  j.asset_url===g.scene.cg_url&&j.qa?.passed&&j.spec&&currentSceneMatches(g,j.spec));
 if(!frame)throw Error('Для видео нужен проверенный кадр текущей сцены. Сначала собери новый CG.');
 return frame;
}
export async function executeStandaloneCommand(input){
 const {name,argument}=parseCommand(input.action);
 const id=String(input.game_id||'');
 if(!/^[a-f0-9-]{36}$/i.test(id))throw Error('Неверный ID сохранения.');
 const g=await games.gameGet(id);
 if(!Number.isSafeInteger(input.expected_version)||input.expected_version!==g.version)
  throw Error('Версия сохранения изменилась. Обнови историю.');
 if(['undo','video'].includes(name)&&input.confirmed!==true)
  throw Error('Подтверди /'+name+' перед выполнением.');
 if(name==='video'){
  if(g.local_scene?.mode==='local')return {type:'video',job:await local.queueLocalVideo(id,{motion:argument})};
  const frame=verifiedVideoFrame(g,await jobs.jobsForGame(id));
  const last=g.messages.filter(x=>x.role==='narrator').at(-1)?.text||'';
  const prompt=['Animate the supplied current story frame. Preserve characters, costumes, location and lighting.',
   'Story context: '+last.slice(0,1200),'Motion: '+(argument||'Subtle natural movement and gentle cinematic camera motion.')].join('\n');
  const job=await jobs.enqueue({game_id:id,kind:'video',quality:'fast',preview_only:true,
   force:true,priority:40,prompt,video_start_asset:frame.asset_url,video_source_verified:true});
  return {type:'video',job:{id:job.id,status:job.status}};
 }
 if(['ooc','recap'].includes(name))throw Error('Эта команда выполняется вне сюжета.');
 if(g.local_scene?.mode==='local'){
  if(name==='undo'||name==='retry')return local.reviseLocalTurn(id,{
   version:input.expected_version,retry:name==='retry',note:argument,model:modelName(input.model)});
  return {type:'local',request:await local.submitLocalCommand(id,input.action,input.expected_version,modelName(input.model))};
 }
 if(name==='undo')return {type:'undo',game:await games.gameUndo(id,input.expected_version)};
 const pending=name==='retry'?await games.gameRetry(id,argument,input.expected_version):
  await games.gameCommand(id,input.action,input.expected_version);
 return {packet:makeNarrationPacket(pending)};
}
