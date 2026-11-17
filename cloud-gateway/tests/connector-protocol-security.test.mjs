import {test} from 'node:test';
import assert from 'node:assert/strict';
import {invocationSchema,grantSchema,driverMessageSchema} from '../scripts/connector-preview/protocol.mjs';

test('patched Zod validator accepts only an authorized invocation envelope',()=>{
  const valid={connectorId:'rdc-file',actionName:'read',arguments:{path:'synthetic/test.txt'}};
  assert.equal(invocationSchema.safeParse(valid).success,true);
  for(const extra of [{principal:'owner-spoof'}, {token:'should-not-exist'}, {deviceId:'another-device'}]){
    const denied=invocationSchema.safeParse({...valid,...extra});
    assert.equal(denied.success,false,'model-supplied owner identity and credentials must be refused');
  }
  for(const bad of [{...valid,connectorId:'../escape'}, {...valid,actionName:''}, {...valid,arguments:[]}])
    assert.equal(invocationSchema.safeParse(bad).success,false);
});

test('patched Zod grant requires explicit readOnly true and rejects extension fields',()=>{
  const safe={connectorId:'rdc',actionName:'status',readOnly:true};
  assert.equal(grantSchema.safeParse(safe).success,true);
  for(const invalid of [{...safe,readOnly:false}, {...safe,writeAccess:true}, {...safe,principal:'spoof'}])
    assert.equal(grantSchema.safeParse(invalid).success,false);
});

test('driver message schema rejects invalid types and extra result envelope metadata',()=>{
  const id='123e4567-e89b-42d3-a456-426614174000';
  assert.equal(driverMessageSchema.safeParse({jsonrpc:'2.0',id,result:{ok:true}}).success,true);
  assert.equal(driverMessageSchema.safeParse({jsonrpc:'2.0',method:'stop'}).success,true);
  for(const malformed of [
    {jsonrpc:'2.0',id,result:[]},
    {jsonrpc:'2.0',id,result:{},principal:'model-supplied'},
    {jsonrpc:'2.0',id:'not-a-uuid',result:{}},
    {jsonrpc:'2.0',method:'stop',tool:'rdc_job_run'}
  ])assert.equal(driverMessageSchema.safeParse(malformed).success,false);
});
