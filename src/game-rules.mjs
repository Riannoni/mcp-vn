import {randomInt,randomUUID} from "node:crypto";
const STATS=["strength","agility","insight","presence","arcana"];
const MODES=["narrative","adventure"];
const clean=(x,n=200)=>String(x??"").replace(/\s+/g," ").trim().slice(0,n);
export function ensureRules(game){
 game.rules ||= {};
 const rules=game.rules;
 if(!MODES.includes(rules.mode))rules.mode="narrative";
 rules.stats ||= {};
 for(const stat of STATS)
  if(!Number.isInteger(rules.stats[stat]))rules.stats[stat]=1;
 rules.history ||= [];
 return rules;
}
export function setRulesMode(game,mode){
 if(!MODES.includes(mode))throw Error("Invalid rules mode");
 const rules=ensureRules(game);
 rules.mode=mode;
 return rules;
}
export function resolveCheck(game,{stat,difficulty=12,description="",advantage=0}={},die){
 const rules=ensureRules(game);
 if(rules.mode!=="adventure")throw Error("Skill checks are disabled in narrative mode");
 if(!STATS.includes(stat))throw Error("Invalid character stat");
 const dc=Number(difficulty);
 if(!Number.isInteger(dc)||dc<5||dc>30)throw Error("Difficulty must be an integer 5..30");
 const adv=Number(advantage)||0;
 if(![-1,0,1].includes(adv))throw Error("Advantage must be -1, 0 or 1");
 const roll=die||(()=>randomInt(1,21));
 const a=roll(),b=adv!==0?roll():null;
 if(!Number.isInteger(a)||a<1||a>20||b!==null&&(!Number.isInteger(b)||b<1||b>20))
  throw Error("Bad dice source");
 const selected=b===null?a:adv>0?Math.max(a,b):Math.min(a,b);
 const modifier=rules.stats[stat]||0;
 const total=selected+modifier;
 const success=selected===20||selected!==1&&total>=dc;
 const item={id:randomUUID(),turn:game.memory?.turn||0,at:new Date().toISOString(),
  stat,description:clean(description,200),difficulty:dc,rolls:b===null?[a]:[a,b],
  selected,modifier,total,success,margin:total-dc,advantage:adv};
 rules.history=rules.history.concat(item).slice(-120);
 return item;
}
export function getRuleSummary(game){
 const rules=ensureRules(game);
 return {mode:rules.mode,stats:{...rules.stats},recent_checks:rules.history.slice(-5)};
}
