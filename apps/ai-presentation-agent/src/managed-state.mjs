// This file stores a private local bearer credential for interoperating with
// an independent long-lived presentation session. Never print that credential.
import {homedir} from 'node:os';
import {join,isAbsolute,resolve} from 'node:path';
import {mkdir,lstat,readFile} from 'node:fs/promises';

export function statePaths(env=process.env){
 const provided=env.PRESENTATION_AGENT_STATE_DIR;
 const dir=provided??join(homedir(),'.local','state','ai-presentation-agent');
 if(typeof dir!=='string'||!isAbsolute(dir))
   throw new Error('Presentation state directory must be an absolute path.');
 const root=resolve(dir);
 if(root==='/'||root===homedir())throw new Error('Unsafe presentation state directory.');
 return {dir:root,file:join(root,'control.json')};
}
async function checked(path,dir){
 const st=await lstat(path);
 if(st.isSymbolicLink()||!(dir?st.isDirectory():st.isFile()))
   throw new Error('Presentation state path must not be a symlink.');
 if((st.mode&0o077)!==0)
   throw new Error('Private presentation state permissions must restrict group and others.');
 if(typeof process.getuid==='function'&&st.uid!==process.getuid())
   throw new Error('Presentation state must belong to the running user.');
 return st;
}
export async function setupPrivateState(env=process.env){
 const paths=statePaths(env);
 await mkdir(paths.dir,{recursive:true,mode:0o700});
 await checked(paths.dir,true);
 return paths;
}
export async function readPrivateState(env=process.env){
 const paths=statePaths(env);
 try{
   await checked(paths.dir,true);
   await checked(paths.file,false);
   const state=JSON.parse(await readFile(paths.file,'utf8'));
   if(typeof state.instanceId!=='string'||state.instanceId.length<8||
      !Number.isInteger(state.port)||state.port<1||state.port>65535||
      !/^[a-f0-9]{64}$/.test(state.token)||
      !/^[a-f0-9]{64}$/.test(state.viewerToken)||
      (state.stageToken!==undefined&&
       (!/^[a-f0-9]{64}$/.test(state.stageToken)||
        state.stageToken===state.token||state.stageToken===state.viewerToken))||
      (state.streamToken!==undefined&&
       (!/^[a-f0-9]{64}$/.test(state.streamToken)||
        [state.token,state.viewerToken,state.stageToken].includes(state.streamToken))))
      throw new Error('Private presentation state file is invalid.');
   return state;
 }catch(error){
   if(error.code==='ENOENT')throw new Error('No active presentation session state found.');
   throw error;
 }
}
