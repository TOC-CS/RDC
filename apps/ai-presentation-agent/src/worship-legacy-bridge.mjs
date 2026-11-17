/**
 * TOC Worship Library compatibility adapter.
 *
 * Reads the earlier toc.worship.song-library/v1 research format and maps it
 * into the content-addressed source catalog implemented by worship-library.
 * No additional director, live control, network, media or playback dependency.
 */
import {createWorshipLibrary,compileWorshipFromLibrary} from './worship-library.mjs';
import {randomUUID} from 'node:crypto';
import {join,isAbsolute} from 'node:path';
import {mkdir,lstat,readFile,writeFile,rename,unlink,open} from 'node:fs/promises';

const LEGACY='toc.worship.song-library/v1';
const ID=/^[A-Za-z][A-Za-z0-9._-]{0,59}$/;
function plain(v,label){
 if(!v||typeof v!=='object'||Array.isArray(v))
   throw new Error('Invalid '+label+'.');
 return v;
}
function checkLegacy(src){
 plain(src,'legacy song library');
 if(src.schema!==LEGACY)throw new Error('Unsupported legacy worship library schema.');
 if(!Array.isArray(src.songs)||src.songs.length>500)throw new Error('Invalid offline song library.');
 const seen=new Set();
 for(const song of src.songs){
   plain(song,'legacy song');
   if(typeof song.id!=='string'||!ID.test(song.id))throw new Error('Invalid song ID.');
   if(seen.has(song.id))throw new Error('Duplicate song ID.');
   seen.add(song.id);
 }
 return src;
}
function slug(label,index){
 const key=String(label).normalize('NFKC').toLowerCase()
   .replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,45);
 return (key&&/^[a-z]/.test(key)?key:'section-'+String(index+1));
}
function convertLegacy(input,plan){
 const src=checkLegacy(input);
 plain(plan,'service plan');
 if(!Array.isArray(plan.items)||plan.items.length<1||plan.items.length>150)
   throw new Error('Legacy service plan requires 1 to 150 items.');
 const songLookup=new Map(src.songs.map(s=>[s.id,s]));
 const songs=[],scriptures=[],segments=[],refs=[],seenSlots=new Set();
 const perSong=new Map();
 const reserve=item=>{
   if(typeof item.id!=='string'||!ID.test(item.id)||seenSlots.has(item.id))
     throw new Error('Duplicate or invalid legacy service item ID.');
   seenSlots.add(item.id);
 };
 for(const item of plan.items){
   plain(item,'legacy service item');reserve(item);
   if(item.type==='song'){
     const song=songLookup.get(item.songId);
     if(!song)throw new Error('Unknown song reference: '+String(item.songId));
     if(!perSong.has(song.id)){
       if(!Array.isArray(song.sections)||!song.sections.length)
         throw new Error('Legacy song has no sections.');
       const ids=new Map(),sections=[];
       for(const section of song.sections){
         plain(section,'legacy song section');
         if(typeof section.label!=='string'||!section.label.trim())
           throw new Error('Legacy song section requires a label.');
         const key=section.label.trim().normalize('NFKC').toLowerCase().replace(/\s+/g,' ');
         if(ids.has(key))throw new Error('Duplicate legacy song section.');
         const sectionId=slug(section.label,sections.length);
         if(sections.some(x=>x.id===sectionId))
           throw new Error('Ambiguous legacy song section identifier.');
         ids.set(key,sectionId);
         sections.push({
           id:sectionId,label:section.label,
           lines:section.lines,notes:section.notes,chords:section.chords
         });
       }
       const normalized={
         id:song.id,revision:song.revision??'r1',title:song.title,
         rights:song.rights??{source:'unknown'},
         notes:song.notes,key:song.key,sections,arrangements:[]
       };
       songs.push(normalized);
       perSong.set(song.id,{normalized,ids});
     }
     const saved=perSong.get(song.id);
     const order=item.order??song.defaultOrder;
     if(!Array.isArray(order)||!order.length)throw new Error('Song order/arrangement required.');
     const sectionIds=order.map(label=>{
       const key=String(label).trim().normalize('NFKC').toLowerCase().replace(/\s+/g,' ');
       const sectionId=saved.ids.get(key);
       if(!sectionId)throw new Error('Unknown song arrangement section: '+label);
       return sectionId;
     });
     // Each service slot owns its selected arrangement, even for repeated song
     // appearances. The source sections remain stored once per song.
     const arrangementId='slot-'+item.id;
     saved.normalized.arrangements.push({id:arrangementId,sectionIds});
     refs.push({slotId:item.id,sourceType:'song',sourceId:song.id,arrangementId});
   }else if(item.type==='scripture'){
     const sourceId='scripture-'+item.id;
     scriptures.push({
       id:sourceId,revision:'r1',title:item.title??'Scripture Reading',
       reference:item.reference,translation:item.translation??'NKJV',
       text:item.text??'',
       scriptureRights:item.scriptureRights??{source:'unknown',displayAuthorized:false,streamAuthorized:false},
       notes:item.notes
     });
     refs.push({slotId:item.id,sourceType:'scripture',sourceId});
   }else{
     const sourceId='segment-'+item.id;
     segments.push({
       id:sourceId,revision:'r1',type:item.type,title:item.title,
       text:item.text??'',notes:item.notes,
       publicAuthorized:item.publicAuthorized===true,
       streamAuthorized:item.streamAuthorized===true
     });
     refs.push({slotId:item.id,sourceType:'segment',sourceId});
   }
 }
 const catalog=createWorshipLibrary({schema:'toc.worship-library/v1',songs,scriptures,segments});
 const inventory=new Map(catalog.listEntries().map(x=>[x.id,x]));
 const compiledPlan={
   title:plan.title,theme:plan.theme,
   items:refs.map(ref=>{
     const found=inventory.get(ref.sourceId);
     if(!found)throw new Error('Legacy catalog reference missing.');
     return {
       id:ref.slotId,sourceType:ref.sourceType,sourceId:ref.sourceId,
       revision:found.revision,sha256:found.sha256,
       ...(ref.arrangementId?{arrangementId:ref.arrangementId}:{})
     };
   })
 };
 return {catalog,compiledPlan};
}
export function buildServiceFromWorshipLibrary(library,plan,options={}){
 const normalized=convertLegacy(library,plan);
 return compileWorshipFromLibrary(normalized.compiledPlan,normalized.catalog,options);
}
/**
 * Private, atomic offline persistence for legacy research format.
 * Path selection and use must be explicitly performed by the local operator.
 */
export class WorshipLibraryStore{
 constructor({root}={}){
   if(typeof root!=='string'||!isAbsolute(root)||root==='/'||root.length>2048)
     throw new Error('Worship library requires an absolute private root directory.');
   this.root=root;
 }
 async directory(create=false){
   if(create){
     try{await mkdir(this.root,{mode:0o700});}
     catch(error){if(error?.code!=='EEXIST')throw error;}
   }
   const info=await lstat(this.root);
   if(info.isSymbolicLink()||!info.isDirectory())
     throw new Error('Worship library directory cannot be a symbolic link.');
   if((info.mode&0o077)!==0)
     throw new Error('Worship library directory must be owner-private (0700).');
 }
 async save(catalog){
   const input=checkLegacy(catalog);
   await this.directory(true);
   const destination=join(this.root,'songs.json');
   const tmp=join(this.root,'.songs-'+randomUUID()+'.tmp');
   try{
     await writeFile(tmp,JSON.stringify(input,null,2)+'\n',{flag:'wx',mode:0o600});
     const handle=await open(tmp,'r');
     try{await handle.sync();}finally{await handle.close();}
     // Never follow a substituted output symlink.
     try{const previous=await lstat(destination);
       if(previous.isSymbolicLink()||!previous.isFile())
         throw new Error('Existing songs.json is not a regular library file.');
     }catch(error){if(error?.code!=='ENOENT')throw error;}
     await this.directory(false);
     await rename(tmp,destination);
     return {saved:true,ownerPrivate:true};
   }finally{
     try{await unlink(tmp);}catch{}
   }
 }
 async load(){
   await this.directory(false);
   const path=join(this.root,'songs.json');
   const info=await lstat(path);
   if(info.isSymbolicLink()||!info.isFile())
     throw new Error('Worship library file cannot be a symbolic link.');
   if((info.mode&0o077)!==0)
     throw new Error('Worship library file must be owner-private (0600).');
   const data=await readFile(path,'utf8');
   if(Buffer.byteLength(data)>2_000_000)throw new Error('Worship library exceeds size limit.');
   return checkLegacy(JSON.parse(data));
 }
}
