import test from 'node:test';
import assert from 'node:assert/strict';
import {rdc2BindingConfig,combinedDurableBindings} from '../../scripts/rdc2-bindings.mjs';

test('RDC 2.0 actor binding is absent unless exactly enabled',()=>{
  assert.deepEqual(rdc2BindingConfig({}),{});
  assert.deepEqual(rdc2BindingConfig({enabled:false}),{});
  assert.deepEqual(rdc2BindingConfig({enabled:'1'}),{});
  assert.deepEqual(rdc2BindingConfig({enabled:1}),{});
  assert.deepEqual(combinedDurableBindings(),{});
});
test('RDC 2.0 alone registers its new private SQLite class without v1 wake class',()=>{
  const config=combinedDurableBindings({v2:true,wake:false});
  assert.deepEqual(config.durable_objects.bindings,
    [{name:'RDC2_DEVICE',class_name:'RDC2DeviceActor'}]);
  assert.deepEqual(config.migrations,
    [{tag:'rdc2-device-sqlite-v1',new_sqlite_classes:['RDC2DeviceActor']}]);
});
test('RDC 2.0 and old wake can be qualified together with noncolliding migrations',()=>{
  const config=combinedDurableBindings({v2:true,wake:true});
  assert.deepEqual(config.durable_objects.bindings,
    [{name:'RDC_WAKE_CHANNEL',class_name:'RDCWakeSignal'},
     {name:'RDC2_DEVICE',class_name:'RDC2DeviceActor'}]);
  assert.deepEqual(config.migrations.map(x=>x.tag),
    ['rdc-wake-sqlite-v1','rdc2-device-sqlite-v1']);
  assert.equal(new Set(config.migrations.map(x=>x.tag)).size,2);
  assert.ok(!JSON.stringify(config).includes('secret'));
  assert.ok(!JSON.stringify(config).includes('public_route'));
});
