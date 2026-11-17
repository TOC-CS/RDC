/**
 * Read-only status link to a running BandMates AI Studio companion-host.
 * The current companion API does not expose authoritative performed song
 * sections. Do not derive cues from tempo, keys, a planned form, MIDI notes,
 * or a visible band name.
 *
 * No CoreMIDI, CoreAudio, mixer, device, app or band session mutation occurs.
 */
const LOCAL_HOSTS=new Set(['127.0.0.1','localhost','[::1]','::1']);
const privateUrl=(raw)=>{
 const url=new URL(raw);
 if(url.protocol!=='http:'||!LOCAL_HOSTS.has(url.hostname)||
    url.username||url.password||url.search||url.hash||url.pathname!=='/')
   throw new Error('BandMates owner status must use an explicit loopback HTTP base URL.');
 return url.origin;
};
const readOnlyPaths=Object.freeze(['/api/band/status','/api/live/status','/api/state']);
const text=(value,max)=>typeof value==='string'?value.slice(0,max):null;
export class BandMatesLiveLink{
 constructor({baseUrl='http://127.0.0.1:8746',fetcher=fetch,
   timeoutMs=1600,clock=()=>Date.now(),onCurrentSection=null}={}){
   this.base=privateUrl(baseUrl);
   if(typeof fetcher!=='function')throw new TypeError('A read-only fetch function is required.');
   if(!Number.isInteger(timeoutMs)||timeoutMs<100||timeoutMs>15000)
     throw new Error('BandMates status request timeout out of bounds.');
   if(typeof clock!=='function')throw new TypeError('Clock required.');
   if(onCurrentSection!==null&&typeof onCurrentSection!=='function')
     throw new TypeError('Optional current-section callback must be a function.');
   this.fetcher=fetcher;this.timeoutMs=timeoutMs;this.clock=clock;
   this.onCurrentSection=onCurrentSection;this.last=null;this.pollCount=0;
 }
 async inspect(){
   // Each read uses the exact same loopback origin and GET-only API.
   const results=[];
   for(const path of readOnlyPaths){
     const response=await this.fetcher(this.base+path,{
       method:'GET',signal:AbortSignal.timeout(this.timeoutMs),redirect:'error',
       headers:{Accept:'application/json'}
     });
     if(!response?.ok)throw new Error('BandMates read-only '+path+' returned HTTP '+response?.status);
     let body;
     try{body=await response.json();}
     catch{throw new Error('Invalid JSON from BandMates read-only '+path);}
     if(!body||typeof body!=='object'||Array.isArray(body))
       throw new Error('Invalid BandMates status object from '+path);
     results.push(body);
   }
   const [band,live,desktop]=results;
   if(typeof band.running!=='boolean'||typeof live.running!=='boolean'||
      typeof desktop.protocol!=='string'||!Array.isArray(desktop.channels))
     throw new Error('BandMates companion API status schema mismatch.');
   this.pollCount++;
   const report={
     schema:'toc.presentation.bandmates-live-status/v1',
     source:'BandMates AI Studio local companion API',
     transport:'read-only-loopback-GET',
     inspectedAt:this.clock(),
     liveCompanionReachable:true,
     bandRunning:band.running,
     bandGeneration:Number.isSafeInteger(band.generation)?band.generation:null,
     bandActivity:text(band.activity,48),
     liveFollowingRunning:live.running,
     liveFollowingStatus:text(live.status,50),
     liveHardwareOutputVerified:live.hardwareOutputVerified===true,
     currentTitle:text(desktop.bandTitle,120),
     nativeSectionSignalAvailable:false,
     currentSection:null,
     currentSectionOccurrence:null,
     presentationCueSent:false,
     reason:band.running?'no_authoritative_current_song_section':'bandmates_idle',
     pollingCount:this.pollCount
   };
   // No automatic event from this path: the live endpoint has no confirmed
   // song title + section occurrence. Caller must wait for a verified live
   // non-real-time callback or an independently observed vocal cue.
   this.last=report;
   return {...report};
 }
}
