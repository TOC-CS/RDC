import {randomBytes} from 'node:crypto';

// Stage HTML is only a shell. Notes/chords arrive through stage-only SSE,
// never via public deck, public SSE, or the initial document.
export function renderStageConfidenceHtml({eventsPath}={}){
 if(typeof eventsPath!=='string'||!eventsPath.startsWith('/v1/stage-events?key=')||
    eventsPath.length>1000)throw new Error('Stage SSE source must be explicit and local.');
 const nonce=randomBytes(16).toString('base64');
 const css=[
  ':root{color-scheme:dark;font-family:system-ui,-apple-system,Arial,sans-serif}',
  '*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#090f1b;color:#f5f7ff;padding:3vw}',
  'header{display:flex;justify-content:space-between;align-items:center;font-size:clamp(.9rem,1.4vw,1.5rem);color:#bac6d5}',
  '.layout{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:3vw;min-height:70vh;margin-top:2rem}',
  'section{border:1px solid #2e3849;border-radius:1rem;padding:3vw;min-width:0}',
  'h1{font-size:clamp(2.2rem,5vw,6rem);line-height:1.06;margin:.4em 0}',
  'h2{font-size:clamp(1.2rem,2.5vw,2.8rem)}',
  '.cue{white-space:pre-line;line-height:1.4;font-size:clamp(1.4rem,2.8vw,3rem)}',
  '.next{white-space:pre-line;font-size:clamp(1.15rem,2vw,2.2rem);line-height:1.35}',
  '.private{font-size:clamp(1rem,1.7vw,1.8rem);white-space:pre-line;overflow-wrap:anywhere;color:#ffdb9b}',
  '.muted{opacity:.7}#status[data-fault=true]{color:#ff9494}',
  '#stage-clock{display:flex;gap:.75rem;align-items:baseline;font-variant-numeric:tabular-nums;color:#d9ecff}',
  '#timer-remaining{font-size:clamp(1rem,2vw,2rem);font-weight:750}',
  '#timer-label{font-size:clamp(.9rem,1.2vw,1.3rem);opacity:.8}',
  '#teleprompt{margin:2rem 0 0;border:1px solid #45617f;border-radius:1rem;padding:1.6rem;background:#0b182a}',
  '#teleprompt[hidden]{display:none}',
  '#teleprompt-role{font-size:1rem;color:#a9cde8;letter-spacing:.08em}',
  '#teleprompt-current{font-size:var(--prompt-size,1.3rem);line-height:1.4;white-space:pre-line;overflow-wrap:anywhere;transition:transform var(--scroll-seconds,1s) ease}',
  '#teleprompt-next{font-size:1rem;opacity:.72;white-space:pre-line;overflow-wrap:anywhere}',
  '#teleprompt[data-mirrored=true] .teleprompt-line{transform:scaleX(-1)}',
  '@media(max-width:720px){.layout{grid-template-columns:1fr}.cue{font-size:clamp(1.5rem,5vw,2.6rem)}}'
 ].join('');
 const js=[
  "const bind=(id,text)=>{document.getElementById(id).textContent=String(text??'')};",
  "const feed=new EventSource("+JSON.stringify(eventsPath)+");",
  "const render=state=>{",
  "if(!state||state.loaded===false||!state.current){",
  "for(const id of ['title','current','next','chords','private-notes','section','timer-label','timer-remaining','teleprompt-role','teleprompt-current','teleprompt-next','teleprompt-progress'])bind(id,'');",
  "bind('teleprompt-current','');bind('teleprompt-next','');",
  "document.getElementById('teleprompt').hidden=true;",
  "bind('status','CLEAR / NO SERVICE');document.body.dataset.active='false';return;}",
  "document.body.dataset.active='true';",
  "document.body.dataset.look=state.look?.layout==='confidence'?'confidence':'confidence';",
  "document.body.dataset.visibility=state.visibility==='clear'?'clear':'visible';",
  "bind('title',state.current.title);bind('current',state.current.text);",
  "bind('next',state.next?.text??'');",
  "bind('chords',Array.isArray(state.current.chords)?state.current.chords.join('  '):'');",
  "bind('private-notes',state.current.notes);bind('section',state.current.section??'');",
  "const clock=state.clock;",
  "if(clock&&Number.isFinite(clock.remainingMs)){const sec=Math.ceil(clock.remainingMs/1000);",
  "bind('timer-remaining',String(Math.floor(sec/60)).padStart(2,'0')+':'+String(sec%60).padStart(2,'0'));",
  "bind('timer-label',clock.label??'');}else{bind('timer-label','');bind('timer-remaining','');}",
  "const fault=state.outputFaulted===true;",
  "const prompt=state.teleprompt;const prompter=document.getElementById('teleprompt');",
  "if(prompt&&prompt.loaded&&state.visibility!=='clear'&&!fault){",
  "prompter.hidden=false;prompter.dataset.mirrored=String(prompt.mirrored===true);",
  "const fontScale=Math.max(.8,Math.min(2.6,Number(prompt.fontScale)||1.3));",
  "const scrollSpeed=Math.max(.25,Math.min(3,Number(prompt.scrollSpeed)||1));",
  "prompter.style.setProperty('--prompt-size',String(fontScale)+'rem');",
  "prompter.style.setProperty('--scroll-seconds',String(scrollSpeed)+'s');",
  "bind('teleprompt-role',String(prompt.role??'speaker').toUpperCase());",
  "bind('teleprompt-current',prompt.current);bind('teleprompt-next',prompt.next);",
  "bind('teleprompt-progress',String(Math.round((Number(prompt.progress)||0)*100))+'%');",
  "}else{prompter.hidden=true;bind('teleprompt-current','');bind('teleprompt-next','');}",
  "bind('status',fault?'OUTPUT UNVERIFIED':state.visibility==='clear'?'STAGE CLEARED':state.held?'HELD':state.started?'STAGE LIVE':'PREVIEW ONLY');",
  "document.getElementById('status').dataset.fault=String(fault);};",
  "feed.onmessage=event=>{try{render(JSON.parse(event.data))}catch{bind('status','STAGE DATA ERROR')}};",
  "feed.onerror=()=>{bind('teleprompt-current','');bind('teleprompt-next','');bind('private-notes','');",
  "document.getElementById('teleprompt').hidden=true;bind('status','STAGE CONNECTION LOST')};",
  "feed.onopen=()=>{if(document.body.dataset.active!=='true')bind('status','STAGE CONNECTED')};"
 ].join('');
 const csp="default-src 'none'; script-src 'nonce-"+nonce+
   "'; style-src 'nonce-"+nonce+
   "'; connect-src 'self'; img-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'";
 return '<!doctype html><html lang="en"><head><meta charset="utf-8">'+
   '<meta name="viewport" content="width=device-width,initial-scale=1.0">'+
   '<meta http-equiv="Content-Security-Policy" content="'+csp+'">'+
   '<meta name="referrer" content="no-referrer"><title>Private Stage Confidence</title>'+
   '<style nonce="'+nonce+'">'+css+'</style></head><body data-active="false">'+
   '<header><strong>CONFIDENCE MONITOR · PRIVATE</strong><div id="stage-clock" aria-label="Private stage timer"><span id="timer-label"></span><span id="timer-remaining"></span></div><span id="status" aria-live="polite">CONNECTING</span></header>'+
   '<div class="layout"><section><div id="section" class="muted"></div><h1 id="title"></h1>'+
   '<div id="current" class="cue"></div><h2>Chords</h2><div id="chords" class="private"></div></section>'+
   '<section><h2>Next cue</h2><div id="next" class="next"></div>'+
   '<h2>Private notes</h2><div id="private-notes" class="private"></div></section></div>'+
   '<section id="teleprompt" hidden aria-label="Private speaker and singer teleprompter"><div id="teleprompt-role"></div>'+
   '<div id="teleprompt-current" class="teleprompt-line"></div>'+
   '<div id="teleprompt-next" class="teleprompt-line"></div><div id="teleprompt-progress" class="muted"></div></section>'+
   '<script nonce="'+nonce+'">'+js+'</script></body></html>';
}
