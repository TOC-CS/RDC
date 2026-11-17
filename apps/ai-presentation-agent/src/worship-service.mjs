/**
 * Pure, offline worship service compiler. ProPresenter is never required.
 *
 * Privacy is enforced by constructing new, purpose-specific objects from a
 * whitelist. No source object spread, private field or stage reference enters
 * the public decks. A stage cue is available only through a locally granted
 * function; a remote stage endpoint needs its own separate authentication.
 */
const ID=/^[a-zA-Z][a-zA-Z0-9._-]{0,79}$/;
const TYPES=new Set(['song','scripture','countdown','announcement','sermon','prayer','closing','media','title']);
const clampText=(value,max,label,{optional=false}={})=>{
 if(optional&&value==null)return '';
 if(typeof value!=='string'||value.length>max)throw new Error('Invalid '+label);
 return value.trim();
};
const id=(value,label)=>{
 if(typeof value!=='string'||!ID.test(value))throw new Error('Invalid '+label+' identifier.');
 return value;
};
const privateNote=value=>typeof value==='string'?value.slice(0,4000):'';
const safeShort=(text,max=500)=>String(text??'').slice(0,max);
const publicSlide=(data)=>{
 const out={
   id:id(data.id,'slide'),
   title:clampText(data.title,250,'public title'),
   text:clampText(data.text??'',8000,'public slide text'),
   kind:clampText(data.kind??'content',60,'public kind'),
 };
 for(const key of ['song','section','reference']){
   if(typeof data[key]==='string'&&data[key].length)
     out[key]=clampText(data[key],200,key);
 }
 if(Number.isSafeInteger(data.occurrence)&&data.occurrence>=1)out.occurrence=data.occurrence;
 return Object.freeze(out);
};
const normalizeSectionKey=value=>String(value).trim().normalize('NFKC').toLowerCase().replace(/\s+/g,' ');
const trimLine=line=>clampText(line,240,'song lyric line');
const hasDisplayRights=rights=>rights?.source==='original'&&rights.displayAuthorized===true||
 rights?.displayAuthorized===true&&typeof rights.source==='string'&&rights.source!=='unknown'&&
 typeof rights.licenseId==='string'&&rights.licenseId.trim().length>0;
// In-room display and public livestream are independent authorizations.
// Even owner-authored content needs an explicit stream permission in a plan.
const hasStreamRights=rights=>hasDisplayRights(rights)&&rights.streamAuthorized===true;

export function compileWorshipService(plan,{stageGrant=null}={}){
 if(!plan||typeof plan!=='object'||Array.isArray(plan))
   throw new Error('Worship service plan object required.');
 const title=clampText(plan.title,240,'service title');
 if(!title)throw new Error('A service title is required.');
 if(!['dark','light',undefined].includes(plan.theme))
   throw new Error('Unsupported worship service theme.');
 if(!Array.isArray(plan.items)||plan.items.length<1||plan.items.length>150)
   throw new Error('Worship service requires 1 to 150 ordered items.');
 const usedIds=new Set();
 const audience=[],stream=[],stage=[],rundown=[],issues=[];
 const publish=(slide,privateProps={},broadcast={})=>{
   const publicData=publicSlide(slide);
   if(usedIds.has(publicData.id))throw new Error('Duplicate generated service slide ID: '+publicData.id);
   usedIds.add(publicData.id);
   if(audience.length>=1000)throw new Error('Service exceeds 1000 slides.');
   const broadcastSlide=publicSlide({
     id:publicData.id,title:safeShort(broadcast.title??publicData.title,250),
     text:broadcast.text??publicData.text,
     kind:publicData.kind,
     song:publicData.song,
     section:publicData.section,
     occurrence:publicData.occurrence,
     reference:publicData.reference
   });
   audience.push(publicData);stream.push(broadcastSlide);
   stage.push(Object.freeze({
     id:publicData.id,
     title:publicData.title,
     text:publicData.text,
     song:publicData.song??null,
     section:publicData.section??null,
     occurrence:publicData.occurrence??null,
     notes:privateNote(privateProps.notes),
     chords:Array.isArray(privateProps.chords)?
       Object.freeze(privateProps.chords.map(v=>safeShort(v,50))):Object.freeze([]),
     key:privateNote(privateProps.key),
   }));
 };
 for(const item of plan.items){
   if(!item||typeof item!=='object'||Array.isArray(item))throw new Error('Invalid service item.');
   const itemId=id(item.id,'service item');
   const type=clampText(item.type,40,'item type');
   if(!TYPES.has(type))throw new Error('Unsupported worship service item: '+type);
   const itemTitle=clampText(item.title,250,'item title');
   if(!itemTitle)throw new Error('Service item needs a title.');
   rundown.push(Object.freeze({id:itemId,type,title:itemTitle}));
   if(type==='song'){
     if(!Array.isArray(item.sections)||item.sections.length<1||item.sections.length>100)
       throw new Error('Song must define 1 to 100 lyric sections.');
     if(!Array.isArray(item.order)||item.order.length<1||item.order.length>200)
       throw new Error('Song must define an arrangement of 1 to 200 sections.');
     const sectionMap=new Map();
     for(const section of item.sections){
       if(!section||typeof section!=='object'||Array.isArray(section))
         throw new Error('Invalid song lyric section.');
       const label=clampText(section.label,100,'section label');
       const key=normalizeSectionKey(label);
       if(!label||sectionMap.has(key))throw new Error('Duplicate or empty song lyric section.');
       if(!Array.isArray(section.lines)||section.lines.length>80||
          section.lines.some(line=>typeof line!=='string'||line.length>240))
         throw new Error('Song lyrics require at most 80 valid lines per section.');
       sectionMap.set(key,section);
     }
     const rights=hasDisplayRights(item.rights);
     const streamRights=hasStreamRights(item.rights);
     if(!rights)issues.push(Object.freeze({type:'lyrics_rights',itemId}));
     if(rights&&!streamRights)issues.push(Object.freeze({type:'livestream_lyrics_rights',itemId}));
     const counts=new Map();
     for(let i=0;i<item.order.length;i++){
       const key=normalizeSectionKey(item.order[i]);
       const section=sectionMap.get(key);
       if(!section)throw new Error('Song arrangement references unknown section: '+key);
       const occurrence=(counts.get(key)??0)+1;counts.set(key,occurrence);
       const rawLines=section.lines.map(trimLine);
       const pages=[];
       for(let offset=0;offset<Math.max(1,rawLines.length);offset+=2)
         pages.push(rawLines.slice(offset,offset+2).join('\n'));
       for(let page=0;page<pages.length;page++){
         const identifier=itemId+'-s'+String(i+1)+'-p'+String(page+1);
         publish({
           id:identifier,
           title:itemTitle,
           text:rights?pages[page]:'',
           kind:'song',song:itemTitle,section:section.label,occurrence
         },{
           notes:section.notes??item.notes,
           chords:section.chords,
           key:item.key
         },{
           // The camera overlay is separate from stage notes and can be
           // omitted when stream rights differ from room display rights.
           title:itemTitle,text:streamRights?pages[page]:''
         });
       }
     }
     continue;
   }
   const base={id:itemId,title:itemTitle,kind:type,text:''};
   let broadcastText='';
   if(type==='scripture'){
     const reference=clampText(item.reference,150,'Scripture reference');
     if(!reference||!/^[1-3]?\s?[A-Za-z][A-Za-z ]+\s+\d{1,3}:\d{1,3}(?:-\d{1,3})?$/.test(reference))
       throw new Error('A valid Scripture reference is required.');
     if(item.translation!==undefined&&item.translation!=='NKJV')
       throw new Error('This worship plan uses NKJV only.');
     base.reference=reference;
     const source=item.scriptureRights;
     const rights=source?.displayAuthorized===true&&typeof source.source==='string'&&
       source.source.length>0&&source.source!=='unknown';
     base.text=rights?clampText(item.text??'',7000,'authorized Scripture text'):'';
     broadcastText=rights&&source.streamAuthorized===true?base.text:'';
     if(!rights)issues.push(Object.freeze({type:'scripture_reference_only',itemId}));
   }else{
     base.text=clampText(item.text??'',7000,'service public text');
     broadcastText=base.text;
   }
   publish(base,{notes:item.notes,chords:item.chords,key:item.key},{text:broadcastText});
 }
 const publicDeck=Object.freeze({
   title,theme:plan.theme==='light'?'light':'dark',
   slides:Object.freeze(audience)
 });
 const broadcastDeck=Object.freeze({
   title,theme:publicDeck.theme,slides:Object.freeze(stream)
 });
 // Local-only private stage view. Never serialize this callable into any
 // public deck, REST, SSE or OBS result.
 const granted=typeof stageGrant==='string'&&stageGrant.length>0;
 const getStageCue=(index,providedGrant)=>{
   if(!granted||providedGrant!==stageGrant||!Number.isInteger(index)||
       index<0||index>=stage.length)return null;
   const current=stage[index],next=stage[index+1]??null;
   return structuredClone({
     ...current,
     next:next?{id:next.id,title:next.title,text:next.text,
       section:next.section,occurrence:next.occurrence}:null
   });
 };
 return Object.freeze({
   schema:'toc.worship-service/v1',
   publicDeck,broadcastDeck,
   rundown:Object.freeze(rundown),
   issues:Object.freeze(issues),
   stageAvailable:granted,
   getStageCue
 });
}
