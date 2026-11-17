#!/usr/bin/env node
/**
 * TOC Ministries: offline-only church service compiler.
 *
 * Writes ONLY owner-local, public-audience and stream-safe JSON. No native
 * output, stage notes, projection, OS audio, microphone, camera, OBS or network.
 * Further private confidence/rendering is a separate authenticated phase.
 */
import {readFile,writeFile,mkdir,lstat,unlink,rmdir} from 'node:fs/promises';
import {isAbsolute,join} from 'node:path';
import {createWorshipLibrary,compileWorshipFromLibrary} from '../src/worship-library.mjs';

const MAX_JSON_BYTES=2_000_000;
const NAMES=Object.freeze(['audience.json','broadcast.json','issues.json']);

function parseOptions(argv){
 const recognized=new Set(['--library','--plan','--output-dir']);
 if(argv.length!==6)throw new Error(
   'Usage: compile-worship-service.mjs --library /absolute.json --plan /absolute.json --output-dir /absolute/new-dir');
 const options={};
 for(let i=0;i<argv.length;i+=2){
   const flag=argv[i],value=argv[i+1];
   if(!recognized.has(flag)||flag in options||typeof value!=='string'||!isAbsolute(value))
     throw new Error('Provide each recognized option exactly once using absolute local paths.');
   options[flag]=value;
 }
 if(Object.keys(options).length!==3)throw new Error('Library, plan and output-dir are all required.');
 if(options['--library']===options['--plan']||
    options['--library']===options['--output-dir']||
    options['--plan']===options['--output-dir'])
   throw new Error('Service inputs and output destination must have distinct paths.');
 return options;
}
async function loadJson(file){
 const raw=await readFile(file);
 if(raw.byteLength>MAX_JSON_BYTES)throw new Error('Offline service JSON exceeds the size limit.');
 try{return JSON.parse(raw.toString('utf8'));}
 catch{throw new Error('Invalid offline catalog or service JSON.');}
}
async function createProtectedOutputDirectory(dir){
 if(!isAbsolute(dir))throw new Error('Output must use an absolute directory.');
 let created=false;
 try{await mkdir(dir,{mode:0o700});created=true;}
 catch(error){if(error?.code!=='EEXIST')throw error;}
 const metadata=await lstat(dir);
 if(metadata.isSymbolicLink()||!metadata.isDirectory())
   throw new Error('Output must be a regular directory, never a symbolic link.');
 if((metadata.mode&0o077)!==0)
   throw new Error('Output directory must be private to its owning user (0700).');
 return created;
}
async function writeExclusive(dir,data,createdDir){
 const completed=[];
 try{
   // Preflight rejects common accidental duplicate exports before any write.
   for(const name of NAMES){
     try{await lstat(join(dir,name));throw new Error('Existing export would be overwritten: '+name);}
     catch(error){if(error?.code!=='ENOENT')throw error;}
   }
   for(const name of NAMES){
     await writeFile(join(dir,name),JSON.stringify(data[name],null,2)+'\n',{
       flag:'wx',mode:0o600
     });
     completed.push(join(dir,name));
   }
 }catch(error){
   // Remove only files created by THIS invocation, never an older export.
   for(const file of completed){try{await unlink(file);}catch{}}
   if(createdDir){try{await rmdir(dir);}catch{}}
   throw error;
 }
}
export async function compileOfflineServiceFiles(args){
 const opts=parseOptions(args);
 const [catalog,plan]=await Promise.all([
   loadJson(opts['--library']),loadJson(opts['--plan'])
 ]);
 const library=createWorshipLibrary(catalog);
 const built=compileWorshipFromLibrary(plan,library);
 const outputDir=opts['--output-dir'];
 const createdDir=await createProtectedOutputDirectory(outputDir);
 await writeExclusive(outputDir,{
   'audience.json':built.publicDeck,
   'broadcast.json':built.broadcastDeck,
   'issues.json':built.issues
 },createdDir);
 return Object.freeze({
   schema:'toc.worship-cli-receipt/v1',
   project:'TOC',
   compiled:true,
   outputFiles:[...NAMES],
   audienceSlides:built.publicDeck.slides.length,
   broadcastSlides:built.broadcastDeck.slides.length,
   rightsIssues:built.issues.length,
   stageExported:false,
   hardwareActivated:false,
   livestreamStarted:false
 });
}
if(process.argv[1]&&new URL('file:'+process.argv[1]).pathname===new URL(import.meta.url).pathname){
 try{
   const receipt=await compileOfflineServiceFiles(process.argv.slice(2));
   process.stdout.write(JSON.stringify(receipt)+'\n');
 }catch(error){
   process.stderr.write('TOC offline compiler refused request: '+String(error?.message??error)+'\n');
   process.exitCode=1;
 }
}
