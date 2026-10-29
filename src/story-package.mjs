import {ENGINE_POLICY} from './engine-policy.mjs';
const required=(value,max)=>{
 if(typeof value!=='string'||!value.trim()||value.length>max)throw Error('Invalid text field');
 return value.trim();
};
const optional=(value,max)=>value==null?'':required(value,max);
const slug=value=>{
 if(typeof value!=='string'||!/^[a-z0-9][a-z0-9_-]{1,79}$/.test(value))
  throw Error('Invalid story ID');
 return value;
};
const httpsPage=value=>{
 if(value==null||value==='')return '';
 const url=new URL(required(value,2048));
 if(url.protocol!=='https:'||url.username||url.password||url.port||url.hash)
  throw Error('A canonical HTTPS source page is required');
 return url.href;
};
export function normalizeStoryPackage(raw){
 if(!raw||typeof raw!=='object'||Array.isArray(raw))throw Error('Not a JSON story');
 if(raw.schema!==ENGINE_POLICY.story_package_schema)throw Error('Unsupported story package version');
 if(raw.rights_confirmed!==true)throw Error('Story import requires confirmed rights');
 if(!['original','external','user-provided'].includes(raw.source))throw Error('Invalid source');
 if(raw.source==='external'&&!raw.source_url)throw Error('External story needs provenance');
 for(const forbidden of ['engine','engine_policy','scripts','remote_assets','javascript','html'])
  if(Object.hasOwn(raw,forbidden))throw Error('Story package cannot contain executable or engine-level fields');
 const characters=raw.characters??[];
 if(!Array.isArray(characters)||characters.length>64)throw Error('Invalid character list');
 const seen=new Set();
 const cast=characters.map((c,i)=>{
  if(!c||typeof c!=='object'||Array.isArray(c))throw Error('Invalid character');
  const name=required(c.name,100);
  if(seen.has(name.toLocaleLowerCase()))throw Error('Repeated character');
  seen.add(name.toLocaleLowerCase());
  const age=c.age;
  if(age!==undefined&&(!Number.isInteger(age)||age<0||age>250))throw Error('Invalid character age');
  return {id:slug(c.id||'actor-'+(i+1)),name,
    ...(age===undefined?{}:{age}),description:optional(c.description,8000)};
 });
 const scene=raw.scene;
 if(!scene||typeof scene!=='object'||Array.isArray(scene))throw Error('Opening scene required');
 if(scene.background_url||scene.cg_url||(scene.sprites||[]).length)throw Error('External assets are not imported automatically');
 const choices=raw.choices??[];
 if(!Array.isArray(choices)||choices.length>12)throw Error('Invalid choices');
 const source_url=httpsPage(raw.source_url);
 return {
  id:slug(raw.id),title:required(raw.title,180),author:required(raw.author,120),
  source:raw.source,rights_confirmed:true,source_url,
  summary:required(raw.summary,5000),lore:required(raw.lore,60000),
  opening:required(raw.opening,12000),
  scene:{location:required(scene.location,180),background_url:'',sprites:[]},
  characters:cast,choices:choices.map(x=>required(x,400)),
  package_schema:ENGINE_POLICY.story_package_schema,
  provenance:{format:'local-json-v1',imported_at:new Date().toISOString(),
    source:raw.source,source_url}
 };
}
