import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,access} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join} from 'node:path';

const root=fileURLToPath(new URL('..',import.meta.url));
const lib=join(root,'skills/ai-presentation-agent/worship');
const load=async path=>JSON.parse(await readFile(join(lib,path),'utf8'));

test('worship research pack retains 26 unique training modules with actionable objectives',async()=>{
 const items=await load('data/modules.json');
 assert.equal(items.length,26);
 assert.equal(new Set(items.map(x=>x.id)).size,26);
 for(const item of items){
   assert.ok(item.id);
   assert.ok(item.title);
   assert.ok(item.learningOutcome?.length>35);
   assert.ok(item.acceptance?.length>20);
 }
});
test('worship research pack retains 18 unique evaluation scenarios and explicit prohibited behavior',async()=>{
 const cases=await load('data/evaluation-scenarios.json');
 assert.equal(cases.length,18);
 assert.equal(new Set(cases.map(x=>x.id)).size,18);
 for(const item of cases){
   assert.ok(item.situation?.length>30);
   assert.ok(item.expected?.length>30);
   assert.ok(item.prohibited?.length>20);
   assert.ok(item.verification?.length>20);
 }
});
test('all reference and implementation files in the new worship skill are preserved and readable',async()=>{
 for(const path of [
  'SKILL.md','README.md','HANDOFF_NOTES.md','IMPLEMENTATION_PLAN.md',
  'DESIGN.md','research/PROPRESENTER_OBS_RESEARCH.md','research/SOURCES.md',
  'references/CHURCH_SERVICE_PLAYBOOK.md','references/LYRICS_AND_SCRIPTURE.md',
  'references/OUTPUTS_AND_STAGE.md','references/LIVESTREAM_OBS_GUIDE.md',
  'references/AI_CUES_AND_COORDINATION.md','references/LICENSING_AND_IMPORT.md'
 ]){
   const body=await readFile(join(lib,path),'utf8');
   assert.ok(body.length>300,path);
 }
 await load('examples/sunday-service.json');
 await load('examples/obs-scene-map.json');
});
test('scenario acceptance matrix preserves zero physical service acceptance claims',async()=>{
 const record=JSON.parse(await readFile(join(root,'evidence/worship-evaluation-matrix-20261116.json'),'utf8'));
 assert.equal(record.researchModules,26);
 assert.equal(record.evaluationScenarios,18);
 assert.equal(record.records.length,18);
 assert.equal(record.physicalAndStreamingAccepted,0);
 assert.equal(record.productionReady,false);
 assert.ok(record.softwareEvidenceMapped>=15);
 for(const row of record.records){
   assert.equal(row.actualVenueAccepted,false);
   assert.ok(row.remainingGate.length>20);
   for(const file of row.softwareEvidence)await access(join(root,file));
 }
});
