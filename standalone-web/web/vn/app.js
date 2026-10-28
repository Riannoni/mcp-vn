import {COMMANDS,matchingCommands,latencyText} from "./commands.js";
const $=id=>document.getElementById(id);
let currentGame=null,models=[],busy=false,oauthTimer=null,currentSave="";
let fit=true,activeModel="local-cydonia-24b";
let currentLocalEpisode=null,localPollBusy=false;
let visualPollActive=false,visualPollBusy=false,lastVisualGame="",visualPollOnce=false;
let lastVisualJobs=[],stageView="auto",castVisible=true,lastTurnWallSec=null;
const EFFORT_NAMES={auto:"Авто (настройка модели)",low:"Низкая · быстро",
 medium:"Средняя · баланс",high:"Высокая · глубже",
 xhigh:"Очень высокая · медленно",max:"Максимальная · самый долгий ответ"};
function selectedEffort(){return $("reasoning-panel").hidden?"auto":($("reasoning").value||"auto")}
function updateReasoning(){
 const item=models.find(x=>x.id===$("narrator").value);
 const allowed=Array.isArray(item?.reasoning_levels)?item.reasoning_levels:[];
 const panel=$("reasoning-panel");
 panel.hidden=allowed.length===0;
 const select=$("reasoning");
 select.replaceChildren();
 for(const level of allowed)select.add(new Option(EFFORT_NAMES[level]||level,level));
 let stored="auto";
 try{stored=localStorage.getItem("vn-web-effort:"+item?.id)||"auto"}catch(_){}
 select.value=allowed.includes(stored)?stored:"auto";
 panel.title=item?.provider==="grok"?
   "Grok 4.7: auto обычно соответствует высокой глубине; на других версиях уровни могут отличаться.":
   "Поддержка конкретных уровней зависит от GPT-модели. Более глубокий анализ требует больше токенов.";
}
async function pollVisualJobs(){
 if(visualPollBusy||busy||!currentGame||currentGame.local_scene?.mode==="local")return;
 const id=currentGame.id;
 visualPollBusy=true;
 try{
  const result=await api("/api/vn/visual-jobs?id="+encodeURIComponent(id));
  if(currentGame?.id!==id)return;
  const jobs=result.jobs||[];
  lastVisualJobs=jobs;

  const active=jobs.filter(x=>x.status==="queued"||x.status==="working");
  if(active.length){
   visualPollActive=true;
   $("stage-caption").textContent="Генерация изображения: "+active.map(j=>j.kind+
     (j.character?" · "+j.character:"")).join(", ");
  }
  if(visualPollActive||visualPollOnce){
   const response=await api("/api/vn/game?id="+encodeURIComponent(id));
   if(currentGame?.id!==id)return;
   currentGame=response.game;
   renderScene(currentGame);
   if(!active.length){
    visualPollActive=false;visualPollOnce=false;
    const error=jobs.find(j=>j.status==="failed"&&
     (j.kind==="background"||j.kind==="sprite"));
    const warn=$("scene-warning");
    if(error&&(!currentGame.scene?.background_url||
      currentGame.scene?.background_dirty||
      (currentGame.scene?.sprites||[]).some(x=>x.visual_dirty))){
      warn.hidden=false;
      warn.textContent="Не удалось создать иллюстрацию: "+(error.error||"ошибка генерации");
      $("visual-retry").hidden=false;
    }else{warn.hidden=true;$("visual-retry").hidden=true}
    // Once a missing location background completes, schedule the character
    // layers against its accepted final URL, never against a stale image.
    if(!currentGame.awaiting_narrator)
      await scheduleMissingVisuals(currentGame).catch(e=>
       console.warn("next visual stage:",e.message));
   }
  }
 }catch(e){console.warn("visual jobs:",e.message)}
 finally{visualPollBusy=false}
}
async function scheduleMissingVisuals(g,{retry=false}={}){
 if(!g||g.local_scene?.mode==="local")return;
 const scene=g.scene||{};
 const missing=!scene.background_url||!!scene.background_dirty||
   !(scene.sprites||[]).length||
   (scene.sprites||[]).some(x=>!x.image_url||x.visual_dirty);
 if(!missing&&!retry)return;
 const result=await api("/api/vn/visual-refresh",{game_id:g.id,retry});
 if(result.visual?.scheduled?.length){
  visualPollActive=true;visualPollOnce=true;
  $("stage-caption").textContent="Иллюстрация поставлена в очередь · "+
   result.visual.scheduled.map(x=>x.kind).join(", ");
 }
 if(result.visual?.failed?.length){
  const warn=$("scene-warning");
  warn.hidden=false;warn.textContent=result.visual.failed[0].error;
 }
}

async function api(path,data=undefined){
 const opts={credentials:"same-origin",headers:{"Accept":"application/json"}};
 if(data!==undefined){opts.method="POST";opts.headers["Content-Type"]="application/json";opts.body=JSON.stringify(data);}
 const response=await fetch(path,opts);
 let result={};try{result=await response.json()}catch(_){}
 if(!response.ok)throw Error(result.error||"HTTP "+response.status);
 return result;
}
function showToast(value){
 const el=$("notification");el.textContent=value;el.hidden=false;
 setTimeout(()=>{el.hidden=true},5200);
}
function label(tag,value,cls=""){
 const el=document.createElement(tag);el.textContent=value||"";el.className=cls;return el;
}
function status(message){
 $("service-state").textContent=message;
}
function showLogin(){
 $("login").hidden=false;$("app").hidden=true;
}
function showApp(){
 $("login").hidden=true;$("app").hidden=false;
}
async function loadModels(){
 const catalog=await api("/api/vn/models");
 models=catalog.models||[];
 const select=$("narrator"),old=select.value||activeModel;
 select.replaceChildren();
 const groups={local:"Локальные · ROCm",openai:"ChatGPT / Codex · OAuth",grok:"Grok / xAI · OAuth"};
 for(const type of ["local","openai","grok"]){
  const opt=document.createElement("optgroup");opt.label=groups[type];
  const entries=models.filter(x=>x.provider===type);
  if(!entries.length){
   const unavailable=new Option(type==="local"?"Недоступны":type==="openai"?"Требуется вход ChatGPT":"Требуется вход Grok","");
   unavailable.disabled=true;opt.append(unavailable);
  }else{
   for(const m of entries){
    const name=m.id==="local-qwen-9b"?"Qwen 9B · локальная":m.id==="local-cydonia-24b"?"Cydonia 24B · локальная":m.name;
    opt.append(new Option(name,m.id));
   }
  }
  select.append(opt);
 }
 const available=models.map(x=>x.id);
 select.value=available.includes(old)?old:available.includes("local-cydonia-24b")?"local-cydonia-24b":(available[0]||"");
 activeModel=select.value;
 updateReasoning();
 $("provider-badge").textContent=activeModel.startsWith("local")?"На этом ПК":activeModel.startsWith("grok")?"Grok":"ChatGPT";
 status(catalog.connected?"Готово":"Модели недоступны");
 showProviderStates();
}
function renderMessages(items){
 const view=$("transcript");view.replaceChildren();
 for(const m of (items||[]).slice(-90)){
  const node=label("div","","message"+(m.role==="player"?" player":""));
  node.append(label("small",m.speaker||(m.role==="player"?"Игрок":"Рассказчик")));
  node.append(label("div",m.text||""));
  view.append(node);
 }
 view.scrollTop=view.scrollHeight;
}
function renderScene(g){
 const stage=$("stage"),bg=$("scene-background"),cg=$("scene-cg"),sprites=$("scene-sprites");
 const scene=g.scene||{},url=scene.background_url||"";
 bg.style.backgroundImage=url?"url("+JSON.stringify(url)+")":"none";
 const availableCG=!!scene.cg_url&&!scene.cg_dirty;
 const isCG=availableCG&&(stageView==="cg"||
   (stageView==="auto"&&scene.mode==="cg"));
 const onlyBackground=stageView==="background";
 cg.hidden=!isCG;
 if(isCG&&cg.src!==scene.cg_url)cg.src=scene.cg_url;
 sprites.hidden=isCG||onlyBackground||!castVisible;
 sprites.replaceChildren();
 if(!isCG){
  for(const sp of (scene.sprites||[]).slice(0,5)){
   if(!sp.image_url)continue;
   const image=document.createElement("img");image.src=sp.image_url;
   image.alt=sp.name||"Персонаж";image.loading="lazy";image.decoding="async";
   sprites.append(image);
  }
 }
 stage.classList.toggle("fill",!fit);
 $("scene-location").textContent=scene.location||"Неизвестная локация";
 $("scene-style").textContent=g.art_style||"";
 $("stage-caption").textContent=isCG?"Иллюстрация сцены":
   onlyBackground?"Фон локации":
   (scene.sprites||[]).length?"Фон и персонажи":"Фон локации";
 const mode=$("view-layers"),background=$("view-background"),people=$("toggle-characters");
 mode.disabled=!availableCG;
 mode.textContent=isCG?"◈ Показать слои":"◈ Показать CG";
 mode.classList.toggle("is-active",isCG);
 background.classList.toggle("is-active",onlyBackground);
 people.classList.toggle("is-active",!sprites.hidden&&!isCG);
 const canCompose=!g.awaiting_narrator&&g.local_scene?.mode!=="local"&&
   !!scene.background_url&&!scene.background_dirty&&
   !!(scene.sprites||[]).length&&!(scene.sprites||[]).some(x=>x.visual_dirty);
 $("manual-cg").disabled=!canCompose;

}
function renderGame(g){
 currentGame=g;
 $("story-name").textContent=g.title||g.story?.title||"История";
 renderMessages(g.messages);
 renderScene(g);
 $("turn-status").textContent=g.awaiting_narrator?"Ожидается рассказчик":lastTurnWallSec===null?"Готово":"Ответ за "+lastTurnWallSec.toLocaleString("ru-RU")+" с";
 const pending=!!g.awaiting_narrator;
 const local=g.local_scene?.mode==="local";
 $("send").disabled=busy||pending||(local&&!!currentLocalEpisode?.pending);
 $("resume").hidden=!pending||local;
 $("resume").disabled=busy;
 $("player-action").disabled=busy||pending||(local&&!!currentLocalEpisode?.pending);
 $("state-message").hidden=!pending;
 if(pending)$("state-message").textContent="Действие сохранено. Можно повторить незавершённый ответ.";
 $("local-exit").hidden=!local;
 $("save").disabled=busy;$("refresh").disabled=busy;
 $("narrator").disabled=busy;$("reasoning").disabled=busy;
 $("open-commands").disabled=busy||pending||(local&&!!currentLocalEpisode?.pending);

}
async function refreshLocalEpisode(){
 if(!currentGame||currentGame.local_scene?.mode!=="local")return;
 if(localPollBusy)return;
 localPollBusy=true;
 const id=currentGame.id;
 try{
  const ep=(await api("/api/vn/local-status?id="+encodeURIComponent(id))).local_episode;
  if(currentGame?.id!==id)return;
  currentLocalEpisode=ep;
  currentGame.version=ep.version;
  renderMessages(ep.transcript||[]);
  const view=ep.visual_display||{};
  if(view.mode==="cg"&&view.cg_url){
   const cg=$("scene-cg");cg.hidden=false;
   if(cg.src!==view.cg_url)cg.src=view.cg_url;
   $("scene-sprites").hidden=true;
   $("stage-caption").textContent="Иллюстрация сцены";
  }else if(view.mode==="layers"){
   $("scene-cg").hidden=true;
   const sprites=$("scene-sprites");
   sprites.hidden=false;
   sprites.replaceChildren();
   const canonical=currentGame.scene?.sprites||[];
   for(const actor of ep.visual_state?.characters||[]){
    const url=view.sprite_urls?.[actor.name]||canonical.find(x=>x.name===actor.name)?.image_url;
    if(!url)continue;
    const img=document.createElement("img");img.src=url;img.alt=actor.name;
    img.loading="lazy";sprites.append(img);
   }
  }
  $("turn-status").textContent=ep.pending?"Локальный рассказчик пишет…":
   ep.visual_pending?"Текст готов · строится изображение":"Локальная сцена готова";
  $("send").disabled=busy||!!ep.pending;
  $("open-commands").disabled=busy||!!ep.pending;
  $("player-action").disabled=busy||!!ep.pending;
  if(ep.last_error&&!ep.pending)showToast("Локальный рассказчик: "+ep.last_error);

 }catch(e){$("turn-status").textContent="Ошибка локальной сцены";console.warn(e.message)}
 finally{localPollBusy=false}
}
async function loadGame(id){
 if(!id)return;
 currentSave=id;
 const d=await api("/api/vn/game?id="+encodeURIComponent(id));
 if(currentSave!==id)return;
 closeInfo();closeCommandMenu();
 currentLocalEpisode=null;
 visualPollActive=false;visualPollOnce=true;lastVisualGame=id;
 lastVisualJobs=[];stageView="auto";castVisible=true;lastTurnWallSec=null;
 renderGame(d.game);
 if(d.game.local_scene?.mode==="local")await refreshLocalEpisode();
 else {
  await scheduleMissingVisuals(d.game).catch(e=>console.warn("visual schedule:",e.message));
  await pollVisualJobs();
 }
 try{localStorage.setItem("vn-web-last-save",id)}catch(_){}
}
async function loadGames(){
 const response=await api("/api/vn/games");
 const items=response.games||[];
 const select=$("save");select.replaceChildren();
 if(!items.length){select.add(new Option("Нет сохранений",""));currentGame=null;return;}
 for(const g of items)select.add(new Option((g.title||g.story_title||"Без названия")+" · "+(g.hero||g.hero_name||"")+" · "+(g.updated_at||"").slice(0,10),g.id));
 let last="";try{last=localStorage.getItem("vn-web-last-save")||""}catch(_){}
 const id=items.some(x=>x.id===currentSave)?currentSave:items.some(x=>x.id===last)?last:items[0].id;
 select.value=id;await loadGame(id);
}
async function refresh(){
 try{
  await loadModels();
  if(currentGame)await loadGame(currentGame.id);
  else await loadGames();
 }catch(e){showToast(e.message)}
}
async function runTurn(resume=false){
 if(busy||!currentGame)return;
 const action=$("player-action").value.trim();
 if(!resume&&!action){showToast("Введи действие или выбери команду");return}
 const name=!resume&&action.startsWith("/")?action.split(/\s/)[0].slice(1).toLowerCase():"";
 if(name&&!COMMANDS.some(x=>x.name===name)){showToast("Неизвестная команда. Выбери команду из меню «/».");return}
 const prompts={undo:"Отменить последний ход? Его текст и изменения будут удалены.",
  video:"Создать видео из готового кадра сцены? Генерация может занять несколько минут."};
 if(prompts[name]&&!confirm(prompts[name]))return;
 const id=currentGame.id;
 closeCommandMenu();busy=true;renderGame(currentGame);
 $("turn-status").textContent=name==="undo"?"Отменяем ход…":name==="video"?"Готовим видео…":name==="ooc"||name==="recap"?"Рассказчик отвечает…":"Рассказчик пишет…";
 const start=performance.now();
 try{
  const body={game_id:id,model:activeModel,reasoning_effort:selectedEffort()};
  if(!resume){body.action=action;body.expected_version=currentGame.version;}
  if(prompts[name])body.confirmed=true;
  const local=currentGame.local_scene?.mode==="local";
  const result=await api(name?"/api/vn/command":resume?"/api/vn/resume":local?"/api/vn/local-turn":"/api/vn/turn",body);
  if(currentGame?.id!==id)return;
  $("player-action").value="";
  if(result.game)renderGame(result.game);
  if(result.type==="ooc"||result.type==="recap"){
   displayInfo(result.type==="ooc"?"Вне сюжета":"Краткий пересказ",result.text);
  }else if(result.type==="video"){
   showVideoJob(id,result.job.id);
  }else if(result.type==="local"||(local&&!name)){
   await refreshLocalEpisode();
  }else{
   lastTurnWallSec=Number(((performance.now()-start)/1000).toFixed(1));
   if(result.type==="undo"){stageView="auto";castVisible=true;lastTurnWallSec=null;}
   if(result.visual?.scheduled?.length){visualPollActive=true;visualPollOnce=true;}
   if(result.type==="undo"&&!local)await scheduleMissingVisuals(currentGame);
  }
 }catch(e){
  showToast(e.message);
  try{if(currentGame?.id===id)await loadGame(id)}catch(_){}
 }finally{
  busy=false;
  if(currentGame?.id===id){renderGame(currentGame);if(currentGame.local_scene?.mode==="local")await refreshLocalEpisode();}
 }
}
let commandItems=[],commandIndex=0,commandManual=false,videoTimer=null,infoEpoch=0;
function closeCommandMenu(){
 $("command-menu").hidden=true;commandManual=false;
 $("player-action").setAttribute("aria-expanded","false");
 $("player-action").removeAttribute("aria-activedescendant");
 $("open-commands").setAttribute("aria-expanded","false");
}
function selectCommand(item){
 $("player-action").value="/"+item.name+(item.args?" ":"");
 closeCommandMenu();$("player-action").focus();
}
function paintCommandMenu(){
 const menu=$("command-menu");menu.replaceChildren();
 for(const [index,item] of commandItems.entries()){
  const button=document.createElement("button");button.type="button";
  button.className="command-option";button.id="command-option-"+item.name;
  button.setAttribute("role","option");button.setAttribute("aria-selected",String(index===commandIndex));
  button.append(label("span",item.icon,"command-icon"));
  const words=label("span","","command-words");
  const title=label("span","","command-title");title.append(label("strong","/"+item.name));
  if(item.args)title.append(label("span",item.args+(item.optional?" (необязательно)":""),"command-args"));
  words.append(title,label("span",item.description,"command-description"));button.append(words);
  button.addEventListener("click",()=>selectCommand(item));menu.append(button);
 }
 menu.hidden=!commandItems.length;
 $("player-action").setAttribute("aria-expanded",String(!menu.hidden));
 $("open-commands").setAttribute("aria-expanded",String(!menu.hidden));
 if(commandItems.length){
  $("player-action").setAttribute("aria-activedescendant","command-option-"+commandItems[commandIndex].name);
  menu.children[commandIndex].scrollIntoView({block:"nearest"});
 }
}
function updateCommandMenu(){
 commandItems=matchingCommands($("player-action").value,commandManual);
 commandIndex=0;paintCommandMenu();
}
function closeInfo(){
 infoEpoch++;
 $("info-modal").hidden=true;$("info-video").pause();
 clearTimeout(videoTimer);videoTimer=null;
}
async function showVideoJob(gameId,jobId){
 const epoch=displayInfo("Видео сцены","Видео создаётся. Можно закрыть это окно и продолжить историю.");
 const current=()=>infoEpoch===epoch&&!$("info-modal").hidden&&currentGame?.id===gameId;
 async function poll(){
  if(!current())return;
  try{
   const response=await api("/api/vn/visual-jobs?id="+encodeURIComponent(gameId));
   if(!current())return;
   const job=(response.jobs||[]).find(x=>x.id===jobId);
   if(job?.status==="done"&&job.asset_url){
    $("info-body").textContent="Видео готово.";
    $("info-video").src=job.asset_url;$("info-video").hidden=false;return;
   }
   if(job?.status==="failed"){$("info-body").textContent="Не удалось создать видео. Попробуй /video ещё раз.";return;}
   videoTimer=setTimeout(poll,4000);
  }catch(e){if(current())$("info-body").textContent=e.message;}
 }
 await poll();
}
function displayInfo(title,value,asGallery=false){
 infoEpoch++;
 clearTimeout(videoTimer);videoTimer=null;$("info-video").pause();$("info-video").hidden=true;$("info-video").removeAttribute("src");
 $("info-title").textContent=title;
 $("info-modal").hidden=false;
 $("info-gallery").hidden=!asGallery;
 $("info-body").hidden=asGallery;
 $("info-gallery").replaceChildren();
 if(!asGallery)$("info-body").textContent=value||"Пока нет данных.";
 return infoEpoch;
}
async function openHistory(){
 const id=currentGame?.id;
 const messages=currentGame?.local_scene?.mode==="local"?
  currentLocalEpisode?.transcript:currentGame?.messages;
 const text=(messages||[]).map(m=>
  (m.speaker||m.role||"Рассказчик")+":\n"+(m.text||"")).join("\n\n────────────\n\n");
 const epoch=displayInfo("История",text);
 if(!id)return;
 try{
  const response=await api("/api/vn/visual-jobs?id="+encodeURIComponent(id));
  if(infoEpoch!==epoch||currentGame?.id!==id)return;
  const videos=(response.jobs||[]).filter(x=>x.kind==="video").slice(0,5);
  if(videos.length){
   const panel=$("info-gallery");panel.hidden=false;
   for(const job of videos){
    const button=label("button",job.status==="done"?"▶ Видео сцены":job.status==="failed"?"Видео: не удалось создать":"Видео создаётся…","subtle");
    button.type="button";button.addEventListener("click",()=>showVideoJob(id,job.id));panel.append(button);
   }
  }
 }catch(_){}
}
async function openLatency(){
 if(!currentGame)return;
 if(currentGame.local_scene?.mode==="local"){
  displayInfo("Время ответа",latencyText(localLatency()));return;
 }
 const id=currentGame.id,epoch=displayInfo("Время ответа","Загрузка…");
 try{
  const result=await api("/api/vn/performance?id="+encodeURIComponent(id));
  if(infoEpoch===epoch&&currentGame?.id===id)$("info-body").textContent=latencyText(result.performance,lastTurnWallSec);
 }catch(e){if(infoEpoch===epoch)$("info-body").textContent=e.message;}
}
function openLooks(){
 if(!currentGame)return;
 displayInfo("Канонические образы персонажей","",true);
 const panel=$("info-gallery");
 const visible=currentGame.scene?.sprites||[];
 const identities=currentGame.identities||{};
 const names=new Set([...visible.map(x=>x.name),...Object.keys(identities)]);
 if(!names.size){panel.append(label("div","В этом сохранении пока нет закреплённых персонажей."));return}
 for(const name of names){
  const sprite=visible.find(x=>x.name===name);
  const face=identities[name]||{};
  const url=sprite?.image_url||face.base_sprite_url||face.face_url||"";
  const figure=document.createElement("figure");
  if(url){
   const image=document.createElement("img");
   image.src=url;image.alt=name;image.loading="lazy";
   image.onerror=()=>{image.replaceWith(label("div","Изображение недоступно"))};
   figure.append(image);
  }else figure.append(label("div","Образ ожидает генерации."));
  const caption=document.createElement("figcaption");
  caption.textContent=name+" · "+(sprite?.outfit||"базовый образ")+
   " · "+(sprite?.emotion||"нейтральная эмоция");
  figure.append(caption);panel.append(figure);
 }
}
function localLatency(){
 const rows=currentLocalEpisode?.metrics||[],values=rows.map(x=>x.overall_ms).filter(Number.isFinite).sort((a,b)=>a-b);
 const n=values.length;
 return {count:n,median_roundtrip_ms:n?(values[Math.floor((n-1)/2)]+values[Math.floor(n/2)])/2:null,
  shortest_roundtrip_ms:values[0],longest_roundtrip_ms:values.at(-1),
  observations:rows.map(x=>({action_preview:(currentLocalEpisode.transcript||[]).find(m=>m.request_id===x.request_id&&m.role==="player")?.text,
   observed_roundtrip_ms:x.overall_ms}))};
}
async function exitLocalStory(){
 if(!currentGame||busy)return;
 if(!confirm("Завершить локальный эпизод и вернуться к основному сюжету?"))return;
 busy=true;
 try{
  const current=(await api("/api/vn/game?id="+encodeURIComponent(currentGame.id))).game;
  await api("/api/vn/local-exit",{
   game_id:current.id,expected_version:current.version});
  await loadGame(current.id);showToast("Локальный эпизод завершён");
 }catch(e){showToast(e.message)}
 finally{busy=false;if(currentGame)renderGame(currentGame)}
}
async function requestCG(){
 if(!currentGame||busy)return;
 if(!confirm("Собрать CG из подтверждённых фона и спрайтов? Графика будет обновляться асинхронно."))return;
 try{
  const result=await api("/api/vn/visual-cg",{
   game_id:currentGame.id,expected_version:currentGame.version});
  visualPollActive=true;visualPollOnce=true;
  showToast("Иллюстрация создаётся");
  await pollVisualJobs();
 }catch(e){showToast(e.message)}
}
function showSceneVariant(next){
 stageView=next;renderScene(currentGame);
}
function oauthProviderName(id){
 return id==="openai"?"ChatGPT / Codex":id==="grok"?"Grok / xAI":"";
}
let oauthActiveProvider=null;
let oauthPolling=false;
function showProviderStates(){
 for(const provider of ["openai","grok"]){
  const connected=models.some(x=>x.provider===provider);
  const active=oauthActiveProvider===provider;
  $("oauth-"+provider+"-state").textContent=connected?"Подключено · проверь модели":
    active?"Идёт авторизация…":"Не подключено";
  $("auth-"+provider).textContent=active?"Продолжить":"Войти";
 }
}
async function openProviders(){
 $("providers-modal").hidden=false;
 try{await pollOAuth()}catch(e){showToast(e.message)}
}
function closeProviders(){ $("providers-modal").hidden=true; }
async function startOAuth(provider){
 if(oauthActiveProvider&&oauthActiveProvider!==provider){
  if(!confirm("Отменить незавершённый вход "+oauthProviderName(oauthActiveProvider)+
              " и начать "+oauthProviderName(provider)+"?"))return;
 }
 $("oauth-panel").hidden=false;
 $("oauth-provider-name").textContent="Подключение "+oauthProviderName(provider);
 $("oauth-state-message").textContent="Запускаем вход через код устройства…";
 $("oauth-device-fields").hidden=true;
 try{
  const result=await api("/api/vn/oauth/start",{provider});
  if(result.provider!==provider)throw Error("Прокси запустил не тот провайдер");
  oauthActiveProvider=provider;
  clearInterval(oauthTimer);
  oauthTimer=setInterval(()=>pollOAuth().catch(e=>showToast(e.message)),1750);
  await pollOAuth();
 }catch(e){
  $("oauth-state-message").textContent="Ошибка запуска: "+e.message;
  showToast(e.message);
 }
}
async function pollOAuth(){
 if(oauthPolling)return;
 oauthPolling=true;
 try{
  const data=await api("/api/vn/oauth/status");
  const provider=data.provider;
  const active=!!data.active;
  oauthActiveProvider=active?provider:null;
  if(!provider){
   $("oauth-panel").hidden=true;
   showProviderStates();
   return;
  }
  $("oauth-panel").hidden=false;
  $("oauth-provider-name").textContent="Подключение "+oauthProviderName(provider);
  const fields=$("oauth-device-fields"),link=$("oauth-device-url");
  const url=String(data.url||"");
  const code=String(data.device_code||"");
  // Backend returns a HTTPS URL restricted to the provider's sign-in domain.
  const validUrl=url.startsWith("https://")&&!url.includes("@");
  const show=active&&!!code&&validUrl;
  fields.hidden=!show;
  link.href=show?url:"#";
  $("oauth-device-code").textContent=show?code:"";
  $("oauth-state-message").textContent=data.message||"Ожидаем вход…";
  $("oauth-cancel").disabled=!active;
  if(!active){
   clearInterval(oauthTimer);oauthTimer=null;
   await loadModels();
   if(data.phase==="success"){
    const hasModels=models.some(x=>x.provider===provider);
    showToast(hasModels?"Вход "+oauthProviderName(provider)+" выполнен. Модели доступны.":
      "Вход завершён, но модели ещё не появились. Проверь лимиты тарифа.");
   }
  }
  showProviderStates();
 }finally{oauthPolling=false}
}
async function cancelOAuth(){
 try{
  const result=await api("/api/vn/oauth/cancel",{});
  clearInterval(oauthTimer);oauthTimer=null;
  oauthActiveProvider=null;
  await pollOAuth();
  showToast("Вход отменён");
 }catch(e){showToast(e.message)}
}
async function copyOAuthCode(){
 const value=$("oauth-device-code").textContent.trim();
 if(!value)return;
 try{
  if(navigator.clipboard?.writeText){
   await navigator.clipboard.writeText(value);
  }else{
   const temp=document.createElement("textarea");temp.value=value;
   temp.style.position="fixed";temp.style.opacity="0";
   document.body.append(temp);temp.select();
   if(!document.execCommand("copy"))throw Error("Clipboard is blocked");
   temp.remove();
  }
  showToast("Код скопирован");
 }catch(e){showToast("Выдели код мышью и скопируй вручную")}
}
async function startup(){
 try{
  const auth=await api("/api/session");
  if(!auth.authenticated){showLogin();return}
  showApp();
  await Promise.all([loadModels(),loadGames()]);
  setInterval(async()=>{
   if($("app").hidden||busy||!currentGame)return;
   if(currentGame.local_scene?.mode==="local")await refreshLocalEpisode();
   else if(visualPollActive||visualPollOnce)
    await pollVisualJobs();
  },3800);
 }catch(e){showLogin();$("login-error").textContent=e.message}
}
document.addEventListener("DOMContentLoaded",()=>{
 $("login-form").addEventListener("submit",async e=>{
  e.preventDefault();
  try{
   await api("/api/login",{username:"lab",password:$("login-password").value});
   $("login-error").textContent="";await startup();
  }catch(err){$("login-error").textContent=err.message}
 });
 $("narrator").addEventListener("change",()=>{
  activeModel=$("narrator").value;
    updateReasoning();
  $("provider-badge").textContent=activeModel.startsWith("local")?"На этом ПК":
   activeModel.startsWith("grok")?"Grok":"ChatGPT";
 });
 $("save").addEventListener("change",()=>loadGame($("save").value).catch(e=>showToast(e.message)));
 $("open-history").addEventListener("click",openHistory);
 $("open-latency").addEventListener("click",openLatency);
 $("local-exit").addEventListener("click",exitLocalStory);
 $("open-looks").addEventListener("click",openLooks);
 $("close-info").addEventListener("click",closeInfo);
 $("info-modal").addEventListener("click",e=>{
  if(e.target===$("info-modal"))closeInfo();
 });
 $("view-layers").addEventListener("click",()=>{
   if(!currentGame?.scene?.cg_url)return;
   showSceneVariant(stageView==="layers"?"cg":"layers");
 });
 $("view-background").addEventListener("click",()=>{
   showSceneVariant(stageView==="background"?"auto":"background");
 });
 $("toggle-characters").addEventListener("click",()=>{
   if(stageView!=="layers"){
     stageView="layers";castVisible=true;
   }else castVisible=!castVisible;
   renderScene(currentGame);
 });
 $("manual-cg").addEventListener("click",requestCG);

 $("send").addEventListener("click",()=>runTurn(false));
 $("resume").addEventListener("click",()=>runTurn(true));
 $("fit").addEventListener("click",()=>{
  fit=!fit;
  $("stage").classList.toggle("fill",!fit);
  $("fit").textContent=fit?"▣ Вписать полностью":"▣ Заполнить кадр";
 });
 $("providers-button").addEventListener("click",openProviders);
 $("close-providers").addEventListener("click",closeProviders);
 $("auth-openai").addEventListener("click",()=>startOAuth("openai"));
 $("auth-grok").addEventListener("click",()=>startOAuth("grok"));
 $("oauth-cancel").addEventListener("click",cancelOAuth);
 $("oauth-copy-code").addEventListener("click",copyOAuthCode);
 $("reload-models").addEventListener("click",()=>loadModels().catch(e=>showToast(e.message)));
  $("reasoning").addEventListener("change",()=>{
    try{localStorage.setItem("vn-web-effort:"+activeModel,$("reasoning").value)}catch(_){}
  });
  $("visual-retry").addEventListener("click",async()=>{
    if(!currentGame)return;
    try{
      await scheduleMissingVisuals(currentGame,{retry:true});
      $("visual-retry").hidden=true;
      await pollVisualJobs();
    }catch(e){showToast(e.message)}
  });
 $("refresh").addEventListener("click",refresh);
 $("open-commands").addEventListener("click",()=>{
  if(!$("command-menu").hidden){closeCommandMenu();return}
  commandManual=true;updateCommandMenu();$("player-action").focus();
 });
 $("player-action").addEventListener("input",()=>{commandManual=false;updateCommandMenu()});
 $("player-action").addEventListener("keydown",e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==="Enter"){e.preventDefault();runTurn(false);return}
  if(e.key==="Escape"){closeCommandMenu();return}
  if($("command-menu").hidden||!commandItems.length)return;
  if(e.key==="ArrowDown"||e.key==="ArrowUp"){
   e.preventDefault();commandIndex=(commandIndex+(e.key==="ArrowDown"?1:-1)+commandItems.length)%commandItems.length;paintCommandMenu();
  }else if(e.key==="Enter"){e.preventDefault();selectCommand(commandItems[commandIndex]);}
 });
 document.addEventListener("click",e=>{if(!e.target.closest(".input-area"))closeCommandMenu()});
 document.addEventListener("keydown",e=>{if(e.key==="Escape"){closeCommandMenu();closeInfo();closeProviders();}});
 startup();
});
