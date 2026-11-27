/**
 * Offline compiled Site configuration parity preflight.
 *
 * Compare exact generated Wrangler manifests for an inactive private V2
 * candidate with its unchanged baseline. Check pinned bundle bytes, actor
 * export and transport entry points. This is source-artifact evidence ONLY.
 * It cannot attest to hosted Site versions, protected rollback or release.
 * No network access, credential reads, mutation, or cloud deployment.
 */
import {readFileSync,readdirSync,lstatSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {isDeepStrictEqual} from 'node:util';
import {basename,resolve,join,relative} from 'node:path';
import {pathToFileURL} from 'node:url';

const digest=value=>createHash('sha256').update(value).digest('hex');
const pattern=/^[a-f0-9]{64}$/;
const expectedV2Binding={name:'RDC2_DEVICE',class_name:'RDC2DeviceActor'};
const expectedMigration={
  tag:'rdc2-device-sqlite-v1',
  new_sqlite_classes:['RDC2DeviceActor']
};
const report=()=>({
  scope:'offline-compiled-artifact-only',
  compiledArtifactCompatible:false,
  hostedProtectedVersionVerified:false,
  archiveEnablementApproved:false,
  releaseApproved:false,
  candidateBundleSha256:null,
  artifactTreeSha256:null,
  artifactTreeFileCount:null,
  blockers:[]
});
const unsafeRoutes=c=>Boolean(
  (c?.workers_dev!==undefined&&c.workers_dev!==false)||
  (c?.route!==undefined&&c.route!==null&&c.route!=='')||
  (c?.routes!==undefined&&
    (!Array.isArray(c.routes)||c.routes.length>0))
);
function retainedLegacy(c){
  if(!Array.isArray(c?.d1_databases)||!c.d1_databases.some(x=>x.binding==='DB'))
    return false;
  if(!Array.isArray(c?.r2_buckets)||!c.r2_buckets.some(x=>x.binding==='BUCKET'))
    return false;
  if(c?.durable_objects?.bindings!==undefined&&
     !Array.isArray(c.durable_objects.bindings))return false;
  if(c?.migrations!==undefined&&!Array.isArray(c.migrations))return false;
  return true;
}
function forbiddenVars(c){
  if(!c?.vars||typeof c.vars!=='object'||Array.isArray(c.vars))return false;
  return Object.keys(c.vars).some(key=>
    /(SECRET|TOKEN|PASSWORD|INTERNAL_KEY|DEVICE_ID)/i.test(key))||
    Object.hasOwn(c.vars,'RDC2_RUNTIME_ENABLED')||
    Object.hasOwn(c.vars,'RDC2_TOMBSTONE_ARCHIVE_ENABLED');
}
// Workerd generated builds may set no_bundle=true: index.js is only the
// entrypoint, and changing an independently loaded _next chunk leaves that
// entrypoint SHA unchanged. Pin the complete emitted artifact tree, including
// the exact relative paths, to detect altered or injected executable modules.
// No symlinks, device nodes or unbounded trees are eligible for release.
export function fingerprintArtifactTree(root){
  const base=resolve(root);
  if(!lstatSync(base).isDirectory()||lstatSync(base).isSymbolicLink())
    throw Error('unsafe_artifact_root');
  const files=[];
  let totalBytes=0;
  const walk=(dir,prefix='')=>{
    for(const name of readdirSync(dir).sort()){
      const path=join(dir,name);
      const relativePath=prefix?prefix+'/'+name:name;
      const stat=lstatSync(path);
      if(stat.isSymbolicLink())throw Error('artifact_symlink');
      if(stat.isDirectory()){walk(path,relativePath);continue}
      if(!stat.isFile())throw Error('unexpected_artifact_type');
      totalBytes+=stat.size;
      if(files.length>=8192||totalBytes>512*1024*1024)
        throw Error('artifact_tree_capacity');
      files.push([relativePath,digest(readFileSync(path))]);
    }
  };
  walk(base);
  if(!(['','server/'].some(base=>
      files.some(([path])=>path===base+'index.js')&&
      files.some(([path])=>path===base+'wrangler.json'))))
    throw Error('missing_artifact_entrypoints');
  return {sha256:digest(JSON.stringify(files)),fileCount:files.length};
}
function safeReadJson(file,result,blocker){
  try{
    if(basename(resolve(file))!=='wrangler.json')throw Error('wrong_filename');
    const config=JSON.parse(readFileSync(resolve(file),'utf8'));
    if(!config||typeof config!=='object'||Array.isArray(config))throw Error('wrong_shape');
    return config;
  }catch{result.blockers.push(blocker);return null}
}
export function verifyCompiledSite({baselineConfigPath,candidateConfigPath,
  bundlePath,expectedBundleSha256,artifactRoot,expectedArtifactTreeSha256}={}){
  const result=report();
  const baseline=safeReadJson(baselineConfigPath,result,'baseline_manifest_unavailable');
  const candidate=safeReadJson(candidateConfigPath,result,'candidate_manifest_unavailable');
  if(!baseline||!candidate)return result;
  if(!retainedLegacy(baseline)||!retainedLegacy(candidate))
    result.blockers.push('legacy_storage_bindings_missing');
  if(unsafeRoutes(baseline)||unsafeRoutes(candidate))
    result.blockers.push('unprotected_public_routing');
  if(forbiddenVars(baseline)||forbiddenVars(candidate))
    result.blockers.push('embedded_runtime_credentials_or_unsafe_activation');
  const originalBindings=baseline.durable_objects?.bindings??[];
  const originalMigrations=baseline.migrations??[];
  if(originalBindings.some(x=>x.name==='RDC2_DEVICE')||
    originalMigrations.some(x=>x.tag==='rdc2-device-sqlite-v1')){
    result.blockers.push('baseline_already_contains_v2');
  }else{
    // Compare the COMPLETE emitted manifest. Inserting one namespace and
    // one additive SQLite migration is the only permitted change here.
    // This rejects silent changes to legacy R2/D1, origin, routing, workers,
    // assets, compatibility dates or any other deployment fields.
    const expected=structuredClone(baseline);
    expected.durable_objects={
      ...expected.durable_objects,
      bindings:[...originalBindings,expectedV2Binding],
    };
    expected.migrations=[...originalMigrations,expectedMigration];
    if(!isDeepStrictEqual(candidate,expected))
      result.blockers.push('compiled_config_not_exact_additive_v2');
  }
  if(!pattern.test(expectedBundleSha256??'')){
    result.blockers.push('expected_bundle_digest_missing');
  }else{
    try{
      if(basename(resolve(bundlePath))!=='index.js')throw Error('wrong_bundle_name');
      const bundle=readFileSync(resolve(bundlePath));
      const actual=digest(bundle);
      result.candidateBundleSha256=actual;
      if(actual!==expectedBundleSha256)
        result.blockers.push('candidate_bundle_digest_mismatch');
      if(!bundle.includes('RDC2DeviceActor')||
        !bundle.includes('v2/device/socket')||
        !bundle.includes('v2/device/result'))
        result.blockers.push('candidate_bundle_missing_actor_or_routes');
    }catch{result.blockers.push('candidate_bundle_unavailable')}
  }
  if(!pattern.test(expectedArtifactTreeSha256??'')){
    result.blockers.push('artifact_tree_digest_missing');
  }else{
    try{
      const root=resolve(artifactRoot);
      // The exact manifest and entrypoint verified above MUST belong to the
      // pinned tree. Otherwise a valid pin from an unrelated build is useless.
      const configRel=relative(root,resolve(candidateConfigPath))
        .split('\\').join('/');
      const entryRel=relative(root,resolve(bundlePath))
        .split('\\').join('/');
      if(!((configRel==='wrangler.json'&&entryRel==='index.js')||
           (configRel==='server/wrangler.json'&&
            entryRel==='server/index.js')))
        throw Error('artifact_root_mismatch');
      const tree=fingerprintArtifactTree(root);
      result.artifactTreeSha256=tree.sha256;
      result.artifactTreeFileCount=tree.fileCount;
      if(tree.sha256!==expectedArtifactTreeSha256)
        result.blockers.push('artifact_tree_digest_mismatch');
    }catch{result.blockers.push('artifact_tree_unavailable_or_unsafe')}
  }
  result.compiledArtifactCompatible=result.blockers.length===0;
  return result;
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  const args=process.argv.slice(2);
  const flag=name=>args.includes(name)?args[args.indexOf(name)+1]:undefined;
  const result=verifyCompiledSite({
    baselineConfigPath:flag('--baseline'),
    candidateConfigPath:flag('--candidate'),
    bundlePath:flag('--bundle'),
    expectedBundleSha256:flag('--bundle-sha256'),
    artifactRoot:flag('--artifact-root'),
    expectedArtifactTreeSha256:flag('--artifact-tree-sha256')
  });
  console.log(JSON.stringify(result,null,2));
  process.exitCode=result.compiledArtifactCompatible?0:2;
}
