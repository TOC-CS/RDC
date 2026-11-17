import test from 'node:test';
import assert from 'node:assert/strict';
import {renderDeckHtml} from '../src/deck.mjs';
const deck={title:'Live output integrity',slides:[
 {id:'welcome',title:'Welcome'}, {id:'song',title:'Song'}
]};
test('live read-only output forbids local arrow keys, buttons and postMessage from desynchronizing the projection',()=>{
 const html=renderDeckHtml(deck,{liveEventsPath:'/v1/view-events?key=unit-test-viewer-secret',
   deckVersion:'test-version'});
 assert.match(html,/EventSource/);
 assert.match(html,/v1\/view-events/);
 assert.doesNotMatch(html,/document\.addEventListener\('keydown'/);
 assert.doesNotMatch(html,/window\.addEventListener\('message'/);
 assert.match(html,/prev'\)\.hidden=true/);
 assert.match(html,/next'\)\.hidden=true/);
});
test('standalone offline presentation still permits operator keyboard and navigation',()=>{
 const html=renderDeckHtml(deck);
 assert.match(html,/document\.addEventListener\('keydown'/);
 assert.match(html,/window\.addEventListener\('message'/);
 assert.match(html,/document\.getElementById\('next'\)\.addEventListener/);
 assert.doesNotMatch(html,/EventSource/);
});
