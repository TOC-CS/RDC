import { env } from "cloudflare:workers";
import { gateway } from "../../../lib/rdc-gateway";

export const dynamic = "force-dynamic";
export async function GET(request: Request) { return gateway.status(request, env); }
