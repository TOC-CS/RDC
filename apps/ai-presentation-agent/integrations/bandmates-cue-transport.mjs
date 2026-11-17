import {readPrivateState} from '../src/managed-state.mjs';

/**
 * Local, owner-authenticated control-plane cue sender.
 *
 * The BandMates native app remains responsible for producing actual current
 * section events. This transport only forwards validated cues received on a
 * separately authorized, non-real-time callback. No retries are performed
 * after an ambiguous network response, to avoid double slide actions.
 */
export function createBandMatesCueTransport({
 readState=readPrivateState,fetcher=fetch,
 timeoutMs=2200
}={}){
 if(typeof readState!=='function'||typeof fetcher!=='function')
   throw new Error('Authenticated local Presentation Agent transport required.');
 if(!Number.isInteger(timeoutMs)||timeoutMs<200||timeoutMs>10000)
   throw new Error('Invalid local cue transport timeout.');
 return async function send(cue){
   const state=await readState();
   if(!state||!Number.isSafeInteger(state.port)||state.port<1||state.port>65535||
     typeof state.token!=='string'||!/^([a-f0-9]{64})$/.test(state.token))
     throw new Error('Invalid private Presentation Agent session.');
   const url='http://127.0.0.1:'+state.port+'/v1/cue';
   let response;
   try{
     response=await fetcher(url,{
       method:'POST',redirect:'error',
       headers:{Authorization:'Bearer '+state.token,'Content-Type':'application/json'},
       body:JSON.stringify(cue),signal:AbortSignal.timeout(timeoutMs)
     });
   }catch{
     throw new Error('BandMates cue delivery outcome unknown. Do not resend without reconciliation.');
   }
   if(!response.ok)
     throw new Error('Presentation Agent rejected BandMates cue (HTTP '+response.status+').');
   let receipt;
   try{receipt=await response.json();}
   catch{throw new Error('BandMates cue delivery receipt malformed. Do not resend.');}
   if(!receipt||typeof receipt.changed!=='boolean')
     throw new Error('BandMates cue delivery receipt invalid. Do not resend.');
   return receipt;
 };
}
