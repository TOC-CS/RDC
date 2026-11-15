import { env } from "cloudflare:workers";
import { gateway } from "../../../lib/rdc-gateway";

export const dynamic = "force-dynamic";
export async function POST(request: Request) { return gateway.result(request, env); }
