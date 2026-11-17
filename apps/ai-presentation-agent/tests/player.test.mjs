import test from 'node:test';
import assert from 'node:assert/strict';
import {renderDeckHtml,buildDeck} from '../src/deck.mjs';

test('presentation creator builds readable slide cards from structured sections',()=>{
 const deck=buildDeck({title:'Annual Review',sections:[{title:'Overview',points:['Year in review','Key goals']},{title:'Results',points:['Progress and lessons']}],theme:'dark'});
 assert.equal(deck.slides.length,3);
 assert.match(deck.slides[1].text,/Year in review/);
 assert.equal(deck.theme,'dark');
});
test('player output escapes untrusted slide text and includes navigation',()=>{
 const html=renderDeckHtml({title:'<img src=x onerror=alert(1)>',slides:[{id:'x',title:'Hello',text:'<script>alert(1)</script>'}]});
 assert.ok(!html.includes('<script>alert(1)</script>'));
 assert.ok(html.includes('&lt;script&gt;'));
 assert.match(html,/function advance/);
 assert.match(html,/Content-Security-Policy/);
});
test('creator limits slide count and text size',()=>{
 assert.throws(()=>buildDeck({title:'Bad',sections:Array.from({length:1100},(_,i)=>({title:String(i)}))}),/too many/i);
});
test('presentation theme is kept during load and exported player',async()=>{
 const {PresentationDirector}=await import('../src/director.mjs');
 const {MemoryAdapter}=await import('../src/adapters.mjs');
 const director=new PresentationDirector({adapter:new MemoryAdapter()});
 director.load(buildDeck({title:'Review',theme:'light',sections:[]}));
 assert.equal(director.deck.theme,'light');
 assert.equal(director.snapshot().theme,'light');
 assert.match(renderDeckHtml(director.deck),/color-scheme:light/);
});
