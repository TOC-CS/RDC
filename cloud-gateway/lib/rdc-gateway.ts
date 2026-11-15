import assets from "./rdc-assets.json";
import { createGateway } from "./rdc-gateway-core.mjs";

export const gateway = createGateway(assets);
