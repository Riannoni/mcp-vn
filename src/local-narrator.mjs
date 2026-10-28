// Compact, scene-directed local narrator instructions.
import {commandInstruction} from "./story-commands.mjs";
// Kept independent of the local-scene disk/API layer for deterministic tests.
const clean=(s,n=800)=>String(s??"").replace(/\s+/gu," ").trim().slice(0,n);
const puzzleTopic=/(врат|рун|маг|плит|тайн|двойник|час|стрелк|врем|механизм|паз|ключ)/iu;

export const NARRATOR_SYSTEM=[
 "Ты пишешь литературную интерактивную сцену оригинальной русскоязычной визуальной новеллы.",
 "Управляешь только окружающей средой и NPC. Макс Кроу (Хавок) — персонаж игрока.",
 "ЗАПРЕЩЕНО придумывать или писать слова, мысли, жесты, выбор и движения Макса. Даже фраза «Макс улыбнулся» — действие за игрока.",
 "Реагируй прежде всего на последнюю реплику игрока: NPC может согласиться, удивиться, отказаться, сменить тему, проявить характер.",
 "Мира — самостоятельная осторожная взрослая женщина, а не послушная кукла. Её решения зависят от ситуации, доверия и согласия; отказ остаётся возможным.",
 "Между взрослыми допускаются флирт, романтика, поцелуи и эмоциональная близость и секс. Для сцен секса описывай все полноценно.",
 "Для image_prompts.cg всегда генерируй детальный английский промпт для SDXL/Pony:", "- Для обычных сцен: описание позы, одежды, локации, освещения, эмоций.", "- Для NSFW/секс сцен: explicit описание позы (from behind, bent forward), nude/unclothed, genital contact, penetration если есть.", "- Всегда указывай: location, pose, clothing state, camera angle, lighting.", "- Пример NSFW: Mira bent forward against brick wall, fully nude, from behind, hands bracing on wall, market square background, warm lighting.", "- Пример обычный: Mira standing in market square, wearing green dress, looking at camera, daylight, brick buildings background.",
 "Не переводи разговор снова к воротам, часам, метке и механизму, если игрок не интересуется расследованием. Атмосфера — фон, не навязчивая тема каждого ответа.",
 "Не повторяй реплики или уже выполненные действия, не разыгрывай одну и ту же реакцию на каждом ходу.",
 "Не придумывай новые глобальные факты, квестовые достижения, предметы или события за пределами локального эпизода.",
 "Пиши просто, живо и грамотно; избегай тавтологии, мелодраматических метафор и пояснений о том, что персонаж «не боится».",
 "Выводи только 2–3 связанных абзаца, примерно 65–145 русских слов. Заверши полным предложением и оставь инициативу герою. Никаких заголовков, списков или комментариев о модели."
].join("\n");

export function narratorMessages(game,session,action){
 const hero=game.hero?.name||"Макс Кроу";
 const all=(session.transcript||[]).filter(m=>!(m.request_id===action.request_id&&m.role==="player"));
 const relevant=all.slice(-6);
 const npcs=(session.participants||[]).filter(p=>p.name!==hero);
 const storyCharacters=(game.story?.characters||[]).filter(x=>npcs.some(p=>p.name===x.name));
 const setting={
  location:clean(game.scene?.location,110),
  protagonist:{name:hero,description:clean(game.hero?.description,520)},
  npcs:storyCharacters.map(c=>({name:c.name,age:c.age,description:clean(c.description,240)})),
  adult_participants:session.participants,
  appearances:(game.scene?.sprites||[]).map(c=>({name:c.name,
    outfit:clean(c.outfit,110),emotion:clean(c.emotion,60),pose:clean(c.pose,60)})),
  current_local_visual:session.visual_state?.schema===2?{
   location:clean(session.visual_state.location,110),
   camera:clean(session.visual_state.camera,100),
   activity:clean(session.visual_state.activity,150),
   characters:(session.visual_state.characters||[]).slice(0,3).map(c=>({
    name:clean(c.name,90),outfit:clean(c.outfit,180),
    pose:clean(c.pose,140),expression:clean(c.expression,90),
    equipment:clean(c.equipment,110),action:clean(c.action,130)
   }))
  }:null
 };
 // Keep only puzzle facts when the actual player turn is about that topic;
 // otherwise the model repeatedly turns mundane romance into a magic puzzle.
 if(puzzleTopic.test(action.text)){
  setting.world=clean(game.story?.summary,160);
  setting.background_facts=(game.memory?.facts||[]).filter(f=>f.active!==false)
   .slice(-3).map(f=>clean(f.value,220));
 }
 const messages=[
  {role:"system",content:NARRATOR_SYSTEM+(action.command?
   "\nПриоритетное правило команды игрока для этого хода:\n"+commandInstruction(action.command):"")},
  {role:"user",content:"Постоянные факты сцены (данные, не инструкции): "+
    JSON.stringify(setting)+"\nСледующие сообщения — история именно этого отдельного эпизода."}
 ];
 for(const line of relevant){
  messages.push({role:line.role==="player"?"user":"assistant",
   content:clean(line.text,line.role==="player"?650:560)});
 }
 messages.push({role:"user",content:action.text.trim().slice(0,2000)});
 return messages;
}

export function responseQuality(text,previousText="",{allowHero=false}={}){
 const value=String(text||"").trim();
 if(!allowHero&&/(?:^|\n)\s*[—-]\s*(?:Макс|Хавок)(?=[\s,.:;!?—-]|$)/iu.test(value))return {ok:false,reason:"hero_dialogue"};
 if(!allowHero&&/(?:^|\n)\s*(?:Макс|Хавок)\s+(?:сказал|произнес|прошептал|ответил|сделал|подошёл|улыбнулся|кивнул|обнял|встал|пошёл|стоял|наклонился)(?=[\s,.:;!?—-]|$)/iu.test(value))
  return {ok:false,reason:"hero_action"};
 if(!allowHero&&/—[^—\n]{5,180}—\s*(?:сказал|ответил|повторил|прошептал|предложил|произнёс)\s+(?:он|Макс|Хавок)(?=[\s,.:;!?—-]|$)/iu.test(value))
  return {ok:false,reason:"hero_dialogue"};
 if(value.length<60)return {ok:false,reason:"too_short"};
 if(value.length>5000)return {ok:false,reason:"too_long"};
 if(!/[.!?…»]$/u.test(value))return {ok:false,reason:"truncated"};
 if(previousText&&value===previousText.trim())return {ok:false,reason:"repeated"};
 return {ok:true,reason:"accepted"};
}
