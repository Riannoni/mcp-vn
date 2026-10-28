// One AMD GPU is shared by ComfyUI and an on-demand local language model.
// Reserving the GPU stops NEW art claims while waiting for existing jobs.
// Never run a full model inference concurrently with an active art worker.
let held=false;
let waiter=Promise.resolve();
export function isLocalGpuReserved(){return held}
export async function withLocalGpu({activeArtJobs,prepare,infer,timeoutMs=150000}){
 if(typeof activeArtJobs!=="function"||typeof infer!=="function")
  throw Error("GPU coordinator requires callbacks");
 const previous=waiter;let releaseQueue;
 waiter=new Promise(resolve=>{releaseQueue=resolve});
 await previous;
 held=true;const started=Date.now();
 try{
  while(await activeArtJobs()){
   if(Date.now()-started>timeoutMs)throw Error("Art GPU is busy; local scene can be retried safely");
   await new Promise(resolve=>setTimeout(resolve,1200));
  }
  if(prepare)await prepare();
  return await infer();
 }finally{held=false;releaseQueue()}
}
