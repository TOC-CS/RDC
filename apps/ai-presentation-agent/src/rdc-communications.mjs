/**
 * Source-bound Presentation Agent draft and receipt adapter for the EXISTING
 * RDC ChatRoom / Atlas Bus v1 transport.
 *
 * No new queue, local database, browser composer, chat session, microphone,
 * projector, OBS or BandMates sound action exists here. All messages remain
 * inert until a separately authenticated RDC/Atlas host binds a recipient.
 */
const SESSION=/^[A-Za-z0-9._:-]{1,128}$/;
const KEY=/^[A-Za-z0-9._:-]{1,200}$/;
const SLIDE=/^[A-Za-z0-9._-]{1,80}$/;
const UUID4=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const MODES=new Set(['manual','assisted','automatic']);
// Only the existing source-bound status serializer can mint an admissible
// outbound draft. A forged schema string or cloned object has no authority.
const trustedDrafts=new WeakSet();
const valid=(v,pattern,label)=>{
 if(typeof v!=='string'||!pattern.test(v))throw new Error('Invalid '+label+'.');
 return v;
};
const roomMembers=(input,local)=>{
 if(!Array.isArray(input)||input.length<2||input.length>3||
    input.some(x=>typeof x!=='string'||!SESSION.test(x))||
    new Set(input).size!==input.length||!input.includes(local))
   throw new Error('A room requires two or three distinct valid participants including the local session.');
 return Object.freeze([...input].sort());
};
function safeStatus(snapshot){
 if(!snapshot||typeof snapshot!=='object'||Array.isArray(snapshot))
   throw new Error('A presentation director status snapshot is required.');
 const slide=snapshot.current;
 const id=slide?.id;
 if(id!=null&&(!SLIDE.test(id)||typeof id!=='string'))
   throw new Error('Invalid public slide identifier.');
 const section=slide?.section;
 if(section!=null&&(typeof section!=='string'||section.length>100))
   throw new Error('Invalid public song-section label.');
 const occurrence=slide?.occurrence;
 if(occurrence!=null&&(!Number.isSafeInteger(occurrence)||occurrence<1||occurrence>10000))
   throw new Error('Invalid public song-section occurrence.');
 const index=snapshot.index;
 const mode=MODES.has(snapshot.mode)?snapshot.mode:'manual';
 return Object.freeze({
   schema:'toc.presentation.room-status/v1',
   presentationLoaded:id!=null,
   slideId:id??null,
   index:Number.isSafeInteger(index)&&index>=0&&index<=1000?index:null,
   ...(section?{section:section.slice(0,100)}:{}),
   ...(occurrence!=null?{occurrence}:{}),
   mode,started:snapshot.started===true,held:snapshot.held===true,
   armed:snapshot.armed===true,outputFaulted:snapshot.outputFaulted===true,
   outputReadbackVerified:false,automaticStageOrStreamControl:false
 });
}
export function preparePresentationRoomStatus({
 snapshot,roomMembers:participants,localSessionId,roomKey,requestId
}={}){
 const local=valid(localSessionId,SESSION,'local bound session ID');
 const key=valid(requestId,KEY,'stable room request key');
 const room=valid(roomKey,KEY,'room key');
 const members=roomMembers(participants,local);
 const recipients=Object.freeze(members.filter(v=>v!==local));
 const status=safeStatus(snapshot);
 const text=JSON.stringify(status);
 if(text.length>3000)throw new Error('Safe room status exceeds bounded RDC message limit.');
 const draft=Object.freeze({
   schema:'toc.presentation.rdc-room-draft/v1',
   sourceSessionId:local,roomKey:room,key,roomMembers:members,
   expectedRecipients:recipients,roomSize:members.length,
   text,
   requiresAuthenticatedRdcBinding:true,
   directChatPushAllowed:false,liveChatObserved:false,
   applied:false
 });
 trustedDrafts.add(draft);
 return draft;
}
export class PresentationRoomDelivery{
 constructor({boundPrincipal=null,operatorApproved=false,roomSend=null}={}){
   this.bound=boundPrincipal;
   this.approved=operatorApproved===true;
   this.roomSend=roomSend;
   this.receipts=new Map();
 }
 async send(draft){
   if(!draft||typeof draft!=='object'||!trustedDrafts.has(draft)||
      draft.schema!=='toc.presentation.rdc-room-draft/v1')
     throw new Error('A trusted validated Presentation Agent room draft is required.');
   if(!this.approved||typeof this.roomSend!=='function'||
      this.bound?.verified!==true||this.bound?.project!=='rdc')
     return {state:'HELD',liveChatObserved:false,actionConfirmed:false,duplicate:false};
   if(this.bound.sessionId!==draft.sourceSessionId||
      !SESSION.test(this.bound.sessionId))
     throw new Error('Room source identity conflicts with authenticated host binding.');
   const signature=JSON.stringify({
     roomMembers:draft.roomMembers,roomKey:draft.roomKey,text:draft.text
   });
   const prior=this.receipts.get(draft.key);
   if(prior){
     if(prior.signature!==signature)
       throw new Error('RDC room idempotency key conflict: destination or content changed.');
     return {...prior.result,duplicate:true};
   }
   if(this.receipts.size>=4096)
     throw new Error('RDC room receipt capacity reached. Begin a separate authorized room.');
   const record={signature,result:{
     state:'OUTCOME_UNKNOWN',liveChatObserved:false,
     actionConfirmed:false,duplicate:false
   }};
   this.receipts.set(draft.key,record);
   try{
     // Actual RDC transport owns recipient fanout, immutable envelope IDs,
     // correlation, per-recipient authorization, fetch/ack and direct-chat
     // ContinuityGate. This side does not create or resend envelopes.
     const outcome=await this.roomSend({
       members:[...draft.roomMembers],roomKey:draft.roomKey,
       key:draft.key,text:draft.text
     });
     const scope=outcome?.scope;
     const receipts=outcome?.receipts;
     if(receipts&&typeof receipts==='object'&&
        draft.expectedRecipients.every(id=>receipts[id]?.message_id)){
       record.result={
         state:scope==='synthetic_fixture_only'?'SYNTHETIC_ENQUEUED':'QUEUED_UNOBSERVED',
         roomId:typeof outcome?.room_id==='string'?outcome.room_id:null,
         recipientCount:draft.expectedRecipients.length,
         liveChatObserved:false,actionConfirmed:false,duplicate:false
       };
     }
   }catch{
     // The bus may have accepted a message before the transport failed.
     // An identical call returns the same UNKNOWN receipt, never replays.
   }
   return {...record.result};
 }
}
export function preparePresentationRoomReply(envelope,{
 localSessionId,authenticatedSource=null,snapshot
}={}){
 if(!authenticatedSource)return Object.freeze({
   state:'UNVERIFIED_SOURCE',executionAllowed:false
 });
 const local=valid(localSessionId,SESSION,'local recipient session');
 if(!envelope||typeof envelope!=='object'||Array.isArray(envelope)||
    envelope.schema_version!=='atlas.bus.message.v1')
   throw new Error('Invalid authenticated RDC room envelope.');
 if(envelope.destination_session_id!==local)
   throw new Error('RDC message recipient or destination is not this presentation session.');
 const from=valid(envelope.source_session_id,SESSION,'authenticated source session');
 if(from!==authenticatedSource)
   throw new Error('RDC room authenticated source mismatch.');
 const payload=envelope.payload;
 if(!UUID4.test(envelope.message_id)||!UUID4.test(envelope.correlation_id)||
    !payload||payload.channel!=='chat-room'||payload.room_id!==envelope.correlation_id)
   throw new Error('RDC room identity or correlation mismatch.');
 const members=roomMembers(payload.participants,local);
 if(!members.includes(from))
   throw new Error('RDC room authenticated source is outside the permitted participants.');
 const message=payload.text;
 if(typeof message!=='string'||message.length>3000)
   throw new Error('RDC room request is invalid or exceeds message bound.');
 // A pause, stop, reviewer decision or control-priority envelope cannot
 // obtain a preapproved status reply merely by carrying status-shaped text.
 if(envelope.message_type!=='question'||envelope.priority!=='normal'||
    envelope.source_project!=='rdc'||envelope.destination_project!=='rdc'||
    !Number.isSafeInteger(envelope.hop_count)||
    envelope.hop_count<0||envelope.hop_count>3)
   return Object.freeze({
     state:'MANUAL_REVIEW',executionAllowed:false,
     stageOrStreamModified:false,chatAutomaticallyInterrupted:false
   });
 if(!['presentation status?','presentation status','status','status?'].includes(message.trim().toLowerCase()))
   return Object.freeze({
     state:'MANUAL_REVIEW',executionAllowed:false,
     stageOrStreamModified:false,chatAutomaticallyInterrupted:false
   });
 return Object.freeze({
   state:'DRAFT_ONLY',roomId:envelope.correlation_id,replyTo:envelope.message_id,
   text:JSON.stringify(safeStatus(snapshot)),
   executionAllowed:false,stageOrStreamModified:false,
   directChatPushAllowed:false,liveChatObserved:false
 });
}
