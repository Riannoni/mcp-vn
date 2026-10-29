import contract from "../engine/contract.json" with {type:"json"};
if(contract.engine_id!=="mcp-vn"||contract.contract_version!==1||
   contract.render?.max_anchored_principals_per_pass!==4)
 throw Error("Unsupported engine contract");
export const ENGINE_POLICY=Object.freeze(contract);
export function engineSnapshot(){
 const r=contract.render;
 return {engine_id:contract.engine_id,contract_version:contract.contract_version,
   render_profile:r.profile,pose_catalog:r.pose_catalog,qa_policy:r.qa_policy,
   max_anchored_principals_per_pass:r.max_anchored_principals_per_pass};
}
export function assertEngineSnapshot(snapshot){
 if(snapshot==null)return true;
 const expected=engineSnapshot();
 if(!snapshot||typeof snapshot!=="object"||
   Object.keys(expected).some(k=>snapshot[k]!==expected[k])||
   Object.keys(snapshot).some(k=>!(k in expected)))
   throw Error("Incompatible engine contract: update server and worker together");
 return true;
}
