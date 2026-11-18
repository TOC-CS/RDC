import assert from 'node:assert/strict';
import {test} from 'node:test';
import {wakeBindingConfig} from '../scripts/wake-bindings.mjs';

test('private DO binding is absent by default and when opt in is not exact true',()=>{
  assert.deepEqual(wakeBindingConfig({enabled:false}),{});
  assert.deepEqual(wakeBindingConfig({}),{});
  assert.deepEqual(wakeBindingConfig({enabled:'1'}),{});
  assert.deepEqual(wakeBindingConfig({enabled:1}),{});
});

test('explicit private opt-in exposes only the source DO and one SQLite migration',()=>{
  assert.deepEqual(wakeBindingConfig({enabled:true}),{
    durable_objects:{bindings:[{name:'RDC_WAKE_CHANNEL',class_name:'RDCWakeSignal'}]},
    migrations:[{tag:'rdc-wake-sqlite-v1',new_sqlite_classes:['RDCWakeSignal']}]
  });
});

test('feature flags cannot enable an unrelated DO or public endpoint',()=>{
  const value=wakeBindingConfig({enabled:true});
  assert.equal(value.durable_objects.bindings.length,1);
  assert.equal(value.migrations.length,1);
  assert.ok(!JSON.stringify(value).includes('token'));
  assert.ok(!JSON.stringify(value).includes('password'));
});
