import {randomBytes} from 'node:crypto';

/**
 * Public data only, transparent OBS Browser Source. No stage notes/chords,
 * control bearer, stage token, stream key, OBS actions, camera, or audio here.
 */
export function renderBroadcastOverlayHtml({eventsPath}={}){
 if(typeof eventsPath!=='string'||!eventsPath.startsWith('/v1/stream-events?key=')||
    eventsPath.length>1000)throw Error('A local, independently authorized stream event path is required.');
 const nonce=randomBytes(16).toString('base64');
 const css=[
   ':root{font-family:system-ui,-apple-system,Arial,sans-serif;color-scheme:dark}',
   '*{box-sizing:border-box}html,body{height:100%;width:100%;margin:0;background:transparent!important;overflow:hidden}',
   'main{position:absolute;left:7%;bottom:7%;width:86%;max-width:86%;display:flex;justify-content:center}',
   '#overlay{border-radius:.75em;padding:1.1em 1.6em;background:rgba(0,0,0,.70);',
   'text-align:center;max-width:100%;overflow-wrap:anywhere}',
   '#overlay[hidden]{display:none!important}',
   'body[data-look="minimal"] #overlay{background:transparent;padding:.35em .8em;border-radius:0}',
   'body[data-background="light"] #overlay{background:rgba(255,255,255,.86)}',
   'body[data-background="light"] h1,body[data-background="light"] #text{color:#111}',
   'body[data-background="light"] #reference{color:#333}',
   'h1{color:#fff;margin:0 0 .25em;font-size:clamp(22px,3vw,48px);line-height:1.15}',
   '#text{color:#fff;font-size:clamp(24px,3.3vw,58px);line-height:1.15;white-space:pre-line}',
   '#reference{font-size:clamp(14px,1.4vw,28px);color:#ffe9aa;margin-top:.4em}',
   '@media(max-width:600px){main{left:4%;width:92%;bottom:4%}#overlay{padding:.7em 1em}}'
 ].join('');
 const js=[
   "const bind=(id,text)=>{document.getElementById(id).textContent=String(text??'')};",
   "const output=document.getElementById('overlay');",
   "const clear=()=>{output.hidden=true;for(const id of ['title','text','reference'])bind(id,'')};",
   "clear();",
   "const connection=new EventSource("+JSON.stringify(eventsPath)+");",
   "connection.onmessage=event=>{try{",
   "const state=JSON.parse(event.data);",
   "if(!state||state.loaded===false||!state.current||state.outputFaulted===true){clear();return;}",
   "document.body.dataset.visibility=state.visibility==='clear'?'clear':'visible';",
   "if(state.visibility==='clear'){clear();return;}",
   "const slide=state.current;",
   "document.body.dataset.look=['lower-third','minimal'].includes(state.look?.layout)?state.look.layout:'lower-third';",
   "document.body.dataset.background=['transparent','light','dark'].includes(state.look?.background)?state.look.background:'transparent';",
   "bind('title',slide.title);bind('text',slide.text);bind('reference',slide.reference??'');",
   "output.hidden=!(slide.title||slide.text||slide.reference);",
   "}catch{clear();}};",
   "connection.onerror=()=>{document.body.dataset.connection='reconnecting'};",
   "connection.onopen=()=>{document.body.dataset.connection='connected'};"
 ].join('');
 const csp="default-src 'none'; script-src 'nonce-"+nonce+
  "'; style-src 'nonce-"+nonce+
  "'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'";
 return '<!doctype html><html lang="en"><head><meta charset="utf-8">'+
   '<meta name="viewport" content="width=device-width,initial-scale=1.0">'+
   '<meta name="referrer" content="no-referrer">'+
   '<meta http-equiv="Content-Security-Policy" content="'+csp+'">'+
   '<title>Public Stream Overlay</title><style nonce="'+nonce+'">'+css+'</style></head>'+
   '<body><main aria-label="Public broadcast graphics only"><section id="overlay" hidden>'+
   '<h1 id="title"></h1><div id="text"></div><div id="reference"></div></section></main>'+
   '<script nonce="'+nonce+'">'+js+'</script></body></html>';
}
