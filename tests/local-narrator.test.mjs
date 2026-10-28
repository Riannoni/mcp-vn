import test from "node:test";
import assert from "node:assert/strict";
import {NARRATOR_SYSTEM,narratorMessages,responseQuality} from "../src/local-narrator.mjs";

const session={
 participants:[{name:"Макс Кроу",age:34},{name:"Мира",age:26}],
 transcript:[
  {role:"player",request_id:"old1",text:"Мира, что ты любишь делать после работы?"},
  {role:"narrator",request_id:"old1",
   text:"— Люблю читать у окна и гулять, когда улицы наконец становятся тихими, — сказала Мира."},
  {role:"player",request_id:"new2",text:"Ты бы хотела выпить чаю?"}
 ]
};
const game={
 hero:{name:"Макс Кроу",description:"Возраст: 34. Сдержанный авантюрист."},
 story:{summary:"Город на границе миров.",characters:[
  {name:"Мира",age:26,description:"Взрослая осторожная проводница."}
 ]},
 scene:{location:"Площадь Тиррена",sprites:[
  {name:"Макс Кроу",outfit:"default",emotion:"neutral",pose:"standing"},
  {name:"Мира",outfit:"green cloak",emotion:"calm",pose:"standing"}
 ]},
 memory:{facts:[{scope:"world",subject:"Пепельные врата",value:"Часы идут назад.",active:true}]}
};
test("prompt gives the model role-separated history and doesn't echo the new player message",()=>{
 const action={request_id:"new2",text:"Ты бы хотела выпить чаю?"};
 const messages=narratorMessages(game,session,action);
 assert.equal(messages[0].role,"system");
 assert.ok(NARRATOR_SYSTEM.includes("ЗАПРЕЩЕНО"));
 assert.ok(messages.some(x=>x.role==="assistant"));
 assert.equal(messages.at(-1).content,action.text);
 assert.equal(messages.filter(x=>x.content===action.text).length,1);
 assert.ok(!messages[1].content.includes("Часы идут назад."));
 assert.ok(messages[1].content.includes("Мира"));
 assert.ok(!messages[1].content.includes("local_action"));
});
test("local narrator receives persistent wardrobe, poses and identities",()=>{
 const withVisual={...session,visual_state:{schema:2,location:"Town",
  camera:"medium",activity:"A quiet conversation",characters:[
   {name:"Мира",outfit:"forest-green cloak",pose:"sitting",
    expression:"curious",equipment:"silver pendant",action:"holding a map"}]}};
 const data=narratorMessages(game,withVisual,{request_id:"new2",text:"Продолжай."});
 assert.match(data[1].content,/forest-green cloak/);
 assert.match(data[1].content,/silver pendant/);
 assert.match(data[1].content,/sitting/);
});
test("background mystery facts are used only when the current question concerns the mystery",()=>{
 const messages=narratorMessages(game,session,{request_id:"new2",text:"Что это за руна?"});
 assert.ok(messages[1].content.includes("Часы идут назад."));
});
test("quality gate blocks hero speech, hero actions and truncated generations",()=>{
 assert.equal(responseQuality("— Макс ответил: «Я согласен на всё». Мира улыбнулась.").reason,"hero_dialogue");
 assert.equal(responseQuality("Макс сказал, что уже принял решение. Мира кивнула.").reason,"hero_action");
 assert.equal(responseQuality("Мира повернулась к нему и, не отводя взгляда, произнесла: «Всё зависит от нас двоих»").reason,"accepted");
 assert.equal(responseQuality("Мира вздохнула и тихо начала рассказывать об утреннем тумане, но её слова").reason,"truncated");
 assert.equal(responseQuality("Мира тихо улыбнулась, когда ветер прошелестел над пустынной площадью. Она внимательно посмотрела на собеседника.").ok,true);
});
