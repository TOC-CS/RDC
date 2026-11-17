#!/usr/bin/env node
// Compile only. Never executes AppleScript or controls a foreground app.
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir,platform} from 'node:os';
import {join} from 'node:path';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {buildKeynoteScript,buildPowerPointScript} from '../src/adapters.mjs';

const run=promisify(execFile);
export async function verifyMacPresentationScripts({os=platform(),compiler=run}={}){
 if(os!=='darwin')
   return {schema:'presentation.mac-script-check/v1',platform:os,
     checked:0,passed:0,failed:0,status:'not_applicable'};
 const path=await mkdtemp(join(tmpdir(),'toc-presentation-compile-'));
 const operations=['next','previous','goto','readback'];
 const sources=[['keynote',buildKeynoteScript],['powerpoint-macos',buildPowerPointScript]];
 const results=[];
 try{
   for(const [app,build] of sources){
     for(const action of operations){
       const file=join(path,app+'-'+action+'.scpt');
       const script=build(action,2);
       try{
         await compiler('/usr/bin/osacompile',['-e',script,'-o',file],
           {encoding:'utf8',timeout:5000,maxBuffer:32768});
         results.push({app,action,compiles:true});
       }catch(error){
         results.push({app,action,compiles:false,
           errorClass:error.code??'compile_failure'});
       }
     }
   }
 }finally{await rm(path,{recursive:true,force:true});}
 const passed=results.filter(r=>r.compiles).length;
 return {schema:'presentation.mac-script-check/v1',platform:os,
   checked:results.length,passed,failed:results.length-passed,
   status:passed===results.length?'syntax_verified':'syntax_failed',
   liveAppExecutionVerified:false,visualOutputVerified:false,
   note:'Compilation validates syntax only; real application control and output still require separate tests.',
   results};
}
if(process.argv[1]&&import.meta.url===new URL('file://'+process.argv[1]).href){
 const results=await verifyMacPresentationScripts();
 process.stdout.write(JSON.stringify(results,null,2)+'\n');
 if(results.failed)process.exitCode=1;
}
