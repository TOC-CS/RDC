import {createControlEvent} from './rdc-v2-protocol.mjs';

/**
 * RDC 2.0 in-memory per-device event broker. No durable operation data or
 * executable actions pass through this channel. Consumers reconcile events
 * with the authoritative journal and MUST NOT replay a mutation.
 *
 * This pure component is not connected to the existing production Site.
 */
export class RDCV2EventBroker {
  constructor({deviceId,clock=Date.now,maxEvents=256,maxWaiters=512,ttlMs=5000}) {
    createControlEvent({kind:'queue-ready',deviceId,sequence:0});
    if(typeof clock!=='function'||!Number.isSafeInteger(maxEvents)||maxEvents<1||maxEvents>4096||
       !Number.isSafeInteger(maxWaiters)||maxWaiters<1||maxWaiters>4096||
       !Number.isSafeInteger(ttlMs)||ttlMs<1||ttlMs>30_000)
      throw new TypeError('Invalid RDC broker bounds');
    this.deviceId=deviceId;
    this.clock=clock;
    this.maxEvents=maxEvents;
    this.maxWaiters=maxWaiters;
    this.ttlMs=ttlMs;
    this.sequence=0;
    this.events=[];
    this.waiters=new Set();
  }
  get activeWaiters(){return this.waiters.size}
  prune(){
    const now=this.clock();
    this.events=this.events.filter(record=>now-record.at<=this.ttlMs);
    if(this.events.length>this.maxEvents)this.events=this.events.slice(-this.maxEvents);
  }
  readSince(afterSequence){
    if(!Number.isSafeInteger(afterSequence)||afterSequence<0)
      throw new TypeError('Invalid RDC event cursor');
    this.prune();
    const earliest=this.events[0]?.event.sequence??this.sequence+1;
    return Object.freeze({
      events:Object.freeze(this.events.filter(x=>x.event.sequence>afterSequence).map(x=>x.event)),
      gap:afterSequence<earliest-1||afterSequence>this.sequence,
      latestSequence:this.sequence,
    });
  }
  publish(value){
    if(value===null||typeof value!=='object'||Array.isArray(value)||
       Object.keys(value).some(key=>!['kind','operationId'].includes(key)))
      throw new TypeError('Invalid RDC event input');
    const event=createControlEvent({...value,deviceId:this.deviceId,sequence:this.sequence+1});
    this.sequence++;
    this.events.push({event,at:this.clock()});
    this.prune();
    for(const notify of [...this.waiters])notify();
    return event;
  }
  wait({afterSequence,timeoutMs=1000,signal}){
    if(!Number.isSafeInteger(timeoutMs)||timeoutMs<1||timeoutMs>5000)
      throw new TypeError('Invalid RDC wait interval');
    if(!Number.isSafeInteger(afterSequence)||afterSequence<0)
      throw new TypeError('Invalid RDC event cursor');
    if(signal?.aborted)return Promise.resolve(Object.freeze({events:Object.freeze([]),gap:false,latestSequence:this.sequence}));
    const available=this.readSince(afterSequence);
    if(available.events.length||available.gap)return Promise.resolve(available);
    if(this.waiters.size>=this.maxWaiters)throw new RangeError('RDC event waiter capacity reached');
    return new Promise(resolve=>{
      let done=false, timer;
      const finish=(cancelled=false)=>{
        if(done)return;
        done=true;
        clearTimeout(timer);
        this.waiters.delete(wake);
        signal?.removeEventListener('abort',abort);
        resolve(cancelled?Object.freeze({events:Object.freeze([]),gap:false,latestSequence:this.sequence}):
          this.readSince(afterSequence));
      };
      const wake=()=>finish();
      const abort=()=>finish(true);
      this.waiters.add(wake);
      timer=setTimeout(()=>finish(),timeoutMs);
      if(signal?.aborted)abort();
      else signal?.addEventListener('abort',abort,{once:true});
    });
  }
}
