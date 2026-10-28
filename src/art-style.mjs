// A VN playthrough uses one stable image grammar. Migration is deterministic
// and never changes the original identity anchors or source images.
export const STYLES=Object.freeze(["realistic","semireal","anime","animation","poster"]);
const isStyle=s=>STYLES.includes(s);
export function inferStyle(game){
 if(isStyle(game?.art_style))return game.art_style;
 const weighted=new Map(STYLES.map(s=>[s,0]));
 for(const identity of Object.values(game?.identities||{})){
   if(isStyle(identity?.base_style))
    weighted.set(identity.base_style,weighted.get(identity.base_style)+4);
 }
 for(const sprite of game?.scene?.sprites||[]){
   if(isStyle(sprite?.art_style))
    weighted.set(sprite.art_style,weighted.get(sprite.art_style)+2);
 }
 if(isStyle(game?.scene?.background_style)){
   const s=game.scene.background_style;weighted.set(s,weighted.get(s)+1);
 }
 let winner="realistic",best=0;
 for(const [name,score] of weighted)if(score>best){best=score;winner=name}
 return winner;
}
export function ensureGameStyle(game){
 if(!game||typeof game!=="object")return game;
 if(!isStyle(game.art_style)){
  game.art_style=inferStyle(game);
  game.art_style_origin="legacy_migration";
  game.art_style_locked_at=new Date().toISOString();
 }
 return game;
}
export function requireStyle(style){
 if(!isStyle(style))throw Error("Unsupported VN art style: "+String(style));
 return style;
}
