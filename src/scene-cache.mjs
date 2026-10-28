// Background assets persist per unique place+time+weather for this game.
const compact=(x,n=120)=>String(x??"").trim().replace(/\s+/g," ").slice(0,n);
export function sceneKey(style,{location,time_of_day="",weather=""}={}){
 return JSON.stringify([compact(style,50),compact(location,160).toLowerCase(),
   compact(time_of_day,40).toLowerCase(),compact(weather,40).toLowerCase()]);
}
export function rememberScene(game,scene=game.scene){
 const bg=scene?.background_url,style=scene?.background_style;
 if(!bg||!style||style!==game.art_style)return null;
 game.scene_catalog ||= {};
 const key=sceneKey(game.art_style,scene);
 const record={key,location:compact(scene.location),time_of_day:compact(scene.time_of_day),
  weather:compact(scene.weather),background_url:bg,background_style:style,
  environment:scene.environment||null,saved_at:new Date().toISOString()};
 game.scene_catalog[key]=record;
 const entries=Object.keys(game.scene_catalog);
 if(entries.length>65){
  const oldest=entries.sort((a,b)=>game.scene_catalog[a].saved_at.localeCompare(game.scene_catalog[b].saved_at));
  for(const k of oldest.slice(0,entries.length-65))delete game.scene_catalog[k];
 }
 return record;
}
export function restoreScene(game,scene){
 const key=sceneKey(game.art_style,scene);
 return game.scene_catalog?.[key]||null;
}
