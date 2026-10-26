import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import {dataRoot,attachImage,gameGet} from "./game-store.mjs";
const root=path.join(dataRoot,"jobs");
let lock=Promise.resolve();
const exclusive=fn=>{const p=lock.then(fn);lock=p.catch(()=>{});return p};
const jfile=id=>{if(!/^[a-f0-9-]{36}$/.test(id))throw Error("Invalid job ID");return path.join(root,id+".json")};
const read=id=>fs.readFile(jfile(id),"utf8").then(JSON.parse);
const save=async j=>{await fs.mkdir(root,{recursive:true});const tmp=jfile(j.id)+".tmp";await fs.writeFile(tmp,JSON.stringify(j));await fs.rename(tmp,jfile(j.id))};
const all=async()=>{await fs.mkdir(root,{recursive:true});return Promise.all((await fs.readdir(root)).filter(x=>x.endsWith(".json")).map(x=>read(x.slice(0,-5))))};
const styles={anime:"animagine-xl-4.0-opt.safetensors",semireal:"DreamShaperXL_Turbo_v2_1.safetensors",realistic:"RealVisXL_V5.0_fp16.safetensors",poster:"Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"};
export function styleList(){return Object.keys(styles)}
export async function enqueue({game_id,prompt,kind="background",style="semireal",character=""}){
 await gameGet(game_id);
 if(!["background","sprite","scene","video"].includes(kind))throw Error("Invalid kind");
 if(!styles[style])throw Error("Invalid style");
 if(typeof prompt!=="string"||!prompt.trim()||prompt.length>4000)throw Error("Invalid prompt");
 if(kind==="sprite"&&!character)throw Error("Character required");
 return exclusive(async()=>{
 const j={id:crypto.randomUUID(),game_id,kind,style,character:String(character).slice(0,100),prompt:prompt.trim(),
 model:styles[style],status:"queued",progress:0,attempts:0,created_at:new Date().toISOString()};
 await save(j);return j});
}
export async function getJob(id){return read(id)}
export async function jobsForGame(gameId){
 const jobs=(await all()).filter(x=>x.game_id===gameId);
 return jobs.sort((a,b)=>b.created_at.localeCompare(a.created_at)).slice(0,35);
}
export async function nextJob(){
 return exclusive(async()=>{
 const jobs=(await all()).sort((a,b)=>a.created_at.localeCompare(b.created_at));
 const now=Date.now();
 const j=jobs.find(x=>x.status==="queued"||(x.status==="working"&&Date.parse(x.lease_until||"")<now&&x.attempts<3));
 if(!j)return null;
 j.status="working";j.attempts++;j.lease_until=new Date(now+25*60*1000).toISOString();j.claimed_at=new Date().toISOString();
 await save(j);return j});
}
export async function jobProgress(id,progress){
 return exclusive(async()=>{
 const j=await read(id);if(j.status!=="working")return j;
 j.progress=Math.min(99,Math.max(0,Number(progress)||0));j.lease_until=new Date(Date.now()+25*60*1000).toISOString();
 await save(j);return j});
}
export async function completeJob(id,bytes,mime,baseUrl){
 return exclusive(async()=>{
 const j=await read(id);
 if(j.status!=="working")throw Error("Job is not in progress");
 const ext=mime==="image/png"?"png":mime==="image/jpeg"?"jpg":mime==="image/webp"?"webp":mime==="video/mp4"?"mp4":null;
 if(!ext)throw Error("Unsupported media type");
 if(!Buffer.isBuffer(bytes)||!bytes.length||bytes.length>100*1024*1024)throw Error("Invalid payload size");
 if(ext==="png"&&!bytes.subarray(0,8).equals(Buffer.from("89504e470d0a1a0a","hex")))throw Error("Not PNG");
 if(ext==="mp4"&&bytes.toString("latin1",4,8)!=="ftyp")throw Error("Not MP4");
 const name=crypto.randomUUID()+"."+ext,dir=path.join(dataRoot,"assets");
 await fs.mkdir(dir,{recursive:true});await fs.writeFile(path.join(dir,name),bytes,{flag:"wx",mode:0o600});
 j.file=name;j.status="done";j.progress=100;j.finished_at=new Date().toISOString();
 j.asset_url=baseUrl.replace(/\/$/,"")+"/assets/"+name+"?sig="+assetSignature(name);
 await save(j);
 await attachImage(j.game_id,{kind:j.kind,character:j.character,url:j.asset_url});
 return j});
}
export async function failJob(id,error){
 return exclusive(async()=>{
 const j=await read(id);j.status=j.attempts>=3?"failed":"queued";j.error=String(error||"Generation failed").slice(0,400);
 await save(j);return j});
}
export async function assetFile(name){
 if(!/^[a-f0-9-]{36}\.(png|jpg|webp|mp4)$/.test(name))throw Error("Invalid asset name");
 return path.join(dataRoot,"assets",name);
}

export function assetSignature(name){
 const secret=process.env.VN_ASSET_SECRET;
 if(!secret)throw Error("VN_ASSET_SECRET required");
 return crypto.createHmac("sha256",secret).update(name).digest("hex");
}
