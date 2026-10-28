export const COMMANDS=[
 {name:'continue',icon:'▶',args:'что должно произойти дальше',optional:true,description:'Позволить истории продолжаться самой.'},
 {name:'improvise',icon:'✦',args:'что герой делает или говорит',description:'Написать ход героя по твоей идее и продолжить сюжет.'},
 {name:'ooc',icon:'◌',args:'вопрос или заметка',description:'Поговорить с рассказчиком вне сюжета. История не меняется.'},
 {name:'skip',icon:'◷',args:'сколько времени проходит',description:'Прыжок во времени, например: /skip три дня.'},
 {name:'cut',icon:'▣',args:'место, момент или точка зрения',description:'Перейти к новой сцене, например: /cut гавань на рассвете.'},
 {name:'recap',icon:'▤',args:'',description:'Краткий пересказ событий и текущей ситуации.'},
 {name:'end',icon:'⚑',args:'как всё должно закончиться',optional:true,description:'Написать финал истории прямо сейчас.'},
 {name:'video',icon:'▷',args:'что показать',optional:true,description:'Оживить готовый кадр сцены. Запуск с подтверждением.'},
 {name:'roll',icon:'⚄',args:'2d6+3 · adv/dis · dc 15 · на что',optional:true,description:'Бросить кубики. Рассказчик учтёт результат в истории.'},
 {name:'retry',icon:'↻',args:'что изменить',optional:true,description:'Переписать последний ответ, сохранив действие героя.'},
 {name:'undo',icon:'↶',args:'',description:'Отменить последний ход. Требует подтверждения.'}
];
export function matchingCommands(value,showAll=false){
 if(showAll)return COMMANDS;
 const match=String(value).match(/^\/([a-z]*)$/i);
 return match?COMMANDS.filter(x=>x.name.startsWith(match[1].toLowerCase())):[];
}
export function latencyText(performance={},lastWeb=null){
 const seconds=ms=>Number.isFinite(ms)?(ms/1000).toLocaleString('ru-RU',{maximumFractionDigits:1})+' с':'нет данных';
 const lines=[];
 if(Number.isFinite(lastWeb))lines.push('Последний ответ в этом окне: '+seconds(lastWeb*1000));
 if(!performance.count)return [...lines,'Пока нет завершённых ходов для сравнения.'].join('\n');
 lines.push('Завершённых ходов: '+performance.count,
  'Обычно (медиана): '+seconds(performance.median_roundtrip_ms),
  'Самый быстрый ответ: '+seconds(performance.shortest_roundtrip_ms),
  'Самый долгий ответ: '+seconds(performance.longest_roundtrip_ms));
 const rows=(performance.observations||[]).slice().reverse();
 if(rows.length)lines.push('\nПоследние ходы:',...rows.map(x=>
  '«'+(x.action_preview||'Ход без текста')+'» — '+seconds(x.observed_roundtrip_ms)));
 return lines.join('\n');
}

/** Keyboard contract for the player action textarea (IME-safe). */
export function inputEnterIntent(event){
 if(!event||event.key!=="Enter"||event.isComposing||event.keyCode===229)return "";
 if(event.ctrlKey||event.metaKey||event.shiftKey)return "newline";
 return "send";
}
