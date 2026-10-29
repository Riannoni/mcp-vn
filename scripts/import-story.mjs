#!/usr/bin/env node
/** Offline, explicit import: no scraping, HTTP access or remote assets. */
import fs from 'node:fs/promises';
import {normalizeStoryPackage} from '../src/story-package.mjs';
import {importStoryPackage} from '../src/game-store.mjs';
const args=process.argv.slice(2);
const dry=args.includes('--dry-run');
const filename=args.find(x=>!x.startsWith('--'));
if(!filename||args.some(x=>x.startsWith('--')&&x!=='--dry-run')){
 console.error('Usage: node scripts/import-story.mjs [--dry-run] /path/to/story.json');
 process.exitCode=2;
}else{
 try{
  const st=await fs.stat(filename);
  if(!st.isFile()||st.size>512*1024)throw Error('Story file must be <=512 KiB');
  const doc=JSON.parse(await fs.readFile(filename,'utf8'));
  const normalized=normalizeStoryPackage(doc);
  if(dry)console.log(JSON.stringify({valid:true,id:normalized.id,title:normalized.title,
    characters:normalized.characters.length,source:normalized.source},null,2));
  else console.log(JSON.stringify(await importStoryPackage(doc),null,2));
 }catch(error){console.error('Story import rejected:',error.message);process.exitCode=1}
}
