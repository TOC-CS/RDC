/* Optional best-effort per-device wake hints. The D1 durable journal and
 * conditional claim are always the authority. The production Site must have
 * an explicitly provisioned RDC_WAKE_CHANNEL Durable Object binding before
 * this accelerates anything. No passwords or tool contents enter the signal.
 */
const internalOrigin='https://rdc-wake.internal';
const operationIdPattern=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function makeBoundWakeChannel(env) {
  const namespace=env?.RDC_WAKE_CHANNEL;
  if (!namespace || typeof namespace.idFromName!=='function' ||
      typeof namespace.get!=='function') return null;
  function endpoint(deviceId) {
    if (typeof deviceId!=='string' || !/^[0-9a-f-]{36}$/.test(deviceId))
      throw new Error('Invalid wake device identity');
    return namespace.get(namespace.idFromName(deviceId));
  }
  return {
    async notify(deviceId) {
      const response=await endpoint(deviceId).fetch(new Request(internalOrigin+'/notify',{method:'POST'}));
      if (!response.ok)throw new Error('RDC wake signal unavailable');
    },
    async wait(deviceId,intervalMs) {
      if (!Number.isFinite(intervalMs)||intervalMs<=0)
        throw new Error('Invalid RDC wake wait interval');
      const ms=Math.min(5000,Math.max(1,Math.ceil(intervalMs)));
      const response=await endpoint(deviceId).fetch(new Request(internalOrigin+'/wait?ms='+ms,{method:'POST'}));
      if (!response.ok)throw new Error('RDC wake listener unavailable');
      const payload=await response.json();
      if (payload?.ok!==true||typeof payload.signaled!=='boolean')
        throw new Error('Invalid RDC wake listener result');
      return payload.signaled;
    },
    async notifyResult(deviceId,operationId) {
      if(!operationIdPattern.test(operationId))throw new Error('Invalid result operation ID');
      const address=internalOrigin+'/notify-result?operation_id='+operationId;
      const response=await endpoint(deviceId).fetch(new Request(address,{method:'POST'}));
      if(!response.ok)throw new Error('RDC completion signal unavailable');
    },
    async waitResult(deviceId,operationId,intervalMs) {
      if(!operationIdPattern.test(operationId))throw new Error('Invalid result operation ID');
      if(!Number.isFinite(intervalMs)||intervalMs<=0)
        throw new Error('Invalid completion wait interval');
      const ms=Math.min(5000,Math.max(1,Math.ceil(intervalMs)));
      const address=internalOrigin+'/wait-result?operation_id='+operationId+'&ms='+ms;
      const response=await endpoint(deviceId).fetch(new Request(address,{method:'POST'}));
      if(!response.ok)throw new Error('RDC completion listener unavailable');
      const payload=await response.json();
      if(payload?.ok!==true||typeof payload.signaled!=='boolean')
        throw new Error('Invalid RDC completion listener result');
      return payload.signaled;
    }
  };
}

export class RDCWakeSignal {
  constructor() {
    this.waiters=new Set();
    this.resultWaiters=new Map();
  }
  async fetch(request) {
    const address=new URL(request.url);
    const body=(data,status=200)=>Response.json(data,{status,headers:{'Cache-Control':'no-store'}});
    if(request.method!=='POST')return body({ok:false},405);
    if(address.pathname==='/notify-result'||address.pathname==='/wait-result'){
      const operationId=address.searchParams.get('operation_id');
      if(!operationIdPattern.test(operationId??''))return body({ok:false},400);
      if(address.pathname==='/notify-result'){
        for(const finish of [...(this.resultWaiters.get(operationId)??[])])finish(true);
        return body({ok:true});
      }
      const value=address.searchParams.get('ms');
      if(!value||!/^[1-9][0-9]*$/.test(value)||Number(value)>5000)
        return body({ok:false},400);
      let group=this.resultWaiters.get(operationId);
      if(!group){group=new Set();this.resultWaiters.set(operationId,group)}
      const active=group;
      return new Promise(resolve=>{
        let finished=false,timer;
        const cancel=()=>finish(false);
        const finish=signaled=>{
          if(finished)return;
          finished=true;
          clearTimeout(timer);
          active.delete(finish);
          if(active.size===0)this.resultWaiters.delete(operationId);
          request.signal?.removeEventListener('abort',cancel);
          resolve(body({ok:true,signaled}));
        };
        active.add(finish);
        timer=setTimeout(()=>finish(false),Number(value));
        if(request.signal?.aborted)finish(false);
        else request.signal?.addEventListener('abort',cancel,{once:true});
      });
    }
    if(address.pathname==='/notify') {
      for (const finish of [...this.waiters])finish(true);
      return body({ok:true});
    }
    if(address.pathname==='/wait') {
      const value=address.searchParams.get('ms');
      if(!value||!/^[1-9][0-9]*$/.test(value)||Number(value)>5000)
        return body({ok:false},400);
      const interval=Number(value);
      return new Promise(resolve=>{
        let finished=false, timer;
        const cancel=()=>finish(false);
        const finish=signaled=>{
          if(finished)return;
          finished=true;
          clearTimeout(timer);
          this.waiters.delete(finish);
          request.signal?.removeEventListener('abort',cancel);
          resolve(body({ok:true,signaled}));
        };
        this.waiters.add(finish);
        timer=setTimeout(()=>finish(false),interval);
        if(request.signal?.aborted)finish(false);
        else request.signal?.addEventListener('abort',cancel,{once:true});
      });
    }
    return body({ok:false},404);
  }
}
