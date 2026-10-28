import {randomInt} from 'node:crypto';

export const STORY_COMMANDS=new Set(['continue','improvise','skip','cut','end','roll']);
const names=new Set([...STORY_COMMANDS,'ooc','recap','video','retry','undo']);
export function parseCommand(input){
 if(typeof input!=='string'||input.length>2000)throw Error('Команда: не более 2000 символов');
 const match=input.trim().match(/^\/([a-z]+)(?:\s+([\s\S]*))?$/i);
 if(!match||!names.has(match[1].toLowerCase()))throw Error('Неизвестная команда. Выбери команду из меню «/».');
 const name=match[1].toLowerCase(),argument=(match[2]||'').trim();
 if(['improvise','skip','cut','ooc'].includes(name)&&!argument)
  throw Error('Добавь текст после /'+name+'.');
 if(['undo','recap'].includes(name)&&argument)throw Error('/'+name+' не принимает параметры.');
 if(name==='roll')diceSpec(argument);
 return {name,argument};
}
function diceSpec(argument){
 const parts=String(argument||'').trim().split(/\s+/u).filter(Boolean);
 let count=1,sides=20,modifier=0,mode='',dc=null;
 if(parts[0]&&/^[\dd+-]/i.test(parts[0])){
  const m=parts.shift().match(/^(\d*)d(\d+)([+-]\d+)?$/i);
  if(!m)throw Error('Кубики: /roll 2d6+3 или /roll d20 adv dc 15 задача.');
  count=Number(m[1]||1);sides=Number(m[2]);modifier=Number(m[3]||0);
 }
 if(count<1||count>100||sides<2||sides>1000||Math.abs(modifier)>10000)
  throw Error('Допустимо 1–100 кубиков с 2–1000 гранями, модификатор до 10000.');
 while(parts.length){
  const token=parts[0].toLowerCase();
  if(token==='adv'||token==='dis'){
   if(mode||count!==1)throw Error('adv/dis используется один раз и только с одним кубиком.');
   mode=parts.shift().toLowerCase();
  }else if(token==='dc'){
   parts.shift();
   if(dc!==null||!/^\d+$/.test(parts[0]||''))throw Error('После dc укажи сложность числом.');
   dc=Number(parts.shift());if(dc>100000)throw Error('Слишком большая сложность.');
  }else break;
 }
 return {count,sides,modifier,mode,dc,purpose:parts.join(' ')};
}
export function rollDice(argument,random=(sides)=>randomInt(1,sides+1)){
 const spec=diceSpec(argument);
 const rolls=Array.from({length:spec.mode?2:spec.count},()=>random(spec.sides));
 const base=spec.mode==='adv'?Math.max(...rolls):spec.mode==='dis'?Math.min(...rolls):rolls.reduce((a,b)=>a+b,0);
 const total=base+spec.modifier;
 return {...spec,rolls,total,success:spec.dc===null?null:total>=spec.dc};
}
export function prepareStoryCommand(input){
 const command=parseCommand(input);
 if(!STORY_COMMANDS.has(command.name))throw Error('Эта команда не создаёт новый ход.');
 if(command.name==='roll')command.roll=rollDice(command.argument);
 let text='/'+command.name+(command.argument?' '+command.argument:'');
 if(command.roll){
  const r=command.roll;
  text+='\nКубики: '+r.rolls.join(', ')+(r.mode?' ('+r.mode+')':'')+
   (r.modifier?' '+(r.modifier>0?'+':'')+r.modifier:'')+' → '+r.total+
   (r.dc===null?'':' против '+r.dc+' — '+(r.success?'успех':'неудача'));
 }
 return {text,command};
}
export function commandInstruction(command){
 if(!command)return '';
 const rules={
  continue:'Продолжи историю через события и NPC. Не выбирай действия и слова за героя. Уточнение задаёт направление событий.',
  improvise:'Только в этом ходе игрок разрешил тебе написать действия и реплики его героя по заданной идее, а затем реакцию мира и продолжение сюжета.',
  skip:'Перенеси события вперёд на заданный промежуток времени. Кратко свяжи сцены и отрази время суток в scene, если оно изменилось.',
  cut:'Перейди к указанному месту, моменту или точке зрения. Обнови scene только по показанной новой сцене.',
  end:'Напиши завершённый финал истории сейчас, с учётом пожелания. Не предлагай новых завязок; choices должен быть пустым.',
  roll:'Кубики уже бросил сервер. Сохрани указанный результат, модификатор и успех/неудачу. Не перебрасывай и не подменяй числа. Опиши последствия проверки в истории.'
 };
 return [rules[command.name]||'',command.argument?'Пожелание игрока: '+command.argument:'',
  command.roll?'Результат кубиков (факт): '+JSON.stringify(command.roll):'',
  command.retry_note?'Это замена предыдущего ответа. Исправление: '+command.retry_note:''].filter(Boolean).join('\n');
}
