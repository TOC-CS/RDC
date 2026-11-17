#!/usr/bin/env node
// Actual BandMates owner companion API, read-only.
// Does not request MIDI/audio, start sessions, move windows or arm output.
import {BandMatesLiveLink} from '../integrations/bandmates-live.mjs';
try{
 const status=await new BandMatesLiveLink({
   baseUrl:process.env.BANDMATES_LOCAL_STATUS_URL??'http://127.0.0.1:8746'
 }).inspect();
 process.stdout.write(JSON.stringify(status,null,2)+'\n');
}catch(error){
 process.stderr.write('BandMates live read-only connection unavailable: '+
   String(error?.message??error)+'\n');
 process.exitCode=1;
}
