/**
 * Original ProPresenter-independent output Look compiler.
 *
 * Source is a trusted, already rights-filtered compileWorshipService result;
 * incoming browser/API requests cannot supply private note content or
 * override source fields. Returns detached immutable destination-specific
 * packets with allowlisted layers only. Does not control external displays.
 */
const ALLOWED=Object.freeze({
 audience:new Set(['title','text','reference']),
 broadcast:new Set(['title','text','reference']),
 stage:new Set(['title','text','reference','section','next','notes','chords','key','timer'])
});
const LAYOUTS=Object.freeze({
 audience:new Set(['fullscreen','minimal']),
 broadcast:new Set(['lower-third','minimal']),
 stage:new Set(['confidence'])
});
const DEFAULTS=Object.freeze({
 audience:Object.freeze({layout:'fullscreen',background:'dark',layers:['title','text','reference']}),
 broadcast:Object.freeze({layout:'lower-third',background:'transparent',layers:['title','text','reference']}),
 stage:Object.freeze({layout:'confidence',background:'dark',
   layers:['title','text','section','next','notes','chords','timer']})
});
const BACKGROUNDS=new Set(['dark','light','transparent']);
const scalar=value=>typeof value==='string'?value:'';
const isPlain=value=>value&&typeof value==='object'&&!Array.isArray(value)&&
  [Object.prototype,null].includes(Object.getPrototypeOf(value));
export function validateWorshipLook(destination,config=null){
 if(!Object.hasOwn(DEFAULTS,destination))
   throw new Error('Invalid worship Look destination.');
 if(config!==null&&!isPlain(config))
   throw new Error('Invalid worship Look configuration.');
 const chosen=config??DEFAULTS[destination];
 for(const key of Object.keys(chosen))
   if(!['layout','background','layers'].includes(key))
     throw new Error('Unknown worship Look field: '+key);
 const layout=chosen.layout??DEFAULTS[destination].layout;
 if(!LAYOUTS[destination].has(layout))
   throw new Error('Worship Look layout is not allowed for this destination.');
 const background=chosen.background??DEFAULTS[destination].background;
 if(!BACKGROUNDS.has(background)||
    (background==='transparent'&&destination!=='broadcast'))
   throw new Error('Invalid worship Look background.');
 const layers=chosen.layers??DEFAULTS[destination].layers;
 if(!Array.isArray(layers)||layers.length>12||layers.length===0||
    layers.some(layer=>typeof layer!=='string'))
   throw new Error('Invalid worship Look layer list.');
 const unique=new Set(layers);
 if(unique.size!==layers.length)throw new Error('Duplicate worship Look layer.');
 for(const layer of layers)if(!ALLOWED[destination].has(layer))
   throw new Error('Layer '+layer+' is not allowed for '+destination+' output.');
 return Object.freeze({destination,layout,background,layers:Object.freeze([...layers])});
}
export function compileWorshipLook(service,{destination,index,stageGrant=null,look=null}={}){
 if(!service||!['toc.worship-service/v1','toc.worship-library-compilation/v1'].includes(service.schema)||!Object.isFrozen(service)||
    !service.publicDeck||!service.broadcastDeck||
    !Array.isArray(service.publicDeck.slides)||
    !Array.isArray(service.broadcastDeck.slides)||
    service.publicDeck.slides.length!==service.broadcastDeck.slides.length||
    typeof service.getStageCue!=='function')
   throw new Error('A validated compiled worship session is required.');
 const config=validateWorshipLook(destination,look);
 const count=service.publicDeck.slides.length;
 if(!Number.isSafeInteger(index)||index<0||index>=count)
   throw new Error('Worship Look index out of range.');
 let slide,next=null;
 if(destination==='stage'){
   const stage=service.getStageCue(index,stageGrant);
   if(!stage)throw new Error('Private stage authorization required.');
   slide=stage;
   next=stage.next??null;
 }else if(destination==='audience')slide=service.publicDeck.slides[index];
 else slide=service.broadcastDeck.slides[index];
 // Never copy arbitrary source keys or notes into public packets. The
 // source compiler already restricted rights per asset and destination.
 const id=scalar(slide.id),current={
   id,
   title:scalar(slide.title),
   text:scalar(slide.text),
   ...((destination==='stage')?{section:scalar(slide.section)}:{}),
   ...((destination!=='stage'&&slide.reference)?{reference:scalar(slide.reference)}:{})
 };
 const readLayer=layer=>{
   if(layer==='title')return current.title;
   if(layer==='text')return current.text;
   if(layer==='reference')return current.reference??'';
   if(layer==='section')return scalar(slide.section);
   if(layer==='notes')return scalar(slide.notes);
   if(layer==='key')return scalar(slide.key);
   if(layer==='chords')return Object.freeze(
     Array.isArray(slide.chords)?slide.chords.filter(v=>typeof v==='string').map(scalar):[]);
   if(layer==='next')return scalar(next?.text);
   if(layer==='timer')return ''; // live timer exists only in the stage-token-gated control path
   throw new Error('Unsupported internal worship layer.');
 };
 const layers={};
 for(const layer of config.layers)layers[layer]=readLayer(layer);
 return Object.freeze({
   schema:'toc.worship-look-packet/v1',destination,layout:config.layout,
   background:config.background,slideId:id,index,
   current:Object.freeze(current),layers:Object.freeze(layers)
 });
}
