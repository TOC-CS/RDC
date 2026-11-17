import {createHash} from 'node:crypto';

// Immutable director decks can reuse their content digest across thousands of
// cue updates. Mutable or partially mutable decks recompute on every call to
// avoid stale versioning when the user edits content.
export function createDeckVersionHasher(){
 const memo=new WeakMap();
 return state=>{
   const slides=Array.isArray(state?.slides)?state.slides:[];
   const title=String(state?.title??'');
   const theme=String(state?.theme??'dark');
   if(Object.isFrozen(slides)){
     const entry=memo.get(slides);
     if(entry&&entry.title===title&&entry.theme===theme)
       return entry.version;
   }
   const version=createHash('sha256')
     .update(JSON.stringify({title,theme,slides}))
     .digest('hex').slice(0,24);
   if(Object.isFrozen(slides)&&slides.every(value=>
     value!==null&&typeof value==='object'&&Object.isFrozen(value)))
     memo.set(slides,{title,theme,version});
   return version;
 };
}
