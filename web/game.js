import {App} from "@modelcontextprotocol/ext-apps";
import "./style.css";
const $=x=>document.getElementById(x),app=new App({name:"mcp-vn",version:"0.2.0"});
let game=null,busy=false,poll=null,received=false;
const text=r=>r?.content?.find(x=>x.type==="text")?.text||"";
function unpack(r,k="game"){
 if(r?.isError)throw Error(text(r)||"Ошибка");
 const val=r?.structuredContent?.[k]||JSON.parse(text(r)||"{}")[k];
 if(val===undefined)throw Error("Нет поля "+k);
 return val;
}
const element=(tag,className,label)=>{const e=document.createElement(tag);if(className)e.className=className;if(label!==undefined)e.textContent=label;return e};
const state=s=>$("status").textContent=s;
async function call(name,args={}){return app.callServerTool({name,arguments:args})}
function draw(next){
 if(!next)return;
 if(game&&next.id===game.id&&next.version<game.version)return;
 const box=$("transcript"),nearEnd=box.scrollHeight-box.scrollTop-box.clientHeight<140;
 const changed=!game||game.id!==next.id||game.version!==next.version;
 game=next;
 $("title").textContent=game.title;
 $("hero").textContent=game.hero?.name||"";
 $("location").textContent=game.scene?.location||"Неизвестно";
 $("turn-count").textContent=game.messages.length+" сообщений";
 $("send").disabled=busy||game.awaiting_narrator;
 $("undo").disabled=busy||game.awaiting_narrator||!game.undo_stack?.length;
 state(game.awaiting_narrator?"Ждём рассказчика…":"Сохранено");
 const url=game.scene?.background_url||"";
 $("background").style.backgroundImage=url?"url("+JSON.stringify(url)+")":"";
 const sprites=$("sprites");sprites.replaceChildren();
 for(const s of game.scene?.sprites||[]){
  const shell=element("div","sprite");
  if(s.image_url){const img=element("img");img.src=s.image_url;img.alt=s.name;img.loading="lazy";shell.append(img)}
  shell.append(element("span","sprite-label",s.name));sprites.append(shell);
 }
 const video=$("scene-video");
 if(game.scene?.video_url){if(video.dataset.url!==game.scene.video_url){video.src=game.scene.video_url;video.dataset.url=game.scene.video_url}video.hidden=false}
 else{video.hidden=true;video.pause();video.removeAttribute("src");video.dataset.url=""}
 if(changed){
  box.replaceChildren();
  for(const m of game.messages){
   const row=element("article","message "+(m.role==="player"?"player":"narrator"));
   row.append(element("div","speaker",m.speaker||"Рассказчик"),element("div","body",m.text));box.append(row);
  }
  if(nearEnd||game.messages.length<=1)box.scrollTop=box.scrollHeight;
 }
 const options=$("choices");options.replaceChildren();
 if($("show-choices").checked&&!game.awaiting_narrator)
  for(const a of game.choices||[]){
   const b=element("button","option",a);b.onclick=()=>{$("action").value=a;$("action").focus()};options.append(b);
  }
}
async function refresh(){
 if(!game)return;
 const r=await call("get_game",{game_id:game.id});draw(unpack(r));
}
async function refreshJobs(){
 if(!game)return;
 try{
 const jobs=unpack(await call("list_art_jobs",{game_id:game.id}),"jobs");
 const view=$("jobs");view.replaceChildren();
 for(const j of jobs.filter(j=>j.status!=="done").slice(0,3)){
  const line=element("div","job");line.append(element("span",null,(j.kind==="video"?"Видео":"Арт")+" · "+j.style),element("span",null,j.status==="working"?"Генерируется…":j.status==="failed"?"Ошибка":"В очереди"));view.append(line);
 }
 }catch(e){console.warn("jobs",e)}
}
function beginPoll(){
 if(poll)clearInterval(poll);
 poll=setInterval(async()=>{try{await refresh();await refreshJobs()}catch(e){state(e.message)}},4000);
}
async function updateSaves(){
 try{const saves=unpack(await call("list_games"),"games").sort((a,b)=>(b.updated_at||"").localeCompare(a.updated_at||""));
 const s=$("games");s.replaceChildren();
 for(const g of saves){const e=element("option",null,g.title+" · "+g.hero);e.value=g.id;s.append(e)}
 if(game)s.value=game.id;
 }catch(e){state(e.message)}
}
async function updateStories(){
 const stories=unpack(await call("list_stories"),"stories");const s=$("stories");s.replaceChildren();
 for(const g of stories){const e=element("option",null,g.title);e.value=g.id;s.append(e)}
}
async function submit(){
 if(!game||busy||game.awaiting_narrator)return;
 const action=$("action").value.trim();if(!action)return;
 busy=true;$("send").disabled=true;
 try{
  const r=await call("submit_action",{game_id:game.id,action,expected_version:game.version});
  draw(unpack(r));$("action").value="";state("Ход принят, отправляю ChatGPT…");
  const prompt="Продолжи игру mcp-vn (сессия "+game.id+"). ВАЖНО: игрок уже отправил свободное действие через интерфейс и submit_action выполнен. Вызови get_game_context для этой сессии; затем сыграй последствия по миру и характерам, не управляй выбором игрока; вызови gm_continue с 1-6 сообщениями, локацией и необязательными вариантами. При смене локации или появлении нового NPC при необходимости вызови queue_art, style="+$("style").value+". Не вызывай submit_action повторно.";
  const resp=await app.sendMessage({role:"user",content:[{type:"text",text:prompt}]});
  if(resp?.isError)throw Error("ChatGPT не принял сообщение — попроси его продолжить эту сессию в чате.");
  beginPoll();
 }catch(e){state(e.message)}finally{busy=false;$("send").disabled=!!game?.awaiting_narrator}
}
async function requestMedia(kind){
 if(!game)return;
 const style=$("style").value;
 const names=(game.scene?.sprites||[]).map(s=>s.name).join(", ");
 const prompt=kind==="video"
  ?"Short cinematic fantasy visual novel animation. "+game.scene.location+". Atmospheric subtle motion, stable camera, soft lighting, no text."
  :"Wide atmospheric visual novel background of "+game.scene.location+". World: "+(game.story?.summary||"")+". Cinematic environment, detailed composition, no text, no interface, no watermarks.";
 try{
  await call("queue_art",{game_id:game.id,kind,style,prompt,character:""});
  state(kind==="video"?"Видеозадание создано":"Генерация фона поставлена в очередь");
  await refreshJobs();beginPoll();
 }catch(e){state(e.message)}
}
$("send").onclick=submit;
$("action").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!e.isComposing){e.preventDefault();submit()}});
$("show-choices").onchange=()=>game&&draw({...game});
$("undo").onclick=async()=>{if(!game)return;try{draw(unpack(await call("undo_last_turn",{game_id:game.id})));await updateSaves()}catch(e){state(e.message)}};
$("new-game").onclick=async()=>{
 try{
  const r=await call("start_game",{story_id:$("stories").value||"ash-gate",hero_name:game?.hero?.name||"Макс Кроу",hero_description:game?.hero?.description||""});
  game=null;draw(unpack(r));await updateSaves();
 }catch(e){state(e.message)}
};
$("games").onchange=async e=>{try{const r=await call("get_game",{game_id:e.target.value});game=null;draw(unpack(r));await refreshJobs()}catch(err){state(err.message)}};
$("fullscreen").onclick=async()=>{try{await app.requestDisplayMode({mode:"fullscreen"})}catch{state("Полный экран недоступен")}};
$("art").onclick=()=>requestMedia("background");
$("video").onclick=()=>requestMedia("video");
app.ontoolresult=r=>{try{const d=unpack(r);if(!game||d.id===game.id)draw(d)}catch{}};
(async()=>{
 try{
  await app.connect();
  await updateStories();
  if(!game){const saves=unpack(await call("list_games"),"games");
  const latest=[...saves].sort((a,b)=>(b.updated_at||"").localeCompare(a.updated_at||""))[0];
  const r=latest?await call("get_game",{game_id:latest.id}):await call("start_game",{story_id:"ash-gate",hero_name:"Макс Кроу"});
  draw(unpack(r));}
  await updateSaves();await refreshJobs();beginPoll();
 }catch(e){state("Ошибка подключения: "+e.message)}
})();
