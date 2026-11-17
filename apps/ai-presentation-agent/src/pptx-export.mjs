import PptxGenJS from 'pptxgenjs';

const MAX_SLIDES=200;
const MAX_TEXT=10000;
const MAX_RESULT_BYTES=64*1024*1024;
function validateText(value,label,max=MAX_TEXT){
 if(value===undefined||value===null)return '';
 if(typeof value!=='string'||value.length>max||/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/.test(value))
   throw new Error(label+' exceeds the supported content limit.');
 return value;
}
function verifyDeck(deck){
 if(!deck||typeof deck!=='object'||!Array.isArray(deck.slides)||deck.slides.length<1||
    deck.slides.length>MAX_SLIDES)throw new Error('PowerPoint export supports 1 to 200 slides.');
 validateText(deck.title,'Deck title',300);
 if(!['dark','light',undefined,null].includes(deck.theme))throw new Error('Unsupported presentation theme.');
 for(const slide of deck.slides){
   if(!slide||typeof slide!=='object')throw new Error('Invalid slide.');
   validateText(slide.id,'Slide ID',80);
   validateText(slide.title,'Slide title',500);
   validateText(slide.text,'Slide text');
   validateText(slide.reference,'Scripture reference',150);
   validateText(slide.notes,'Speaker notes',5000);
 }
}
function fontSize(text,{kind='content',minimum=22,maximum=34}={}){
 const value=text.replace(/\r/g,'');
 const lengths=value.split('\n').map(line=>line.length);
 const lines=lengths.length;
 const total=value.length;
 let size=maximum;
 if(kind==='lyrics')size=40;
 if(lines>4)size-=Math.min(14,(lines-4)*2.5);
 if(total>150)size-=Math.min(12,(total-150)/55);
 if(lengths.some(l=>l>75))size-=5;
 return Math.max(minimum,Math.min(maximum+(kind==='lyrics'?8:0),Math.round(size)));
}
/**
 * Portable OOXML/PowerPoint generation. PowerPoint, Keynote and Google Slides
 * can import standard PPTX presentations, with app-specific feature loss
 * possible. This export does not operate or launch another presentation app.
 * All slide words originate from the caller-supplied deck.
 */
export async function renderDeckPptx(deck){
 verifyDeck(deck);
 const pptx=new PptxGenJS();
 pptx.layout='LAYOUT_WIDE'; // 13.333 x 7.5 in, standard 16:9.
 pptx.author='AI Presentation Agent';
 pptx.subject='User-authored presentation export';
 pptx.title=validateText(deck.title,'Deck title',300)||'Presentation';
 pptx.lang='en-US';
 const dark=deck.theme!=='light';
 const base=dark?'081526':'F7FAFD';
 const text=dark?'F7FAFE':'192B42';
 const muted=dark?'A9BBD2':'566B82';
 const accent=dark?'16DBAC':'156CB6';
 pptx.theme={headFontFace:'Arial',bodyFontFace:'Arial',lang:'en-US'};
 const shape=pptx.ShapeType.rect;
 for(let i=0;i<deck.slides.length;i++){
   const item=deck.slides[i];
   const slide=pptx.addSlide();
   slide.background={color:base};
   slide.addShape(shape,{x:0.76,y:0.6,w:0.07,h:0.78,
     line:{color:accent,transparency:100},
     fill:{color:accent}});
   const isCover=i===0&&['title','cover'].includes(item.kind??'');
   const titleText=validateText(item.title,'Slide title',500)||validateText(deck.title,'Deck title',300)||'Presentation';
   const titleFont=isCover?52:fontSize(titleText,{minimum:30,maximum:43});
   slide.addText(titleText,{x:1.05,y:isCover?1.8:0.58,w:11.3,h:isCover?1.75:1.32,
     fontFace:'Arial',fontSize:titleFont,bold:true,
     color:text,margin:0,
     valign:'mid',align:isCover?'center':'left',
     breakLine:false,transparency:0});
   if(item.text){
     const body=validateText(item.text,'Slide text');
     const lyric=item.kind==='lyrics';
     slide.addText(body,{
       x:1.05,y:isCover?3.9:2.0,w:11.15,h:isCover?1.7:4.35,
       fontFace:'Arial',
       fontSize:isCover?29:fontSize(body,{kind:lyric?'lyrics':'content',minimum:20,maximum:lyric?37:32}),
       color:text,margin:0.04,
       breakLine:false,
       valign:lyric||isCover?'mid':'top',
       align:isCover?'center':'left',
       paraSpaceAfterPt:lyric?12:8,
       lineSpacingMultiple:1.12
     });
   }
   if(item.reference){
     slide.addText(validateText(item.reference,'Scripture reference',150),{
       x:1.06,y:6.72,w:9.6,h:0.36,fontSize:16,
       fontFace:'Arial',color:muted,margin:0
     });
   }
   slide.addText(String(i+1)+' / '+String(deck.slides.length),{
     x:11.43,y:6.93,w:1.12,h:0.28,
     fontFace:'Arial',fontSize:11,color:muted,margin:0,align:'right'
   });
   if(item.notes){
     slide.addNotes(validateText(item.notes,'Speaker notes',5000));
   }
 }
 const data=await pptx.write({outputType:'nodebuffer',compression:true});
 const buffer=Buffer.isBuffer(data)?data:Buffer.from(data);
 if(buffer.length<100||buffer.length>MAX_RESULT_BYTES)
   throw new Error('PowerPoint export exceeds supported output size.');
 return buffer;
}
