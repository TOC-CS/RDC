import test from 'node:test';
import assert from 'node:assert/strict';
import {compileWorshipService} from '../src/worship-service.mjs';

const plan=rights=>({
 title:'Rights separation rehearsal',
 items:[{
   id:'song',type:'song',title:'Original Licensed Test Song',rights,
   sections:[{label:'chorus',lines:['Original owner-written lyric line']}],
   order:['chorus']
 }]
});
test('original content authorized for room display but not stream remains hidden in public overlay',()=>{
 const session=compileWorshipService(plan({
   source:'original',displayAuthorized:true,streamAuthorized:false
 }));
 assert.equal(session.publicDeck.slides[0].text,'Original owner-written lyric line');
 assert.equal(session.broadcastDeck.slides[0].text,'');
 assert.ok(session.issues.some(x=>x.type==='livestream_lyrics_rights'));
});
test('original authored music without explicit streaming permission fails closed for broadcast lyrics',()=>{
 const session=compileWorshipService(plan({
   source:'original',displayAuthorized:true
 }));
 assert.equal(session.publicDeck.slides[0].text,'Original owner-written lyric line');
 assert.equal(session.broadcastDeck.slides[0].text,'');
});
test('separate explicit room and stream authorization displays permitted original lyric on both',()=>{
 const session=compileWorshipService(plan({
   source:'original',displayAuthorized:true,streamAuthorized:true
 }));
 assert.equal(session.broadcastDeck.slides[0].text,'Original owner-written lyric line');
});
