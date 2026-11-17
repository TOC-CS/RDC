import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,access} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const file=name=>fileURLToPath(new URL('../skills/ai-presentation-agent/'+name,import.meta.url));

test('RDC skill teaches real durable controller commands without exposing tokens',async()=>{
 const s=await readFile(file('SKILL.md'),'utf8');
 assert.match(s,/node scripts\/presentationctl\.mjs/);
 assert.match(s,/--request-id/);
 assert.match(s,/control\.json/);
 assert.match(s,/viewer-export/);
 assert.match(s,/last-known\.json/);
 assert.match(s,/recoveryPreview|RECOVERED PREVIEW/i);
 assert.match(s,/external.*disarm|disarm.*external/i);
});
test('live presentation operator guidance explicitly protects the private talkback channel',async()=>{
 const s=await readFile(file('SKILL.md'),'utf8');
 const r=await readFile(file('references/managed-session.md'),'utf8');
 assert.match(s,/--output-device/);
 assert.match(s,/--confirm-private-monitor/);
 assert.match(s,/never.*default.*output|default.*speaker.*never/i);
 assert.match(r,/last-known\.json/);
 assert.match(r,/PID|process/i);
 assert.match(r,/held preview|recovered preview/i);
});
test('all referenced skill files exist in the source archive',async()=>{
 for(const ref of ['references/integration.md','references/managed-session.md',
   'references/live-comments.md'])await access(file(ref));
});
test('AI host documentation distinguishes stopping the controller from physically blanking the venue screen',async()=>{
 const skill=await readFile(file('SKILL.md'),'utf8');
 const managed=await readFile(file('references/managed-session.md'),'utf8');
 assert.match(skill,/presentationctl\.mjs stop/);
 assert.match(skill,/native.*(screen|projector|output).*remain|does not.*native.*screen/i);
 assert.match(managed,/presentationctl\.mjs stop/);
 assert.match(managed,/native.*screen|projector.*blank/i);
});
test('RDC skill explains stopped-only unload, durable checkpoint removal and live viewer privacy clearing',async()=>{
 const s=await readFile(file('SKILL.md'),'utf8');
 const m=await readFile(file('references/managed-session.md'),'utf8');
 assert.match(s,/presentationctl\.mjs unload/);
 assert.match(s,/stop.*before.*unload|after.*stop.*unload/i);
 assert.match(s,/PRESENTATION CLEARED/);
 assert.match(m,/presentationctl\.mjs unload/);
 assert.match(m,/last-known\.json/);
 assert.match(m,/cannot.*reappear|does not.*restore|deletes.*checkpoint/i);
});
