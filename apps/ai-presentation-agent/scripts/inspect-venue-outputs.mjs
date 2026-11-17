#!/usr/bin/env node
// No display activation, cursor movement, camera, audio or OBS streaming.
import {venueOutputReadiness} from '../src/venue-output-readiness.mjs';
process.stdout.write(JSON.stringify(await venueOutputReadiness(),null,2)+'\n');
