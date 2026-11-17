import test from 'node:test';
import assert from 'node:assert/strict';
import {createDeckVersionHasher} from '../src/deck-version.mjs';

const frozenSlides=Object.freeze([
 Object.freeze({id:'a',title:'Intro',text:'Welcome'}),
 Object.freeze({id:'b',title:'Reading',text:'Scripture'})
]);
test('immutable deck hash remains stable across changing active slide position',()=>{
 const fn=createDeckVersionHasher();
 const base={title:'Sunday',theme:'dark',slides:frozenSlides,index:0};
 const a=fn(base),b=fn({...base,index:1});
 assert.equal(a,b);
 assert.match(a,/^[a-f0-9]{24}$/);
});
test('same frozen slide object with updated title/theme invalidates cached layout',()=>{
 const fn=createDeckVersionHasher();
 const first=fn({title:'Sunday',theme:'dark',slides:frozenSlides});
 assert.notEqual(fn({title:'Sunday Evening',theme:'dark',slides:frozenSlides}),first);
 assert.notEqual(fn({title:'Sunday',theme:'light',slides:frozenSlides}),first);
});
test('mutable deck data always recomputes hash after content correction',()=>{
 const fn=createDeckVersionHasher();
 const slides=[{id:'a',text:'before'}],state={title:'Service',theme:'dark',slides};
 const first=fn(state);
 slides[0].text='after';
 assert.notEqual(fn(state),first);
});
test('frozen outer deck with mutable inner slides never reuses stale cached digest',()=>{
 const fn=createDeckVersionHasher();
 const inner={id:'a',text:'before'};
 const slides=Object.freeze([inner]);
 const state={title:'Service',slides};
 const first=fn(state);
 inner.text='after';
 assert.notEqual(fn(state),first);
});
test('empty unloaded deck has a stable safe version and no content leakage',()=>{
 const fn=createDeckVersionHasher();
 const empty=fn({title:'',slides:[]});
 assert.match(empty,/^[a-f0-9]{24}$/);
 assert.equal(fn({title:'',slides:[]}),empty);
});
