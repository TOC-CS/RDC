/**
 * RDC 2.0 replaces the legacy D1 journal ONLY when the owner explicitly
 * enables a separate, private SQLite-backed Durable Object namespace.
 * The default site build remains unchanged. No public endpoint is added.
 */
import {wakeBindingConfig} from './wake-bindings.mjs';

export function rdc2BindingConfig({enabled=false}={}){
  if(enabled!==true)return {};
  return {
    durable_objects:{
      bindings:[{name:'RDC2_DEVICE',class_name:'RDC2DeviceActor'}]
    },
    migrations:[{
      tag:'rdc2-device-sqlite-v1',
      new_sqlite_classes:['RDC2DeviceActor']
    }]
  };
}
export function combinedDurableBindings({wake=false,v2=false}={}){
  const old=wakeBindingConfig({enabled:wake});
  const next=rdc2BindingConfig({enabled:v2});
  const bindings=[...(old.durable_objects?.bindings??[]),
    ...(next.durable_objects?.bindings??[])];
  if(!bindings.length)return {};
  return {durable_objects:{bindings},migrations:[
    ...(old.migrations??[]),...(next.migrations??[])]};
}
