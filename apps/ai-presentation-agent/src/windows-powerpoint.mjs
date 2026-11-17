import {spawn} from 'node:child_process';

// Conservative Windows adapter. Only attaches to an already-running slideshow;
// it never creates PowerPoint, opens a file, takes focus or presses keys.
// Requires Windows PowerShell and PowerPoint COM in an interactive owner session.
export function buildWindowsPowerPointScript(action,index){
 const allowed=new Set(['next','previous','goto','readback']);
 if(!allowed.has(action))throw new Error('Unsupported Windows PowerPoint action.');
 if(action==='goto'&&(!Number.isInteger(index)||index<0||index>10000))
   throw new Error('Invalid Windows PowerPoint slide index.');
 const base=[
   "$ErrorActionPreference='Stop'",
   "$ppt=[Runtime.InteropServices.Marshal]::GetActiveObject('PowerPoint.Application')",
   "if($null -eq $ppt){throw 'PowerPoint is not running.'}",
   "if($ppt.SlideShowWindows.Count -lt 1){throw 'No PowerPoint slideshow is currently running.'}",
   '$view=$ppt.SlideShowWindows.Item(1).View'
 ];
 if(action==='next')base.push('$view.Next()');
 if(action==='previous')base.push('$view.Previous()');
 if(action==='goto')base.push('$view.GotoSlide('+String(index+1)+')');
 base.push('[Console]::Out.WriteLine([int]$view.CurrentShowPosition)');
 return base.join(';');
}
export class PowerPointWindowsAdapter{
 constructor({platform=process.platform,runner=spawn,timeoutMs=3000}={}){
   if(platform!=='win32')throw new Error('Windows PowerPoint adapter requires an actual Windows host.');
   if(!Number.isInteger(timeoutMs)||timeoutMs<200||timeoutMs>30000)
     throw new Error('Invalid Windows PowerPoint timeout.');
   this.name='powerpoint-windows';
   this.external=true;
   this.runner=runner;
   this.timeoutMs=timeoutMs;
 }
 async execute(action,index){
   const source=buildWindowsPowerPointScript(action,index);
   const encoded=Buffer.from(source,'utf16le').toString('base64');
   return new Promise((resolve,reject)=>{
     let child,finished=false,out='',err='';
     try{
       child=this.runner('powershell.exe',
         ['-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',encoded],
         {windowsHide:true,stdio:['ignore','pipe','pipe']});
     }catch(error){reject(error);return;}
     const finish=(error,value)=>{
       if(finished)return;
       finished=true;clearTimeout(timer);
       return error?reject(error):resolve(value);
     };
     const timer=setTimeout(()=>{
       if(typeof child.kill==='function')child.kill('SIGTERM');
       finish(new Error('Windows PowerPoint operation timed out.'));
     },this.timeoutMs);
     child.stdout?.on('data',buffer=>{if(out.length<2048)out+=String(buffer);});
     child.stderr?.on('data',buffer=>{if(err.length<2048)err+=String(buffer);});
     child.once('error',error=>finish(error));
     child.once('exit',code=>{
       if(code!==0)return finish(new Error('Windows PowerPoint COM operation failed: '+err.slice(0,500)));
       const match=out.trim().match(/^\d+$/);
       if(!match)return finish(new Error('Windows PowerPoint returned an invalid current slide index.'));
       const position=Number(match[0]);
       if(!Number.isSafeInteger(position)||position<1)
         return finish(new Error('Windows PowerPoint returned an invalid slide position.'));
       finish(null,{supported:true,index:position-1,source:'powerpoint-windows-com'});
     });
   });
 }
 async readback({expectedIndex=null}={}){
   const observed=await this.execute('readback');
   return {...observed,confirmed:Number.isInteger(expectedIndex)&&observed.index===expectedIndex};
 }
 async show(index){
   const observed=await this.execute('goto',index);
   if(observed.index!==index)throw new Error('Windows PowerPoint slide readback mismatch.');
   return {ok:true,index,confirmed:true};
 }
 async next(slide){
   const observed=await this.execute('next');
   if(Number.isInteger(slide?.position)&&observed.index!==slide.position)
     throw new Error('Windows PowerPoint next-slide readback mismatch.');
   return {ok:true,index:observed.index,confirmed:Number.isInteger(slide?.position)};
 }
 async previous(slide){
   const observed=await this.execute('previous');
   if(Number.isInteger(slide?.position)&&observed.index!==slide.position)
     throw new Error('Windows PowerPoint previous-slide readback mismatch.');
   return {ok:true,index:observed.index,confirmed:Number.isInteger(slide?.position)};
 }
}
