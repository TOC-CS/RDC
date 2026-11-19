/**
 * RDC 2.0 control-plane protocol. ID-only notifications; the durable
 * operation journal remains authoritative for claims, ownership and results.
 *
 * This module owns wire validation only. It never stores credentials,
 * dispatches local actions, replays mutations or changes the live Site.
 */
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const features=Object.freeze(['queue-hints','result-hints']);
const allowedKinds=new Set(['queue-ready','result-ready']);
const shape=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const exact=(value,allowed,required)=>{
  if(!shape(value))throw new TypeError('Invalid RDC control envelope');
  const keys=Object.keys(value);
  if(keys.some(key=>!allowed.includes(key))||required.some(key=>!Object.hasOwn(value,key)))
    throw new TypeError('Unexpected RDC control field');
};
export function negotiateRdcV2(peer){
  exact(peer,['protocolVersions','features'],['protocolVersions','features']);
  if(!Array.isArray(peer.protocolVersions)||!Array.isArray(peer.features)||
     peer.protocolVersions.length>8||peer.features.length>16||
     !peer.protocolVersions.every(v=>Number.isInteger(v)&&v>=1&&v<=2)||
     !peer.features.every(v=>typeof v==='string'&&v.length>0&&v.length<=64))
    throw new TypeError('Invalid RDC protocol capabilities');
  if(!peer.protocolVersions.includes(2))return null;
  return Object.freeze({version:2,
    features:Object.freeze(features.filter(feature=>peer.features.includes(feature)))});
}
export function createControlEvent(value){
  exact(value,['kind','deviceId','operationId','sequence'],['kind','deviceId','sequence']);
  if(!allowedKinds.has(value.kind)||!uuid.test(value.deviceId)||
     !Number.isSafeInteger(value.sequence)||value.sequence<0)
    throw new TypeError('Invalid RDC control event');
  if(value.kind==='result-ready'&&!uuid.test(value.operationId??''))
    throw new TypeError('Result notification requires an operation ID');
  if(value.kind==='queue-ready'&&Object.hasOwn(value,'operationId'))
    throw new TypeError('Queue notification must not include operation ID');
  return Object.freeze({
    version:2,kind:value.kind,deviceId:value.deviceId,
    ...(value.kind==='result-ready'?{operationId:value.operationId}:{}),
    sequence:value.sequence,
  });
}
export function parseControlEvent(json){
  if(typeof json!=='string'||new TextEncoder().encode(json).length>512)
    throw new TypeError('Invalid RDC control event frame');
  let frame;
  try{frame=JSON.parse(json)}catch{throw new TypeError('Invalid RDC control event JSON')}
  exact(frame,['version','kind','deviceId','operationId','sequence'],
    ['version','kind','deviceId','sequence']);
  if(frame.version!==2)throw new TypeError('Unsupported RDC control version');
  return createControlEvent(Object.fromEntries(
    Object.entries(frame).filter(([key])=>key!=='version')));
}
