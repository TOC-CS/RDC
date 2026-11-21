import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,writeFileSync,rmSync,readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {runRollbackReadback} from '../../scripts/rdc2-rollback-readback.mjs';

const current=resolve(fileURLToPath(new URL('../../lib/v2/rdc2-journal.mjs',import.meta.url)));
const sha=text=>createHash('sha256').update(text).digest('hex');
const source=readFileSync(current);
const args={candidatePath:current,expectedSha256:sha(source)};

test('exact source-hash-pinned rollback reader can recover archived mutations without replay',async()=>{
  const result=await runRollbackReadback(args);
  assert.equal(result.sourceCompatible,true);
  assert.equal(result.releaseApproved,false);
  assert.equal(result.hostedProtectedVersionVerified,false);
  assert.equal(result.candidateSha256,args.expectedSha256);
  assert.equal(result.checks.confirmedArchivedDuplicate,true);
  assert.equal(result.checks.expiredQueuedDuplicate,true);
  assert.equal(result.checks.originalIdPreserved,true);
  assert.equal(result.checks.expiredResultWithheld,true);
  assert.equal(result.checks.forgedDigestRejected,true);
  assert.equal(result.checks.foreignOwnerRejected,true);
  assert.equal(result.checks.freshUnrelatedAdmission,true);
});
test('unpinned or modified source is rejected BEFORE any candidate module evaluates',async()=>{
  await assert.rejects(runRollbackReadback({candidatePath:current}),/expected SHA-256 required/);
  await assert.rejects(runRollbackReadback({...args,expectedSha256:'0'.repeat(64)}),
    /candidate source SHA-256 mismatch/);
});
test('historical rollback missing archived-ID awareness is explicitly unsafe',async()=>{
  const dir=mkdtempSync(join(tmpdir(),'rdc2-unsafe-reader-'));
  try{
    // Intentionally synthetic unsafe reader. The full historical V2 source
    // is tested separately from a pinned Git revision during local QA.
    const bad=join(dir,'rdc2-journal.mjs');
    writeFileSync(bad,source.toString().replace(
      "this.first('SELECT * FROM rdc2_ops WHERE principal=? AND request_key=?',principal,requestKey) ??\n        this.first('SELECT * FROM rdc2_tombstones WHERE principal=? AND request_key=?',principal,requestKey)",
      "this.first('SELECT * FROM rdc2_ops WHERE principal=? AND request_key=?',principal,requestKey)"));
    const modified=readFileSync(bad);
    assert.notEqual(sha(modified),args.expectedSha256);
    const result=await runRollbackReadback({candidatePath:bad,expectedSha256:sha(modified)});
    assert.equal(result.sourceCompatible,false);
    assert.equal(result.releaseApproved,false);
    assert.equal(result.checks.confirmedArchivedDuplicate,false);
    assert.match(result.blockers.join(','),/unsafe_replay|archived/i);
  }finally{rmSync(dir,{recursive:true,force:true})}
});
test('CLI returns nonzero and machine-readable fail-closed receipt for wrong digest',()=>{
  const script=resolve(fileURLToPath(new URL('../../scripts/rdc2-rollback-readback.mjs',import.meta.url)));
  const output=(()=>{try{execFileSync(process.execPath,[script,'--candidate',current,
    '--sha256','0'.repeat(64)],{encoding:'utf8'});return null}
   catch(error){return error}})();
  assert.equal(output?.status,2);
  const receipt=JSON.parse(output.stdout);
  assert.equal(receipt.sourceCompatible,false);
  assert.equal(receipt.releaseApproved,false);
  assert.match(receipt.blockers.join(','),/sha256_mismatch/);
});
