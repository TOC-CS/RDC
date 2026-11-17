#!/usr/bin/env node
// Declarative learning coverage audit. Test paths are evidence of software
// behavior only; they cannot certify an external livestream or physical venue.
import {readFile,writeFile,access} from 'node:fs/promises';
import {resolve,join} from 'node:path';
const root=resolve(new URL('..',import.meta.url).pathname);
const worship=join(root,'skills/ai-presentation-agent/worship');
const scenarios=JSON.parse(await readFile(join(worship,'data/evaluation-scenarios.json'),'utf8'));
const modules=JSON.parse(await readFile(join(worship,'data/modules.json'),'utf8'));
const assignments={
 'repeat-chorus':[['tests/repeated-cues.test.mjs','tests/bandmates-native-songform.integration.test.mjs'],'Native verified performed section and physical lyric confirmation'],
 'unplanned-scripture':[['tests/worship-service.test.mjs','tests/worship-mcp-privacy.test.mjs'],'Authorized NKJV full-text entitlement and live pastor recognition'],
 'preliminary-transcript':[['tests/host-voice.test.mjs','tests/voice-punctuation.test.mjs'],'Actual microphone, acoustics and vocal transcription qualification'],
 'stage-leak':[['tests/worship-stage-security.test.mjs','tests/worship-stream-privacy.test.mjs'],'Independent stage monitor, projector and live camera capture inspection'],
 'wrong-program-scene':[['tests/obs-wire.integration.test.mjs','tests/obs-monitor-wire.integration.test.mjs'],'Actual OBS Program scene switching, preview and broadcast readback'],
 'preview-not-program':[['tests/obs-monitor-wire.integration.test.mjs'],'Actual OBS Studio Mode Preview and Program qualification'],
 'stream-network-loss':[['tests/obs-monitor-failure.test.mjs'], 'Actual streaming provider outage and authenticated stream status observation'],
 'audio-disconnect':[['tests/microphone.test.mjs'], 'Physical audio device dropout and house/stream bus isolation'],
 'wrongly-licensed-lyrics':[['tests/worship-service.test.mjs','tests/worship-library.test.mjs'],'Owner and publisher rights review for the target venue and platform'],
 'private-talkback':[['tests/private-talkback.test.mjs'],'Actual private stage output routing and speaker/stream isolation'],
 'loopback-screen':[['tests/watch.test.mjs','tests/offline-vision-pipeline.test.mjs'],'Independent physical stage camera lens/field-of-view validation'],
 'service-order-change':[['tests/director.test.mjs','tests/worship-library.test.mjs'],'Actual volunteer rehearsal of unplanned service edits'],
 'camera-safety':[['tests/watch.test.mjs'],'Real operator-approved camera permissions and dropout/misrecognition'],
 'slide-hold':[['tests/director.test.mjs','tests/external-fault-latch.test.mjs'],'Physical projector confirmation with operator hold and recovery'],
 'stream-stop':[['tests/obs-monitor.test.mjs'],'Real separately approved StopStreaming/StopRecord authority and provider readback'],
 'crash-recovery':[['tests/managed-crash-recovery.test.mjs','tests/managed-unload-failure.test.mjs'],'Actual projector and broadcast recovery with full physical reauthorization'],
 'ndisdi-availability':[['tests/venue-output-readiness.test.mjs'], 'Actual NDI/SDI compatible hardware and installed drivers'],
 'live-comments':[['tests/live-comments.test.mjs','tests/live-comments-mcp.test.mjs'],'Real authorized social account APIs and moderation; item 9 remains queued']
};
const runlog=process.argv[2]??join(root,'evidence/worship-library-obs-all-tests-20261116.log');
const log=await readFile(runlog,'utf8');
const tests=Number(log.match(/ℹ tests\s+(\d+)/)?.[1]);
const failures=Number(log.match(/ℹ fail\s+(\d+)/)?.[1]);
if(!Number.isSafeInteger(tests)||!Number.isSafeInteger(failures)||failures!==0)
 throw new Error('The worship evidence matrix requires a completed zero-failure regression report.');
if(modules.length!==26||scenarios.length!==18||
 new Set(modules.map(x=>x.id)).size!==26||
 new Set(scenarios.map(x=>x.id)).size!==18)
 throw new Error('Worship research inventory is incomplete or contains duplicate identifiers.');
const records=[];
for(const row of scenarios){
 const [files=[],gate]=assignments[row.id]??[[],'No acceptance mapping entered'];
 for(const name of files)await access(join(root,name));
 records.push({
   scenario:row.id,
   softwareEvidence:files,
   softwareEvidenceAvailable:files.length>0,
   softwareQualifiedByTests:files.length>0&&failures===0,
   actualVenueAccepted:false,
   remainingGate:gate
 });
}
const output={
 schema:'toc.worship-training-evaluation/v1',
 researchModules:modules.length,evaluationScenarios:scenarios.length,
 currentSoftwareSuite:{tests,failures,log:runlog.replace(root+'/','')},
 softwareEvidenceMapped:records.filter(r=>r.softwareEvidenceAvailable).length,
 physicalAndStreamingAccepted:0,
 productionReady:false,
 caveat:'A test file and a zero-failure software suite establish evidence for individual software paths, not end-to-end live worship acceptance.',
 records
};
const dest=join(root,'evidence/worship-evaluation-matrix-20261116.json');
await writeFile(dest,JSON.stringify(output,null,2)+'\n');
const clean=s=>String(s).replace(/\|/g,'/');
const markdown=[
 '# Worship production training and acceptance coverage',
 '',
 'Status: software evidence available for selected scenarios; whole worship production system remains OPEN.',
 'Research source: 26 modules, 18 evaluation scenarios, and the reviewed ProPresenter/OBS skills pack.',
 'Regression suite: '+tests+' tests passed, '+failures+' failures.',
 '',
 '| Scenario | Software evidence | Live / owner acceptance still required |',
 '| --- | --- | --- |',
 ...records.map(r=>'| '+r.scenario+' | '+(r.softwareEvidenceAvailable?r.softwareEvidence.map(x=>x.split('/').at(-1)).join(', '):'None yet')+' | '+clean(r.remainingGate)+' |'),
 '',
 'Physical venue scenarios accepted: 0. OBS livestream, projector, stage monitor, live microphone/camera, permissions, licensing, mobile device and real platform qualification remain independent. The live-comments task remains queued for authorized platform rollout. Test-source paths are indicators, not blanket certification.',
 ''
].join('\n');
await writeFile(join(root,'docs/WORSHIP-EVALUATION-MATRIX-20261116.md'),markdown);
process.stdout.write(JSON.stringify({
 modules:modules.length,scenarios:scenarios.length,
 mapped:output.softwareEvidenceMapped,
 physicalAccepted:0,tests,failures,productionReady:false
})+'\n');
