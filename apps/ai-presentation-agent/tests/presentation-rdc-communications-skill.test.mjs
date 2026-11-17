import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('..',import.meta.url));

test('Presentation Agent skill discovers the existing RDC two-way/three-way communication contract',async()=>{
 const skill=await readFile(root+'skills/ai-presentation-agent/SKILL.md','utf8');
 assert.match(skill,/rdc-communications\.md/);
 assert.match(skill,/three.way|3.way/i);
 assert.match(skill,/Atlas Bus/);
 assert.match(skill,/terminal/);
 assert.match(skill,/direct chat/i);
 assert.match(skill,/unverified|synthetic/i);
});

test('RDC integration reference protects current presentations and describes exact available software tools',async()=>{
 const ref=await readFile(root+'skills/ai-presentation-agent/references/rdc-communications.md','utf8');
 for(const phrase of [
  'atlas.bus.message.v1','rdc.chat_rooms.ChatRoom','rdc.chatctl',
  'presentation_communication_capabilities',
  'presentation_communication_prepare',
  '/v1/communications/capabilities',
  '/v1/communications/prepare','ContinuityGate',
  'synthetic-only','CROSS_PROJECT_DENIED',
  'two-way','three-way','BandMates',
  'mix engineer'
 ])assert.ok(ref.includes(phrase),'Missing communications contract: '+phrase);
 assert.match(ref,/do not.*interrupt|never.*interrupt/i);
 assert.match(ref,/no.*(new|duplicate).*bus|existing.*Atlas Bus/i);
 assert.match(ref,/operator.*grant|operator.*approval/i);
 assert.match(ref,/private.*(notes|stage)|stage.*private/i);
 assert.match(ref,/never.*(automatic.*slide|auto.*advance|live.*output)|does not.*(slide|stream).*control/i);
});

test('integration guide carries actual source/test scope rather than claiming live ChatGPT enrollment',async()=>{
 const doc=await readFile(root+'docs/INTEGRATION.md','utf8');
 assert.match(doc,/RDC.DC.*communication/i);
 assert.match(doc,/read.only.*status|status.*read.only/i);
 assert.match(doc,/synthetic/);
 assert.match(doc,/no.*(real|live).*enrollment|live.*unverified/i);
 assert.match(doc,/cross.project.*(blocked|denied|held)/i);
});
