import assets from "./rdc-assets.json";
import { createGateway } from "./rdc-gateway-core.mjs";
import { makeBoundWakeChannel } from "./rdc-wake.mjs";

// Optional private Durable Object binding. Without it, the original
// long-poll D1 transport remains fully operational and authoritative.
export const gateway = createGateway({...assets,wakeChannel:makeBoundWakeChannel});
