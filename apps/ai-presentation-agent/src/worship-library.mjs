/**
 * TOC Ministries offline church-service content library.
 *
 * A local, immutable, content-addressed catalog is compiled into the existing
 * PresentationDirector-compatible worship service deck. The library performs
 * no file writes, network requests, physical output, stream, or device calls.
 * Callers own the private input JSON and explicitly authorize display rights.
 *
 * Library entries are deliberately inaccessible through JSON serialization
 * of the catalog/compilation. Public audience and broadcast decks contain
 * only whitelisted fields from the existing compiler. Detailed cue provenance,
 * stage chords, and notes require an independently supplied local stage grant.
 */
import {createHash} from 'node:crypto';
import {compileWorshipService} from './worship-service.mjs';

const LIBRARY_SCHEMA='toc.worship-library/v1';
const COMPILE_SCHEMA='toc.worship-library-compilation/v1';
const TYPES=new Set(['title','countdown','announcement','sermon','prayer','closing','media']);
const ITEM_ID=/^[A-Za-z][A-Za-z0-9._-]{0,59}$/;
const COMPONENT_ID=/^[A-Za-z][A-Za-z0-9._-]{0,79}$/;
const REVISION=/^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$/;
const SHA256=/^[0-9a-f]{64}$/;
const stores=new WeakMap();

function validObject(value,description){
 if(!value||typeof value!=='object'||Array.isArray(value))
   throw new Error(description+' must be an object.');
 return value;
}
function validString(value,max,description,{allowEmpty=false}={}){
 if(typeof value!=='string'||value.length>max||(!allowEmpty&&!value.trim()))
   throw new Error('Invalid '+description+'.');
 return value.trim();
}
function id(value,description,pattern=COMPONENT_ID){
 if(typeof value!=='string'||!pattern.test(value))
   throw new Error('Invalid '+description+' identifier.');
 return value;
}
function optionalString(value,max,description){
 return value===undefined?'':validString(value,max,description,{allowEmpty:true});
}
function stringList(value,{max=80,maxLength=240,description='lines'}={}){
 if(!Array.isArray(value)||value.length>max)
   throw new Error('Invalid '+description+' list.');
 return value.map(line=>validString(line,maxLength,description,{allowEmpty:true}));
}
function freezeDeep(value){
 if(value&&typeof value==='object'&&!Object.isFrozen(value)){
   for(const v of Object.values(value))freezeDeep(v);
   Object.freeze(value);
 }
 return value;
}
// Canonical hashes include the private source and rights, not arbitrary
// caller key insertion order. This local digest must never be used as a
// copyright license or substituted for a user-authorized source.
function canonical(value){
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(value&&typeof value==='object')return '{'+Object.keys(value).sort()
   .map(k=>JSON.stringify(k)+':'+canonical(value[k])).join(',')+'}';
 return JSON.stringify(value);
}
function digest(value){return createHash('sha256').update(canonical(value)).digest('hex');}
function rights(source,{scripture=false}={}){
 if(source===undefined)source={source:'unknown'};
 validObject(source,'rights');
 const origin=source.source??'unknown';
 if(!['original','licensed','unknown'].includes(origin))
   throw new Error('Unsupported content rights source.');
 if(scripture&&origin==='original')
   throw new Error('Full NKJV Scripture text must have licensed owner-provided provenance.');
 const displayAuthorized=source.displayAuthorized===true;
 const streamAuthorized=source.streamAuthorized===true;
 if(streamAuthorized&&!displayAuthorized)
   throw new Error('Streaming cannot be authorized without underlying display rights in this library.');
 const licenseId=optionalString(source.licenseId,150,'rights license');
 if(origin==='unknown'&&(displayAuthorized||streamAuthorized))
   throw new Error('Unknown content rights cannot authorize display or livestream.');
 if(origin==='licensed'&&(displayAuthorized||streamAuthorized)&&!licenseId)
   throw new Error('Licensed content requires a local permission/license reference.');
 return freezeDeep({
   source:origin,displayAuthorized,streamAuthorized,
   ...(licenseId?{licenseId}:{})
 });
}
function uniqueById(entries,description){
 const seen=new Set();
 for(const entry of entries){
   if(seen.has(entry.id))throw new Error('Duplicate '+description+' identifier: '+entry.id);
   seen.add(entry.id);
 }
}
function normalizeSong(raw){
 validObject(raw,'song');
 const songId=id(raw.id,'song');
 const title=validString(raw.title,250,'song title');
 const revision=id(raw.revision,'song revision',REVISION);
 if(!Array.isArray(raw.sections)||!raw.sections.length||raw.sections.length>100)
   throw new Error('Song requires 1 to 100 sections.');
 const sections=raw.sections.map(section=>{
   validObject(section,'song section');
   return {
     id:id(section.id,'song section'),
     label:validString(section.label,100,'song section label'),
     lines:stringList(section.lines,{description:'lyric line'}),
     notes:optionalString(section.notes,4000,'private section notes'),
     chords:stringList(section.chords??[],{max:64,maxLength:50,description:'private chords'})
   };
 });
 uniqueById(sections,'song section');
 const labels=new Set();
 for(const section of sections){
   const key=section.label.normalize('NFKC').toLowerCase().replace(/\s+/g,' ');
   if(labels.has(key))throw new Error('Duplicate song section labels are ambiguous.');
   labels.add(key);
 }
 if(!Array.isArray(raw.arrangements)||!raw.arrangements.length||raw.arrangements.length>40)
   throw new Error('Song requires at least one saved arrangement.');
 const arrangements=raw.arrangements.map(arr=>{
   validObject(arr,'song arrangement');
   const sectionIds=stringList(arr.sectionIds,{max:200,maxLength:80,description:'arrangement section IDs'});
   if(!sectionIds.length)throw new Error('Arrangement requires at least one section.');
   for(const sectionId of sectionIds){
     if(!sections.some(s=>s.id===sectionId))
       throw new Error('Arrangement references unknown song section: '+sectionId);
   }
   return {id:id(arr.id,'song arrangement'),sectionIds};
 });
 uniqueById(arrangements,'song arrangement');
 return freezeDeep({
   type:'song',id:songId,revision,title,
   rights:rights(raw.rights),
   notes:optionalString(raw.notes,4000,'private song notes'),
   key:optionalString(raw.key,80,'private musical key'),
   sections,arrangements
 });
}
function normalizeScripture(raw){
 validObject(raw,'Scripture');
 if(raw.translation!=='NKJV')throw new Error('Scripture translation must be NKJV.');
 const source=rights(raw.scriptureRights,{scripture:true});
 const reference=validString(raw.reference,150,'Scripture reference');
 if(!/^[1-3]?\s?[A-Za-z][A-Za-z ]+\s+\d{1,3}:\d{1,3}(?:-\d{1,3})?$/.test(reference))
   throw new Error('Invalid NKJV Scripture reference.');
 return freezeDeep({
   type:'scripture',id:id(raw.id,'Scripture'),
   revision:id(raw.revision,'Scripture revision',REVISION),
   title:optionalString(raw.title,250,'Scripture display title')||'Scripture Reading',
   reference,translation:'NKJV',
   text:optionalString(raw.text,7000,'owner-provided Scripture'),
   scriptureRights:source,
   notes:optionalString(raw.notes,4000,'private pastoral notes')
 });
}
function normalizeSegment(raw){
 validObject(raw,'service segment');
 if(!TYPES.has(raw.type))throw new Error('Unsupported reusable service segment type.');
 const publicAuthorized=raw.publicAuthorized===true;
 const streamAuthorized=raw.streamAuthorized===true;
 if(streamAuthorized&&!publicAuthorized)
   throw new Error('Stream segment cannot be authorized when public text is forbidden.');
 return freezeDeep({
   type:raw.type,id:id(raw.id,'segment'),
   revision:id(raw.revision,'segment revision',REVISION),
   title:validString(raw.title,250,'segment title'),
   text:optionalString(raw.text,7000,'segment public text'),
   publicAuthorized,streamAuthorized,
   notes:optionalString(raw.notes,4000,'private segment notes')
 });
}
function catalogEntries(input){
 validObject(input,'worship library');
 if(input.schema!==LIBRARY_SCHEMA)throw new Error('Unsupported worship library schema.');
 const songs=input.songs??[],scriptures=input.scriptures??[],segments=input.segments??[];
 for(const [label,items] of [['songs',songs],['scriptures',scriptures],['segments',segments]]){
   if(!Array.isArray(items)||items.length>500)throw new Error('Invalid '+label+' catalog.');
 }
 const entries=[
   ...songs.map(normalizeSong),
   ...scriptures.map(normalizeScripture),
   ...segments.map(normalizeSegment)
 ];
 if(entries.length>1500)throw new Error('Worship catalog too large.');
 // IDs are global: a plain sourceId cannot ambiguously match two categories.
 uniqueById(entries,'catalog asset');
 return entries;
}
export function createWorshipLibrary(raw){
 const entries=catalogEntries(raw);
 const index=new Map();
 const listing=[];
 for(const entry of entries){
   const contentHash=digest(entry);
   index.set(entry.id,{entry,sha256:contentHash});
   listing.push(Object.freeze({
     id:entry.id,type:entry.type==='song'?'song':entry.type==='scripture'?'scripture':'segment',
     title:entry.title,revision:entry.revision,sha256:contentHash
   }));
 }
 // Stable catalog ID independent of input map insertion and object key order.
 const digestEntries=[...listing].sort((a,b)=>a.id.localeCompare(b.id))
   .map(item=>({id:item.id,revision:item.revision,sha256:item.sha256}));
 const publicListing=Object.freeze(listing);
 const library=Object.freeze({
   schema:LIBRARY_SCHEMA,
   sha256:digest(digestEntries),
   listEntries:()=>publicListing
 });
 stores.set(library,index);
 return library;
}

function trustedSource(ref,store){
 validObject(ref,'library service item');
 const slotId=id(ref.id,'service slot',ITEM_ID);
 if(!['song','scripture','segment'].includes(ref.sourceType))
   throw new Error('A sourceType of song, scripture or segment is required.');
 const sourceId=id(ref.sourceId,'catalog source');
 const keys=new Set(['id','sourceType','sourceId','revision','sha256','arrangementId']);
 for(const key of Object.keys(ref)){
   if(!keys.has(key))throw new Error('Unexpected reference override: '+key);
 }
 const stored=store.get(sourceId);
 if(!stored)throw new Error('Unknown catalog source: '+sourceId);
 const asset=stored.entry;
 const actualType=asset.type==='song'?'song':asset.type==='scripture'?'scripture':'segment';
 if(actualType!==ref.sourceType)throw new Error('Catalog source type mismatch.');
 if(!ref.revision||!REVISION.test(ref.revision)||ref.revision!==asset.revision)
   throw new Error('Catalog source revision is missing or stale.');
 if(!SHA256.test(ref.sha256??'')||ref.sha256!==stored.sha256)
   throw new Error('Catalog source integrity SHA-256 checksum mismatch.');
 return {slotId,asset,sha256:stored.sha256,arrangementId:ref.arrangementId??null};
}

export function compileWorshipFromLibrary(plan,library,{stageGrant=null}={}){
 validObject(plan,'church service plan');
 const store=stores.get(library);
 if(!store)throw new Error('A validated offline worship library is required.');
 const title=validString(plan.title,240,'service title');
 if(!Array.isArray(plan.items)||!plan.items.length||plan.items.length>150)
   throw new Error('Service requires 1 to 150 ordered items.');
 const expanded=[],usedSlots=new Set();
 // The compiler owns an exact slide-ID to source/rights table at emission time.
 // Never infer identity later using first-match prefixes: an otherwise valid
 // segment ID such as opening-s1-p2 can look like a page of song opening.
 const plannedOwners=new Map(),plannedSlideIds=[];
 const ownSlide=(slideId,slotId,source,streamAllowed,extra={})=>{
   if(plannedOwners.has(slideId))
     throw new Error('Ambiguous generated slide ownership collision: '+slideId);
   if(plannedSlideIds.length>=1000)
     throw new Error('Service exceeds 1000 slides.');
   const provenance=Object.freeze({
     slotId,assetId:source.assetId,sourceType:source.sourceType,
     revision:source.revision,sha256:source.sha256,
     ...(source.arrangementId?{arrangementId:source.arrangementId}:{}),
     ...extra
   });
   plannedOwners.set(slideId,Object.freeze({provenance,streamAllowed}));
   plannedSlideIds.push(slideId);
 };
 const add=({slotId,asset,sha256,arrangementId})=>{
   if(usedSlots.has(slotId))throw new Error('Duplicate service slot identifier: '+slotId);
   usedSlots.add(slotId);
   const source={assetId:asset.id,sourceType:asset.type,revision:asset.revision,
     sha256,arrangementId};
   if(asset.type==='song'){
     if(typeof arrangementId!=='string')
       throw new Error('A named saved song arrangement is required.');
     const arrangement=asset.arrangements.find(a=>a.id===arrangementId);
     if(!arrangement)throw new Error('Unknown saved song arrangement: '+arrangementId);
     const sections=new Map(asset.sections.map(s=>[s.id,s]));
     const order=arrangement.sectionIds.map(sectionId=>sections.get(sectionId).label);
     expanded.push({
       id:slotId,type:'song',title:asset.title,rights:asset.rights,
       notes:asset.notes,key:asset.key,
       sections:asset.sections.map(s=>({
         label:s.label,lines:s.lines,notes:s.notes,chords:s.chords
       })),order
     });
     // Register each compiled page with its exact owner and medium rights
     // BEFORE rendering. Section IDs and repeat occurrences come directly
     // from the saved arrangement, not from a later fuzzy string search.
     const occurrences=new Map();
     for(let sectionIndex=0;sectionIndex<arrangement.sectionIds.length;sectionIndex++){
       const sectionId=arrangement.sectionIds[sectionIndex];
       const section=sections.get(sectionId);
       const occurrence=(occurrences.get(sectionId)??0)+1;
       occurrences.set(sectionId,occurrence);
       const pageCount=Math.max(1,Math.ceil(section.lines.length/2));
       for(let page=1;page<=pageCount;page++){
         const slideId=slotId+'-s'+String(sectionIndex+1)+'-p'+String(page);
         ownSlide(slideId,slotId,source,asset.rights.streamAuthorized===true,
           {sectionId,occurrence,page});
       }
     }
     return;
   }
   if(arrangementId!==null)
     throw new Error('Saved arrangements apply only to songs.');
   if(asset.type==='scripture'){
     expanded.push({
       id:slotId,type:'scripture',title:asset.title,reference:asset.reference,
       translation:asset.translation,text:asset.text,
       scriptureRights:asset.scriptureRights,notes:asset.notes
     });
     ownSlide(slotId,slotId,source,asset.scriptureRights.streamAuthorized===true);
     return;
   }
   expanded.push({
     id:slotId,type:asset.type,title:asset.title,
     text:asset.publicAuthorized?asset.text:'',
     notes:asset.notes
   });
   ownSlide(slotId,slotId,source,asset.streamAuthorized===true);
 };
 for(const ref of plan.items){
   add(trustedSource(ref,store));
 }
 const compiled=compileWorshipService({title,theme:plan.theme,items:expanded},{stageGrant});
 // The lower-level compiler may evolve. Accept output only if the actual
 // public and broadcast slide IDs appear in the same, exactly predeclared
 // sequence. Any unknown, duplicated or reordered ID fails closed.
 if(compiled.publicDeck.slides.length!==plannedSlideIds.length||
    compiled.broadcastDeck.slides.length!==plannedSlideIds.length)
   throw new Error('Compiled slide ownership sequence mismatch.');
 const privateSourceMap=new Map(),streamAllowedByIndex=new Map();
 for(let index=0;index<plannedSlideIds.length;index++){
   const expectedId=plannedSlideIds[index];
   const audienceSlide=compiled.publicDeck.slides[index];
   const broadcastSlide=compiled.broadcastDeck.slides[index];
   const owner=plannedOwners.get(expectedId);
   if(!owner||audienceSlide?.id!==expectedId||broadcastSlide?.id!==expectedId)
     throw new Error('Compiled slide identity or source ownership mismatch.');
   privateSourceMap.set(index,owner.provenance);
   streamAllowedByIndex.set(index,owner.streamAllowed);
 }
 const broadcastDeck=Object.freeze({
   title:compiled.broadcastDeck.title,
   theme:compiled.broadcastDeck.theme,
   slides:Object.freeze(compiled.broadcastDeck.slides.map((slide,index)=>{
     if(streamAllowedByIndex.get(index)===true)return slide;
     // Rights attach to the exact compiler-owned slide position, never an
     // earlier song-shaped prefix. Mask any medium not explicitly granted.
     return Object.freeze({...slide,text:''});
   }))
 });
 const stageAllowed=compiled.stageAvailable===true;
 // A local, out-of-band stage grant is required for provenance and private
 // confidence data. These functions cannot serialize into a public deck.
 const getCueSource=(index,providedGrant)=>{
   if(!stageAllowed||typeof providedGrant!=='string'||providedGrant!==stageGrant||
      !Number.isInteger(index))return null;
   const found=privateSourceMap.get(index);
   return found?structuredClone(found):null;
 };
 return Object.freeze({
   schema:COMPILE_SCHEMA,
   publicDeck:compiled.publicDeck,broadcastDeck,
   rundown:compiled.rundown,issues:compiled.issues,
   stageAvailable:stageAllowed,
   getStageCue:compiled.getStageCue,
   getCueSource
 });
}

export {WorshipLibraryStore,buildServiceFromWorshipLibrary} from './worship-legacy-bridge.mjs';
