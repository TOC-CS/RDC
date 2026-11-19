import assets from "../rdc-assets.json";
import { createRDC2Edge } from "./rdc2-edge.mjs";

// Separate V2 gateway. Runtime stays disabled until exact private Site opt-in,
// verified rollback, compatible worker, and live acceptance are complete.
export const rdc2Edge = createRDC2Edge({ catalog: assets.catalog });
