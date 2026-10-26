import fs from "node:fs/promises";
import path from "node:path";
import { randomUUID } from "node:crypto";
const root=process.env.VN_DATA_DIR||"/data";
const demo={
  id:"ash-gate",title:"Пепельные врата",author:"mcp-vn",source:"original",rights_confirmed:true,
  summary:"Тиррен — город на границе миров, где исчезают воспоминания.",
  lore:"В Тиррене живут люди и магические существа. Время иногда движется вспять. Любое решение меняет мир.",
  opening:"Туман опускается на рыночную площадь. Из древних ворот раздаётся голос: «Назови своё имя, странник!»",
  scene:{location:"Площадь Тиррена",background_url:"",sprites:[]},
  characters:[{id:"mira",name:"Мира",age:26,description:"Взрослая проводница в зелёном плаще, наблюдательна и осторожна."}],
  choices:["Расспросить голос","Войти в ворота","Осмотреть площадь"]
};
const id=x=>{if(typeof x!=="string"||!/^[a-zA-Z0-9_-]{1,100}$/.test(x))throw Error("Invalid id");return x};
const txt=(x,n=10000)=>{if(typeof x!=="string")throw Error("Invalid text");return x.trim().slice(0,n)};
const urls=x=>{if(!x)return "";const u=new URL(x);if(u.protocol!=="https:"||u.username||u.password)throw Error("HTTPS URL required");return u.href};
const file=(k,x)=>path.join(root,k,id(x)+".json");
async function save(k,x,data){
 const f=file(k,x),t=f+"."+randomUUID()+".tmp";
 await fs.mkdir(path.dirname(f),{recursive:true});
 await fs.writeFile(t,JSON.stringify(data),{mode:0o600});
 await fs.rename(t,f);
}
async function load(k,x){return JSON.parse(await fs.readFile(file(k,x),"utf8"))}
let lock=Promise.resolve();
const serialize=fn=>{const v=lock.then(fn);lock=v.catch(()=>{});return v};
export async function init(){
 for(const x of ["stories","games","jobs","assets"]) await fs.mkdir(path.join(root,x),{recursive:true});
 try{await fs.access(file("stories","ash-gate"))}catch{await save("stories","ash-gate",demo)}
}
export async function list(kind){
 await init();const dir=kind==="stories"?"stories":"games";
 const f=(await fs.readdir(path.join(root,dir))).filter(x=>x.endsWith(".json"));
 const all=await Promise.all(f.map(x=>load(dir,x.slice(0,-5))));
 return all.map(x=>({id:x.id,title:x.title,summary:x.summary||"",hero:x.hero?.name||"",updated_at:x.updated_at||""}));
}
export async function gameGet(gameId){await init();return load("games",gameId)}
export async function gameStart(storyId="ash-gate",hero="Макс Кроу",description=""){
 return serialize(async()=>{await init();const s=await load("stories",storyId),now=new Date().toISOString(),gid=randomUUID();
 const game={id:gid,story_id:s.id,title:s.title,hero:{name:txt(hero,100),description:txt(description,5000)},
   story:{summary:s.summary,lore:s.lore,characters:s.characters||[]},scene:s.scene||{location:"Начало",background_url:"",sprites:[]},
   messages:[{id:randomUUID(),role:"narrator",speaker:"Рассказчик",text:s.opening,at:now}],
   choices:s.choices||[],inventory:[],relationships:{},flags:{},version:1,awaiting_narrator:false,
   undo_stack:[],created_at:now,updated_at:now};
 await save("games",gid,game);return game});
}
export async function gameAction(gameId,action,version){
 return serialize(async()=>{const g=await gameGet(gameId);
 if(g.awaiting_narrator)throw Error("Previous turn is awaiting narration");
 if(version!==undefined&&version!==g.version)throw Error("Version conflict. Refresh.");
 const input=txt(action,5000);if(!input)throw Error("Empty action");
 g.undo_stack.push({...structuredClone(g),undo_stack:[]});g.undo_stack=g.undo_stack.slice(-10);
 g.messages.push({id:randomUUID(),role:"player",speaker:g.hero.name,text:input,at:new Date().toISOString()});
 g.choices=[];g.awaiting_narrator=true;g.version++;g.updated_at=new Date().toISOString();
 await save("games",g.id,g);return g});
}
export async function gameNarrate({game_id,messages,scene={},choices=[],inventory_add=[],flags={},relationships={}}){
 return serialize(async()=>{const g=await gameGet(game_id);
 if(!g.awaiting_narrator)throw Error("No player action pending");
 if(!Array.isArray(messages)||messages.length<1||messages.length>12)throw Error("Narration requires 1-12 messages");
 for(const m of messages)g.messages.push({id:randomUUID(),role:"narrator",speaker:txt(m.speaker||"Рассказчик",100),text:txt(m.text,10000),at:new Date().toISOString()});
 if(scene.location!==undefined)g.scene.location=txt(scene.location,180);
 if(scene.background_url!==undefined)g.scene.background_url=urls(scene.background_url);
 if(scene.sprites!==undefined){
 if(!Array.isArray(scene.sprites)||scene.sprites.length>8)throw Error("Too many sprites");
 g.scene.sprites=scene.sprites.map(s=>({name:txt(s.name,100),image_url:urls(s.image_url||""),emotion:txt(s.emotion||"neutral",60)}));
 }
 g.choices=(choices||[]).slice(0,6).map(x=>txt(x,200));
 for(const x of inventory_add||[]){const v=txt(x,180);if(v&&!g.inventory.includes(v))g.inventory.push(v)}
 for(const [k,v] of Object.entries(flags||{})){if(/^[\w-]{1,80}$/.test(k)&&["number","boolean","string"].includes(typeof v))g.flags[k]=v}
 for(const [k,v] of Object.entries(relationships||{})){if(/^[\w-]{1,80}$/.test(k)&&Number.isFinite(v))g.relationships[k]=v}
 g.awaiting_narrator=false;g.version++;g.updated_at=new Date().toISOString();
 await save("games",g.id,g);return g});
}
export async function gameUndo(gameId){
 return serialize(async()=>{const g=await gameGet(gameId);if(g.awaiting_narrator)throw Error("Narration pending");
 const before=g.undo_stack.pop();if(!before)throw Error("Nothing to undo");
 before.undo_stack=g.undo_stack;before.version=g.version+1;before.updated_at=new Date().toISOString();
 await save("games",gameId,before);return before});
}
export async function attachImage(gameId,{kind="background",character="",url}){
 return serialize(async()=>{const g=await gameGet(gameId);
 if(kind==="background"||kind==="scene")g.scene.background_url=urls(url);
 else if(kind==="sprite"){const name=txt(character,100);if(!name)throw Error("Character required");
 g.scene.sprites=(g.scene.sprites||[]).filter(s=>s.name!==name);
 g.scene.sprites.push({name,image_url:urls(url),emotion:"neutral"})}
 else if(kind!=="video")throw Error("Unknown media kind");
 if(kind==="video")g.scene.video_url=urls(url);
 g.version++;g.updated_at=new Date().toISOString();await save("games",gameId,g);return g});
}
export async function importStory(doc){
 return serialize(async()=>{await init();const x=typeof doc==="string"?JSON.parse(doc):doc;
 if(!x||x.rights_confirmed!==true||!["original","user-owned","licensed"].includes(x.source))throw Error("Reuse rights must be confirmed");
 for(const k of ["title","opening","author"])if(!x[k])throw Error("Missing "+k);
 if((x.characters||[]).some(c=>c.age!==undefined&&Number(c.age)<18||c.age_group==="minor"))throw Error("Minor characters are not permitted in this game library");
 const sid=randomUUID(),s={id:sid,title:txt(x.title,180),opening:txt(x.opening),author:txt(x.author,100),source:x.source,rights_confirmed:true,
 summary:txt(x.summary||"",2000),lore:txt(x.lore||"",25000),scene:x.scene||{location:"Начало",background_url:"",sprites:[]},
 characters:(x.characters||[]).slice(0,60),choices:(x.choices||[]).slice(0,6)};
 await save("stories",sid,s);return{id:sid,title:s.title}});
}
export const dataRoot=root;
