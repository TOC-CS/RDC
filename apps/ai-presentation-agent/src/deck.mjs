import {randomBytes} from 'node:crypto';
function escapeHtml(value){
 return String(value??'').replace(/[&<>"']/g,
   ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
export function buildDeck({title='Presentation',sections=[],theme='dark',subtitle=''}={}){
 if(typeof title!=='string'||title.length>300)throw new Error('Invalid presentation title.');
 if(!Array.isArray(sections)||sections.length>999)throw new Error('Too many sections.');
 if(!['dark','light'].includes(theme))throw new Error('Theme must be dark or light.');
 const slides=[{id:'title',title,text:String(subtitle).slice(0,1500),kind:'title'}];
 for(let index=0;index<sections.length;index++){
   const section=sections[index];
   if(!section||typeof section.title!=='string'||section.title.length>250||
      (section.points!==undefined&&(!Array.isArray(section.points)||section.points.length>12)))
     throw new Error('Invalid section.');
   const text=(section.points??[]).map(v=>{
     if(typeof v!=='string'||v.length>500)throw new Error('Section points too long.');
     return v;
   }).join('\n');
   slides.push({id:'section-'+String(index+1),title:section.title,text,kind:section.kind??'content',
     cues:section.cues??[],section:section.section??null,song:section.song??null,reference:section.reference??null,
     scene:section.scene??null,...(section.occurrence===undefined?{}:{occurrence:section.occurrence})});
 }
 return {title,theme,slides};
}
export function renderDeckHtml(deck,{liveEventsPath=null,deckVersion=null}={}){
 if(!deck||!Array.isArray(deck.slides)||deck.slides.length===0||deck.slides.length>1000)
   throw new Error('Deck with slides required.');
 const title=escapeHtml(deck.title??'Presentation');
 const theme=deck.theme==='light'?'light':'dark';
 const nonce=randomBytes(18).toString('base64');
 const slides=deck.slides.map((slide,i)=>'<section class="slide" data-index="'+i+'" id="slide-'+i+'" role="group" aria-label="Slide '+(i+1)+'">'+
   '<div class="count">'+(i+1)+' / '+deck.slides.length+'</div>'+
   '<h1>'+escapeHtml(slide.title)+'</h1>'+
   '<p class="slide-text">'+escapeHtml(slide.text??'')+'</p>'+
   (slide.reference?'<div class="reference">'+escapeHtml(slide.reference)+'</div>':'')+
   '</section>').join('\n');
 const liveViewer=typeof liveEventsPath==='string'&&liveEventsPath.startsWith('/v1/view-events?key=');
 const navigation=liveViewer?
   "document.getElementById('prev').hidden=true;document.getElementById('next').hidden=true;" :
   "document.addEventListener('keydown',event=>{if(['ArrowRight','ArrowDown','PageDown',' '].includes(event.key)){event.preventDefault();advance(1)}else if(['ArrowLeft','ArrowUp','PageUp'].includes(event.key)){event.preventDefault();advance(-1)}});"+
   "document.getElementById('prev').addEventListener('click',()=>advance(-1));"+
   "document.getElementById('next').addEventListener('click',()=>advance(1));"+
   "window.addEventListener('message',event=>{if(event.origin!==location.origin||!event.data||event.data.type!=='presentation.goto'||!Number.isInteger(event.data.index))return;active=event.data.index;advance(0)});";
 const js="let active=0;const slides=[...document.querySelectorAll('.slide')];"+
   "function advance(n){active=Math.max(0,Math.min(slides.length-1,active+n));slides.forEach((s,i)=>{s.hidden=i!==active;s.setAttribute('aria-hidden',String(i!==active))});document.getElementById('progress').textContent=(active+1)+' / '+slides.length;}"+
   navigation+"advance(0);";
 // Browser output receives actual director updates, rather than changing
 // only the exported file's internal slide counter.
 const liveScript=typeof liveEventsPath==='string'&&liveEventsPath.startsWith('/v1/view-events?key=')?
   "const liveEvents=new EventSource("+JSON.stringify(liveEventsPath)+");"+
   "const expectedDeck="+JSON.stringify(deckVersion)+";"+
   "liveEvents.onmessage=event=>{try{const state=JSON.parse(event.data);"+
   "if(state.loaded===false){const main=document.querySelector('main');main?.replaceChildren();if(main)main.setAttribute('aria-label','Presentation Cleared');document.title='Presentation Cleared';document.body.dataset.connection='cleared';document.body.dataset.visibility='visible';document.getElementById('progress').textContent='';document.getElementById('session-status').textContent='PRESENTATION CLEARED';return;}"+
   "if(expectedDeck&&state.deckVersion!==expectedDeck){window.location.reload();return;}"+
   "if(Number.isInteger(state.index)){active=state.index;advance(0);}"+
   "if(state.look){const layers=Array.isArray(state.look.layers)?state.look.layers:[];"+
   "document.body.dataset.look=['fullscreen','minimal'].includes(state.look.layout)?state.look.layout:'fullscreen';"+
   "for(const slide of slides){for(const [selector,layer] of [['h1','title'],['.slide-text','text'],['.reference','reference']]){const part=slide.querySelector(selector);if(part)part.hidden=!layers.includes(layer);}}}"+
   "document.body.dataset.visibility=['visible','clear','blank'].includes(state.look?.visibility)?state.look.visibility:'visible';"+
   "document.body.dataset.outputFaulted=String(state.outputFaulted===true);"+
   "document.body.dataset.held=String(state.held===true);"+
   "const label=state.outputFaulted?'OUTPUT UNVERIFIED, HOLD':state.recoveryPreview?'RECOVERED PREVIEW':!state.started?'NOT STARTED':state.dryRun?'PREVIEW ONLY':state.held?'HELD':'LIVE';"+
   "document.getElementById('session-status').textContent=label;}catch{}};"+
   "liveEvents.onerror=()=>{document.body.dataset.connection='reconnecting';document.getElementById('session-status').textContent='RECONNECTING';};"+
   "liveEvents.onopen=()=>{document.body.dataset.connection='connected';};" : "";
 const css=":root{color-scheme:"+theme+";font-family:system-ui,-apple-system,Arial,sans-serif}*{box-sizing:border-box}body{margin:0;background:"+(theme==='dark'?'#081326':'#f4f7fb')+";color:"+(theme==='dark'?'#f2f8ff':'#182432')+"}.slide{min-height:100vh;width:100vw;padding:8vh 8vw;display:flex;flex-direction:column;justify-content:center;gap:1rem}.slide[hidden]{display:none}body[data-visibility=blank]{background:#000!important;color:#000!important}body[data-visibility=blank] main,body[data-visibility=blank] footer{visibility:hidden}body[data-visibility=clear] main{visibility:hidden}body[data-look=minimal] .count{display:none}body[data-look=minimal] h1{font-size:clamp(1.4rem,3vw,3.6rem)}.count{letter-spacing:.25em;font-size:clamp(.75rem,1.4vw,1.1rem);opacity:.65}h1{font-size:clamp(2.6rem,7vw,8rem);line-height:1.05;max-width:90vw;letter-spacing:-.03em;margin:0}p.slide-text{font-size:clamp(1.3rem,3vw,3.2rem);white-space:pre-line;line-height:1.45;max-width:82vw;margin:0}.reference{font-size:1.2rem;opacity:.7}footer{position:fixed;bottom:1.2rem;right:1.2rem;display:flex;gap:.75rem;align-items:center;opacity:.65}button{cursor:pointer;background:transparent;border:1px solid currentColor;border-radius:8px;color:inherit;padding:.4rem 1rem;font-size:1rem}button[hidden]{display:none}@media print{footer{display:none}.slide{page-break-after:always}}";
 const csp="default-src 'none'; style-src 'nonce-"+nonce+"'; script-src 'nonce-"+nonce+"'; img-src 'none'; connect-src "+(liveEventsPath?"'self'":"'none'")+"; object-src 'none'; base-uri 'none'; frame-ancestors 'none'";
 return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><meta http-equiv="Content-Security-Policy" content="'+csp+'"><title>'+title+'</title><style nonce="'+nonce+'">'+css+'</style></head>'+
 '<body><main aria-label="'+title+'">'+slides+'</main><footer><span id="session-status" aria-live="polite">'+(liveEventsPath?'CONNECTING':'OFFLINE DECK')+'</span><button id="prev" aria-label="Previous slide">←</button><span id="progress"></span><button id="next" aria-label="Next slide">→</button></footer><script nonce="'+nonce+'">'+js+liveScript+'</script></body></html>';
}
