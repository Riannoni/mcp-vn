// Grounded environment tags for English SDXL prompts and strict QA policy.
// Rules are generalizable; scenes can override with scene.environment.
const rules=[
 {id:"outdoor_market_square",test:/площад|рынок|базар|market|town square|marketplace/i,
  positive:["exterior outdoor public medieval market square","open sky","paved cobblestone ground","market stalls and outdoor shop fronts","town clock tower","pedestrians absent","streets leading out of square"],
  negative:["interior","inside a room","bedroom","office","living room","wallpaper","chandelier","ceiling","indoor hallway","apartment","palace room"]},
 {id:"outdoor_street",test:/улиц|переул|проспект|алле|street|road|alley/i,
  positive:["outdoor street","open sky","road surface","distant buildings","external walls and roofs"],
  negative:["interior","living room","bedroom","indoor hallway"]},
 {id:"outdoor_forest",test:/лес|чащ|роща|forest|woods|grove/i,
  positive:["outdoor forest","trees and understory vegetation","sky glimpses through leaves","natural ground"],
  negative:["room","interior","house","wallpaper","chandelier"]},
 {id:"outdoor_courtyard",test:/двор|сад|courtyard|garden/i,
  positive:["outdoor courtyard","open air","sky","architectural facades"],
  negative:["indoor living room","office","bedroom"]},
 {id:"indoor_room",test:/комнат|спальн|кабинет|гостин|поко[ий]|room|bedroom|study|chamber|office/i,
  positive:["interior indoor room","ceiling","interior walls","furniture","windows showing world outside"],
  negative:["wide open public square","outside on street","forest canopy"]},
 {id:"indoor_tavern",test:/таверн|трактир|постоял|inn|tavern|pub/i,
  positive:["interior of a fantasy tavern","wooden tables and benches","warm interior candlelight"],
  negative:["exterior town square","outdoor street"]},
 {id:"underground_cave",test:/пещер|подземел|cave|dungeon/i,
  positive:["dark natural cave or underground dungeon","stone walls","rough floor","underground light sources"],
  negative:["open blue sky","modern office","living room"]}
];
const text=(v,n=1200)=>String(v??"").trim().replace(/\s+/g," ").slice(0,n);
export function environmentFor(scene){
 const custom=scene?.environment;
 if(custom&&typeof custom==="object"&&Array.isArray(custom.positive)&&custom.positive.length){
  return {id:text(custom.id||"custom",80),positive:custom.positive.slice(0,16).map(x=>text(x,140)),
          negative:(custom.negative||[]).slice(0,16).map(x=>text(x,140)),
          indoor:custom.indoor===true,confidence:"explicit"};
 }
 const loc=text(scene?.location||"",160);
 const rule=rules.find(x=>x.test.test(loc));
 if(rule)return {id:rule.id,positive:rule.positive,negative:rule.negative,
                    indoor:rule.id.startsWith("indoor_")||rule.id.startsWith("underground_"),confidence:"rule"};
 return {id:"unclassified",positive:[loc,"coherent natural environment"],negative:["collage","split-screen","unrelated scenery"],indoor:null,confidence:"unknown"};
}
export const environmentID=scene=>environmentFor(scene).id;
export function visibleCharacters(game){
 const names=new Set();
 const visible=[];
 for(const s of game?.scene?.sprites||[]){
  if(!s||!s.name||names.has(s.name))continue;
  names.add(s.name);visible.push(s.name);
 }
 return visible;
}
