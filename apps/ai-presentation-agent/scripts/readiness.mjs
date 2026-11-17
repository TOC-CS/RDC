#!/usr/bin/env node
// Safe diagnostic: neither starts apps nor opens microphone/camera devices.
import {presentationReadiness} from '../src/readiness.mjs';
try{
 process.stdout.write(JSON.stringify(await presentationReadiness(),null,2)+'\n');
}catch(error){
 process.stderr.write('Read-only readiness failed: '+String(error?.message??error)+'\n');
 process.exitCode=1;
}
