import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const root=new URL('../skills/ai-presentation-agent/',import.meta.url);
test('installed local Presentation Agent skill documents source-bound worship outputs, privacy controls and hardware gates',async()=>{
 const text=await readFile(new URL('SKILL.md',root),'utf8');
 for(const pattern of [
   /presentation_load_worship/,
   /presentation_worship_rundown/,
   /presentation_worship_visibility_set/,
   /PRESENTATION_ALLOW_WORSHIP_LOOK_EDIT/,
   /stage-clock-status/,
   /PRESENTATION_ALLOW_STAGE_CLOCK/,
   /venue-readiness/,
   /obs-production-status/,
   /private.*stage/i,
   /physical.*(acceptance|projector|monitor)/i
 ])assert.match(text,pattern);
 assert.match(text,/teleprompt.*queued/i);
});
test('local integration guide documents stage-only dual authorization and no native auto-activation',async()=>{
 const text=await readFile(new URL('references/integration.md',root),'utf8');
 assert.match(text,/X-Stage-Credential/);
 assert.match(text,/PRESENTATION_ALLOW_STAGE_CLOCK/);
 assert.match(text,/private.*timer.*(label|caption)/i);
 assert.match(text,/audience.*(black|blank)/i);
 assert.match(text,/OBS.*(read-only|Studio Mode)/i);
 assert.match(text,/separate.*(external|operator)/i);
});
