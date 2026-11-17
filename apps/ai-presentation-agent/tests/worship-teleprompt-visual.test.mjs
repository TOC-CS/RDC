import test from 'node:test';
import assert from 'node:assert/strict';
import {renderStageConfidenceHtml} from '../src/worship-stage-view.mjs';

const source='/v1/stage-events?key=stage-token-without-public-access';

test('stage-only teleprompt visual has current/next phrases and distinct mirrored pace controls',()=>{
 const html=renderStageConfidenceHtml({eventsPath:source});
 for(const id of ['teleprompt','teleprompt-role','teleprompt-current',
  'teleprompt-next','teleprompt-progress']){
  assert.match(html,new RegExp('id="'+id+'"'),id);
 }
 assert.match(html,/state\.teleprompt/);
 assert.match(html,/\.dataset\.mirrored/);
 assert.match(html,/scrollSpeed/);
 assert.match(html,/fontScale/);
 assert.match(html,/\.textContent=String\(text\?\?''\)/);
 assert.doesNotMatch(html,/\.innerHTML\s*=/);
 assert.equal(html.includes('PRIVATE_PASTOR_STAGE_NOTE_SECRET'),false);
 assert.equal(html.includes('http://127.0.0.1:4455'),false);
});

test('private stage connection loss and service clear remove any stale teleprompt text',()=>{
 const html=renderStageConfidenceHtml({eventsPath:source});
 assert.match(html,/STAGE CONNECTION LOST/);
 assert.match(html,/teleprompt-current/);
 assert.match(html,/teleprompt-next/);
 assert.match(html,/feed\.onerror=.*bind\('teleprompt-current',''\)/);
 assert.match(html,/feed\.onerror=.*bind\('teleprompt-next',''\)/);
 assert.match(html,/state\.loaded===false/);
 assert.match(html,/teleprompt-current',''\)/);
 assert.match(html,/teleprompt-next',''\)/);
});
