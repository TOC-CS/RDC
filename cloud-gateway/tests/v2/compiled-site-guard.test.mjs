import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync,readdirSync,lstatSync,readFileSync,mkdirSync,symlinkSync,renameSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createHash} from 'node:crypto';
import {verifyCompiledSite} from '../../scripts/rdc2-compiled-site-guard.mjs';

const base=()=>({
  name:'isolated-fixture-site',main:'index.js',
  compatibility_date:'2026-05-15',
  compatibility_flags:['nodejs_compat'],
  d1_databases:[{binding:'DB',database_name:'existing-db',database_id:'test-db-id'}],
  r2_buckets:[{binding:'BUCKET',bucket_name:'existing-r2'}],
  durable_objects:{bindings:[]},migrations:[],vars:{},services:[],
  assets:{directory:'../client'},observability:{enabled:true}
});
const upgrade=initial=>{
  const candidate=structuredClone(initial);
  candidate.durable_objects.bindings.push({name:'RDC2_DEVICE',class_name:'RDC2DeviceActor'});
  candidate.migrations.push({tag:'rdc2-device-sqlite-v1',
    new_sqlite_classes:['RDC2DeviceActor']});
  return candidate;
};
const script='export class RDC2DeviceActor {} // v2/device/socket v2/device/result';
const sha=raw=>createHash('sha256').update(raw).digest('hex');
// Independent test-side artifact pinning. Include every output file, not just
// index.js: Workerd no_bundle mode loads external modules from this tree.
const treePin=root=>{
  const files=[];
  const walk=(dir,base='')=>{
    for(const name of readdirSync(dir).sort()){
      const path=join(dir,name);
      const relative=base?base+'/'+name:name;
      const info=lstatSync(path);
      if(info.isSymbolicLink())throw Error('pin cannot include symlinks');
      if(info.isDirectory())walk(path,relative);
      else if(info.isFile())files.push([relative,sha(readFileSync(path))]);
      else throw Error('unexpected artifact type');
    }
  };
  walk(root);
  return sha(JSON.stringify(files));
};
function fixture(){
  const root=mkdtempSync(join(tmpdir(),'rdc2-compiled-site-guard-'));
  const baseline=base(),candidate=upgrade(baseline);
  const baselinePath=join(root,'baseline','wrangler.json');
  const candidatePath=join(root,'candidate','wrangler.json');
  const bundlePath=join(root,'candidate','index.js');
  const {mkdirSync}=requirelessFs;
  mkdirSync(join(root,'baseline'));mkdirSync(join(root,'candidate'));
  const run=async({before=baseline,after=candidate,bundle=script,expectedSha=sha(script)}={})=>{
    writeFileSync(baselinePath,JSON.stringify(before));
    writeFileSync(candidatePath,JSON.stringify(after));
    writeFileSync(bundlePath,bundle);
    return verifyCompiledSite({baselineConfigPath:baselinePath,
      candidateConfigPath:candidatePath,bundlePath,expectedBundleSha256:expectedSha,
      artifactRoot:join(root,'candidate'),
      expectedArtifactTreeSha256:treePin(join(root,'candidate'))});
  };
  return {run,baseline,candidate,root,cleanup:()=>rmSync(root,{recursive:true,force:true})};
}
import * as requirelessFs from 'node:fs';

test('offline compiled V2 opt-in can only pass artifact parity, never live deployment approval',async()=>{
  const f=fixture();
  try{
    const r=await f.run();
    assert.equal(r.compiledArtifactCompatible,true);
    assert.equal(r.releaseApproved,false);
    assert.equal(r.hostedProtectedVersionVerified,false);
    assert.equal(r.archiveEnablementApproved,false);
    assert.equal(r.scope,'offline-compiled-artifact-only');
    assert.equal(r.candidateBundleSha256,sha(script));
    assert.deepEqual(r.blockers,[]);
  }finally{f.cleanup()}
});
test('compiled Site refuses missing/incorrect V2 actor class or SQLite migration',async()=>{
  const f=fixture();
  try{
    const variants=[
      x=>{x.durable_objects.bindings=[]},
      x=>{x.durable_objects.bindings[0].class_name='RDCWakeSignal'},
      x=>{x.migrations=[]},
      x=>{x.migrations[0].new_sqlite_classes=['RDCWakeSignal']},
      x=>{x.migrations.push(structuredClone(x.migrations[0]))},
    ];
    for(const change of variants){
      const x=upgrade(f.baseline);change(x);
      const r=await f.run({after:x});
      assert.equal(r.compiledArtifactCompatible,false,JSON.stringify(x));
    }
  }finally{f.cleanup()}
});
test('V2 opt-in refuses any unrelated DB/R2, services, or asset change against baseline',async()=>{
  const f=fixture();
  try{
    for(const change of [
      x=>{x.d1_databases[0].database_id='different-db'},
      x=>{x.r2_buckets[0].bucket_name='different-bucket'},
      x=>{x.services=[{binding:'UNREVIEWED',service:'new-worker'}]},
      x=>{x.assets.directory='../different-files'},
      x=>{x.compatibility_date='2026-06-01'},
    ]){
      const c=upgrade(f.baseline);change(c);
      assert.equal((await f.run({after:c})).compiledArtifactCompatible,false);
    }
  }finally{f.cleanup()}
});
test('V2 staged Site cannot enable runtime or archive or distribute device credentials in compiled vars',async()=>{
  const f=fixture();
  try{
    for(const vars of [
      {RDC2_RUNTIME_ENABLED:'1'},
      {RDC2_TOMBSTONE_ARCHIVE_ENABLED:'1'},
      {RDC_DEVICE_SECRET:'synthetic-secret-do-not-deploy'},
      {RDC2_INTERNAL_KEY:'synthetic-internal-key-do-not-deploy'},
      {RDC_DEVICE_ID:'wrong-target-device-id'}
    ]){
      const c=upgrade(f.baseline);c.vars={...c.vars,...vars};
      assert.equal((await f.run({after:c})).compiledArtifactCompatible,false);
    }
  }finally{f.cleanup()}
});
test('V2 compiled Site refuses public routing, anonymous workers_dev, or dangerous baseline',async()=>{
  const f=fixture();
  try{
    for(const change of [
      x=>{x.routes=['*/*']},
      x=>{x.route='*.example.test/*'},
      x=>{x.workers_dev=true},
    ]){
      const c=upgrade(f.baseline);change(c);
      assert.equal((await f.run({after:c})).compiledArtifactCompatible,false);
      const b=base();change(b);
      assert.equal((await f.run({before:b,after:upgrade(b)})).compiledArtifactCompatible,false);
    }
  }finally{f.cleanup()}
});
test('bundle SHA mismatch, missing class export or transport routes blocks source compatibility',async()=>{
  const f=fixture();
  try{
    const cases=[
      {bundle:script,expectedSha:sha('wrong-original')},
      {bundle:'export default {}',expectedSha:sha('export default {}')},
      {bundle:'export class RDC2DeviceActor {}',expectedSha:sha('export class RDC2DeviceActor {}')},
    ];
    for(const c of cases){
      assert.equal((await f.run(c)).compiledArtifactCompatible,false);
    }
  }finally{f.cleanup()}
});
test('missing V1 baseline DB/R2 bindings cannot be considered compatible',async()=>{
  const f=fixture();
  try{
    for(const change of [x=>{x.d1_databases=[]},x=>{x.r2_buckets=[]}]){
      const b=base();change(b);
      const r=await f.run({before:b,after:upgrade(b)});
      assert.equal(r.compiledArtifactCompatible,false);
    }
  }finally{f.cleanup()}
});

test('malformed or object-form public routing and activation flags fail closed even when baseline matches',async()=>{
  const f=fixture();
  try{
    for(const change of [
      x=>{x.routes={pattern:'*.example.test/*'}},
      x=>{x.workers_dev='true'},
      x=>{x.vars.RDC2_RUNTIME_ENABLED='0'},
      x=>{x.vars.RDC2_TOMBSTONE_ARCHIVE_ENABLED='0'},
    ]){
      const b=base();change(b);
      const result=await f.run({before:b,after:upgrade(b)});
      assert.equal(result.compiledArtifactCompatible,false,
        'unsafe but unchanged baseline must not count as source readiness');
    }
  }finally{f.cleanup()}
});
test('an unchanged historical wake actor and migration are preserved exactly when opt-in adds V2',async()=>{
  const f=fixture();
  try{
    const b=base();
    b.durable_objects.bindings.push({name:'RDC_WAKE_CHANNEL',class_name:'RDCWakeSignal'});
    b.migrations.push({tag:'rdc-wake-sqlite-v1',new_sqlite_classes:['RDCWakeSignal']});
    assert.equal((await f.run({before:b,after:upgrade(b)})).compiledArtifactCompatible,true);
    const replacement=upgrade(b);
    replacement.migrations[0].tag='rewritten-old-migration';
    assert.equal((await f.run({before:b,after:replacement})).compiledArtifactCompatible,false);
  }finally{f.cleanup()}
});


test('no_bundle transitive module mutation is rejected despite unchanged pinned index.js',async()=>{
  const f=fixture();
  try{
    await f.run();
    const folder=join(f.root,'candidate','_next','static');
    mkdirSync(folder,{recursive:true});
    const modulePath=join(folder,'actor-chunk.mjs');
    writeFileSync(modulePath,'export const operation = "original";');
    const pinned=treePin(join(f.root,'candidate'));
    const props={baselineConfigPath:join(f.root,'baseline','wrangler.json'),
      candidateConfigPath:join(f.root,'candidate','wrangler.json'),
      bundlePath:join(f.root,'candidate','index.js'),
      expectedBundleSha256:sha(script),
      artifactRoot:join(f.root,'candidate'),expectedArtifactTreeSha256:pinned};
    assert.equal(verifyCompiledSite(props).compiledArtifactCompatible,true);
    writeFileSync(modulePath,'export const operation = "modified";');
    const changed=verifyCompiledSite(props);
    assert.equal(changed.compiledArtifactCompatible,false,
      'a modified code-split module must invalidate the exact release artifact');
    assert.ok(changed.blockers.includes('artifact_tree_digest_mismatch'),JSON.stringify(changed));
  }finally{f.cleanup()}
});

test('new injected asset or symlink in artifact tree fails closed before protected canary',async()=>{
  const f=fixture();
  try{
    await f.run();
    const root=join(f.root,'candidate');
    const pinned=treePin(root);
    const props={baselineConfigPath:join(f.root,'baseline','wrangler.json'),
      candidateConfigPath:join(root,'wrangler.json'),
      bundlePath:join(root,'index.js'),expectedBundleSha256:sha(script),
      artifactRoot:root,expectedArtifactTreeSha256:pinned};
    writeFileSync(join(root,'extra-shim.js'),'export const injected=true;');
    assert.equal(verifyCompiledSite(props).compiledArtifactCompatible,false);
    rmSync(join(root,'extra-shim.js'));
    symlinkSync(join(f.root,'baseline','wrangler.json'),join(root,'out-of-tree.mjs'));
    const link=verifyCompiledSite(props);
    assert.equal(link.compiledArtifactCompatible,false);
    assert.ok(link.blockers.includes('artifact_tree_unavailable_or_unsafe'),JSON.stringify(link));
  }finally{f.cleanup()}
});


test('real built Site layout fingerprints client assets and server chunks as one release tree',async()=>{
  const f=fixture();
  try{
    await f.run();
    const root=join(f.root,'candidate');
    mkdirSync(join(root,'server'));mkdirSync(join(root,'client'));
    renameSync(join(root,'wrangler.json'),join(root,'server','wrangler.json'));
    renameSync(join(root,'index.js'),join(root,'server','index.js'));
    const client=join(root,'client','client-entry.js');
    writeFileSync(client,'export const visible="original";');
    const pinned=treePin(root);
    const args={baselineConfigPath:join(f.root,'baseline','wrangler.json'),
      candidateConfigPath:join(root,'server','wrangler.json'),
      bundlePath:join(root,'server','index.js'),
      expectedBundleSha256:sha(script),
      artifactRoot:root,expectedArtifactTreeSha256:pinned};
    assert.equal(verifyCompiledSite(args).compiledArtifactCompatible,true,
      'a normal dist/{server,client} layout must be accepted');
    writeFileSync(client,'export const visible="tampered";');
    const changed=verifyCompiledSite(args);
    assert.equal(changed.compiledArtifactCompatible,false);
    assert.ok(changed.blockers.includes('artifact_tree_digest_mismatch'));
  }finally{f.cleanup()}
});
