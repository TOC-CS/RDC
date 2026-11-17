/**
 * Source-bound service rundown for an authorized local operator.
 *
 * Pure metadata: never returns full lyrics, licensed Bible text, stage chords,
 * private pastoral notes, credentials, comments, physical device controls,
 * venue timing guesses or any source reference with unvalidated fields.
 */
const SCHEMAS=new Set(['toc.worship-service/v1','toc.worship-library-compilation/v1']);
const MODES=new Set(['manual','assisted','automatic']);
const OUTPUTS=new Set(['audience','stage','broadcast']);
const safeString=(v,max=250)=>typeof v==='string'?v.slice(0,max):'';
const publicCue=slide=>slide?Object.freeze({
 id:safeString(slide.id,80),
 title:safeString(slide.title),
 kind:safeString(slide.kind,60),
 ...(typeof slide.song==='string'?{song:safeString(slide.song,200)}:{}),
 ...(typeof slide.section==='string'?{section:safeString(slide.section,100)}:{}),
 ...(Number.isSafeInteger(slide.occurrence)&&slide.occurrence>=1?{occurrence:slide.occurrence}:{}),
 ...(typeof slide.reference==='string'?{reference:safeString(slide.reference,150)}:{})
}):null;
export function buildWorshipOperatorRundown(service,{
 index=0,started=false,held=false,mode='manual',outputFaulted=false,
 looks=null,visibility=null
}={}){
 if(!service||typeof service!=='object'||!SCHEMAS.has(service.schema)||
   !Object.isFrozen(service)||!service.publicDeck||
   !Array.isArray(service.publicDeck.slides)||
   !Array.isArray(service.rundown))
   throw new Error('A validated compiled worship service is required.');
 const slides=service.publicDeck.slides;
 if(!Number.isSafeInteger(index)||index<0||index>=slides.length)
   throw new Error('Worship rundown index out of range.');
 if(!MODES.has(mode)||typeof started!=='boolean'||typeof held!=='boolean'||
    typeof outputFaulted!=='boolean')
   throw new Error('Invalid worship rundown status or mode.');
 const items=Object.freeze(service.rundown.map(item=>Object.freeze({
   id:safeString(item.id,80),
   type:safeString(item.type,60),
   title:safeString(item.title,250)
 })));
 const safeLooks=Array.isArray(looks?.destinations)?
   looks.destinations.filter(item=>OUTPUTS.has(item?.destination))
    .map(item=>Object.freeze({
      destination:item.destination,
      layout:safeString(item.layout,60),
      background:safeString(item.background,40),
      layers:Object.freeze(Array.isArray(item.layers)?
       item.layers.filter(v=>typeof v==='string').map(v=>v.slice(0,50)):[])
    })): [];
 const safeVisibility=Array.isArray(visibility?.outputs)?
   visibility.outputs.filter(item=>OUTPUTS.has(item?.destination))
    .map(item=>Object.freeze({
      destination:item.destination,
      mode:['visible','clear','blank'].includes(item.mode)?item.mode:'unknown'
    })): [];
 return Object.freeze({
   schema:'toc.worship.operator-rundown/v1',
   index,current:publicCue(slides[index]),next:publicCue(slides[index+1]??null),
   slidesRemaining:Math.max(0,slides.length-index-1),
   totalSlides:slides.length,
   items,
   looks:Object.freeze(safeLooks),
   visibility:Object.freeze(safeVisibility),
   status:Object.freeze({started,held,mode,outputFaulted}),
   nativeProjectionVerified:false,broadcastProviderVerified:false,
   externalWritesPerformed:false,privateStageDataIncluded:false
 });
}
